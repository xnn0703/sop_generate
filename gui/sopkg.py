"""SOP 工程包（.sopkg）导入导出

.sopkg 本质是 zip 文件，根目录是 SOP 工程文件夹：

    XESA01.sopkg                     ← 顶层 zip
    └── XESA01/
        ├── product.yaml
        ├── images/
        └── output/  （可选）
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from core.paths import SOP_PACKAGES_DIR, sop_package_dir


def export_sopkg(model: str, dst: Path) -> Path:
    """把 sop_packages/<model>/ 打包为 .sopkg（zip 改名）。"""
    src = sop_package_dir(model)
    if not src.exists():
        raise FileNotFoundError(f"SOP 工程不存在：{src}")

    dst = Path(dst)
    if dst.suffix.lower() not in (".sopkg", ".zip"):
        dst = dst.with_suffix(".sopkg")

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob("*"):
            if file.is_file():
                arcname = Path(model) / file.relative_to(src)
                zf.write(file, arcname.as_posix())
    return dst


def import_sopkg(src: Path) -> tuple[str, bool]:
    """从 .sopkg 解压到 sop_packages/。

    返回 (model, overwritten)。如果同名已存在会先备份为 <model>.bak_<ts>/。
    """
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(f"文件不存在：{src}")

    with zipfile.ZipFile(src, "r") as zf:
        names = zf.namelist()
        # 找根目录（应该只有一个，对应 model 名）
        roots = sorted({Path(n).parts[0] for n in names if n.strip("/")})
        if not roots:
            raise ValueError(f"{src.name} 是空包")
        if len(roots) > 1:
            raise ValueError(f"{src.name} 包含多个根目录，期望恰好一个 SOP")

        model = roots[0]
        # 校验合法 model 名（仅禁文件系统不允许字符）
        forbidden = set('\\/:*?"<>|')
        bad = sorted({c for c in model if c in forbidden or ord(c) < 32})
        if bad:
            raise ValueError(f"包内的 model 名 {model!r} 含文件系统不允许字符 {''.join(bad)!r}")

        # 校验必须含 product.yaml
        if not any(n.endswith(f"{model}/product.yaml") or n == f"{model}/product.yaml"
                   for n in names):
            raise ValueError(f"{src.name} 内未找到 {model}/product.yaml")

        # 已存在则备份
        dst_dir = sop_package_dir(model)
        overwritten = False
        if dst_dir.exists():
            import time
            backup = dst_dir.with_name(f"{model}.bak_{int(time.time())}")
            shutil.move(str(dst_dir), str(backup))
            overwritten = True

        SOP_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        zf.extractall(path=SOP_PACKAGES_DIR)

    return model, overwritten
