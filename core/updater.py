"""自动更新核心库

工作流：
1. check_latest()  调 Gitee API 查最新 release
2. is_newer()       版本号比较
3. download_release() 下载所有 .7z.NNN 分卷（带进度回调）
4. apply_update()    合并分卷 → py7zr 解压 → 覆盖文件（跳过 products/assets/output）
5. relaunch()        启动新版本可执行文件
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .paths import resource_dir

# Gitee 仓库信息从 release.config.json 读取（CI 打包时由 Secrets 注入实际值）
_CONFIG_DEFAULT = {
    "gitee_owner": "your-org",
    "gitee_repo": "sop_generate-releases",
    "gitee_api": "https://gitee.com/api/v5",
}


def _load_release_config() -> dict:
    cfg_path = resource_dir() / "release.config.json"
    if not cfg_path.exists():
        return _CONFIG_DEFAULT
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_CONFIG_DEFAULT, **{k: v for k, v in data.items() if not k.startswith("_")}}
    except (OSError, json.JSONDecodeError):
        return _CONFIG_DEFAULT


def _api_base() -> str:
    cfg = _load_release_config()
    return f"{cfg['gitee_api']}/repos/{cfg['gitee_owner']}/{cfg['gitee_repo']}"


def is_release_configured() -> bool:
    """release.config.json 是否填了真实值（不是占位）。"""
    cfg = _load_release_config()
    return cfg["gitee_owner"] not in ("your-org", "")

# 升级时保留的用户数据目录（相对于 app_dir）
PRESERVE_PATHS = {"products", "assets", "output"}

ProgressCb = Callable[[str, int, int], None]   # (stage, current_bytes, total_bytes)


@dataclass
class ReleaseInfo:
    tag: str          # "v1.1.0"
    name: str         # release 标题
    body: str         # release 描述
    assets: list[dict]  # [{name, browser_download_url, size}, ...]

    @property
    def archive_parts(self) -> list[dict]:
        """筛选出当前平台的 7z 分卷附件，按名字排序。"""
        if sys.platform == "darwin":
            pat = re.compile(r"sop_generate-mac.+\.7z\.\d+$", re.I)
        else:
            pat = re.compile(r"sop_generate-win.+\.7z\.\d+$", re.I)
        parts = [a for a in self.assets if pat.search(a["name"])]
        return sorted(parts, key=lambda x: x["name"])


# =================================================================
# 1. 检查更新
# =================================================================
def check_latest(timeout: float = 8.0) -> ReleaseInfo | None:
    """查 Gitee 最新 release。失败返回 None（不抛，调用方静默忽略）。"""
    if not is_release_configured():
        return None
    try:
        req = urllib.request.Request(
            f"{_api_base()}/releases/latest",
            headers={"User-Agent": "sop_generate-updater"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    return ReleaseInfo(
        tag=data.get("tag_name", ""),
        name=data.get("name", ""),
        body=data.get("body", ""),
        assets=data.get("assets") or [],
    )


# =================================================================
# 2. 版本比较
# =================================================================
def _parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v.lstrip("vV"))
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def is_newer(remote_tag: str, local_version: str) -> bool:
    return _parse_version(remote_tag) > _parse_version(local_version)


# =================================================================
# 3. 下载
# =================================================================
def _download_one(url: str, out: Path, max_retry: int = 4,
                  progress: ProgressCb | None = None,
                  total_so_far_callback=None) -> int:
    """下载单个文件，含重试 + Content-Length 大小校验。

    返回实际写入的字节数。任何阶段失败会自动重试，全部重试失败抛 RuntimeError。
    """
    last_err: Exception | None = None
    for attempt in range(1, max_retry + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sop_generate-updater"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                cl = resp.headers.get("Content-Length")
                expected = int(cl) if cl and cl.isdigit() else None
                written = 0
                with open(out, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 64)
                        if not chunk:
                            break
                        f.write(chunk)
                        written += len(chunk)
                        if progress and total_so_far_callback:
                            progress(f"下载 {out.name}", *total_so_far_callback(written))

            # 大小校验
            actual = out.stat().st_size
            if expected is not None and actual != expected:
                raise RuntimeError(
                    f"{out.name} 下载不完整：实际 {actual} 字节，"
                    f"服务器 Content-Length 声明 {expected} 字节"
                )
            return actual
        except Exception as e:
            last_err = e
            try:
                if out.exists():
                    out.unlink()
            except OSError:
                pass
            if attempt < max_retry:
                time.sleep(min(2 ** attempt, 10))
                continue
    raise RuntimeError(f"{out.name} 下载失败（重试 {max_retry} 次）：{last_err}")


def download_release(release: ReleaseInfo, target_dir: Path,
                     progress: ProgressCb | None = None) -> list[Path]:
    """把所有 .7z 分卷下载到 target_dir，返回本地文件路径列表。

    单个分卷失败自动重试 4 次（指数退避），全部下载完成后做大小校验。
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    parts = release.archive_parts
    if not parts:
        raise RuntimeError(f"Release {release.tag} 未包含 .7z 分卷附件")

    # 总字节数（assets size 字段可能缺失）
    total_bytes = sum(p.get("size") or 0 for p in parts)
    total_done = 0
    local_files: list[Path] = []

    for asset in parts:
        url = asset["browser_download_url"]
        out = target_dir / asset["name"]
        expected_size = asset.get("size") or 0

        # 已存在且大小一致就跳过
        if out.exists() and expected_size > 0 and out.stat().st_size == expected_size:
            total_done += out.stat().st_size
            local_files.append(out)
            if progress:
                progress(f"已存在 {asset['name']}", total_done, total_bytes)
            continue

        start_done = total_done

        def cb(written: int, _start=start_done) -> tuple[int, int]:
            return (_start + written, total_bytes)

        written = _download_one(url, out, progress=progress, total_so_far_callback=cb)
        total_done = start_done + written
        local_files.append(out)

    return local_files


# =================================================================
# 4. 解压并应用更新
# =================================================================
def _merge_parts(parts: list[Path], merged_path: Path,
                  progress: ProgressCb | None = None) -> Path:
    """把分卷合并成单个 .7z 文件。"""
    total = sum(p.stat().st_size for p in parts)
    done = 0
    with open(merged_path, "wb") as out:
        for p in parts:
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress("合并分卷", done, total)
    return merged_path


def _extract_7z(archive: Path, dest: Path,
                  progress: ProgressCb | None = None) -> None:
    import py7zr
    if progress:
        progress("解压中（请稍候）", 0, 1)
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=dest)
    if progress:
        progress("解压完成", 1, 1)


def apply_update(parts: list[Path], app_dir: Path, tag: str = "",
                 progress: ProgressCb | None = None) -> Path:
    """应用更新到 app_dir，返回新主程序可执行文件路径。

    Windows：原地替换（除 PRESERVE_PATHS 外的文件）。
    macOS：解压到 app_dir/sop_generate-mac-<tag>/ 隔壁目录，并把用户数据复制过去
            （避免 updater 删除自己所在的 .app 包）。
    """
    staging = app_dir.parent / f".sop_generate_staging_{int(time.time())}"
    staging.mkdir(parents=True, exist_ok=True)

    try:
        merged = _merge_parts(parts, staging / "merged.7z", progress)

        # 7z 魔数校验，提前发现下载/合并出问题
        with open(merged, "rb") as f:
            magic = f.read(6)
        if magic != b"\x37\x7a\xbc\xaf\x27\x1c":
            raise RuntimeError(
                f"合并后的 7z 文件头错误（魔数 {magic.hex()}，应为 377abcaf271c）。"
                f"可能某个分卷下载不完整或损坏，请重新启动程序重试更新。"
            )

        _extract_7z(merged, staging, progress)
        try:
            merged.unlink()
        except OSError:
            pass

        # 解压结果应该是 staging/sop_generate-{win,mac}-vX.Y.Z/
        sub_dirs = [d for d in staging.iterdir() if d.is_dir()]
        if not sub_dirs:
            raise RuntimeError("7z 解压后未找到任何子目录")
        new_root = sub_dirs[0]
        if progress:
            progress(f"解压完成，新版位于 {new_root.name}", 1, 1)

        # 通用：原地替换 app_dir 下除 PRESERVE_PATHS 外的所有文件
        # （macOS 上 updater 已通过 self-relocation 搬到 /tmp 跑，
        #   所以可以放心删除原 .app；symlinks=True 保留 .app 内部链接）
        for item in new_root.iterdir():
            if item.name in PRESERVE_PATHS:
                continue
            target = app_dir / item.name
            if progress:
                progress(f"替换 {item.name}", 0, 1)
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if item.is_dir():
                shutil.copytree(item, target, symlinks=True)
            else:
                shutil.copy2(item, target, follow_symlinks=False)

        # 返回新主程序路径
        if sys.platform == "darwin":
            new_app = app_dir / "sop_generate.app"
            return new_app if new_app.exists() else app_dir
        else:
            exe = app_dir / "sop_generate.exe"
            return exe if exe.exists() else app_dir
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# =================================================================
# 5. 等待主程序退出 + 启动新版本
# =================================================================
def wait_for_pid(pid: int, timeout: float = 30.0) -> bool:
    """等指定 PID 进程退出，返回是否成功退出。"""
    try:
        import psutil
    except ImportError:
        time.sleep(3)   # 兜底：盲等 3 秒
        return True

    end = time.time() + timeout
    while time.time() < end:
        if not psutil.pid_exists(pid):
            return True
        time.sleep(0.5)
    return False


def relaunch(exe_or_app: Path) -> None:
    """启动新版本（不等待，立即返回）。"""
    if sys.platform == "darwin" and exe_or_app.suffix == ".app":
        subprocess.Popen(["open", str(exe_or_app)])
    elif sys.platform == "win32":
        subprocess.Popen([str(exe_or_app)], creationflags=0x00000008)  # DETACHED_PROCESS
    else:
        subprocess.Popen([str(exe_or_app)])
