"""调用 Chromium 系浏览器 headless 把 HTML 渲染为 PDF。

优先级：Google Chrome > Microsoft Edge > Chromium > Brave。
都未找到时抛 RuntimeError，调用方应回退到"提示用户手动 ⌘P"。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_MAC_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]
_LINUX_CMDS = ["google-chrome", "chromium-browser", "chromium", "microsoft-edge"]
_WIN_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str | None:
    """返回可用浏览器的可执行路径，找不到返回 None。"""
    if sys.platform == "darwin":
        for p in _MAC_CANDIDATES:
            if Path(p).exists():
                return p
    elif sys.platform.startswith("linux"):
        for cmd in _LINUX_CMDS:
            p = shutil.which(cmd)
            if p:
                return p
    elif sys.platform == "win32":
        for p in _WIN_PATHS:
            if Path(p).exists():
                return p
    return None


def export_pdf(html_path: Path, pdf_path: Path | None = None,
               browser: str | None = None) -> Path:
    """把 HTML 渲染为 PDF。

    返回 PDF 路径。失败抛 RuntimeError。
    """
    html_path = html_path.resolve()
    if not html_path.exists():
        raise FileNotFoundError(f"HTML 不存在：{html_path}")

    if pdf_path is None:
        pdf_path = html_path.with_suffix(".pdf")
    pdf_path = pdf_path.resolve()

    browser = browser or find_browser()
    if not browser:
        raise RuntimeError(
            "未找到 Chrome / Edge / Chromium。请安装其一，或用 --html-only 仅生成 HTML 后手动 ⌘P。"
        )

    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not pdf_path.exists():
        raise RuntimeError(
            f"浏览器导出 PDF 失败（exit={result.returncode}）\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    return pdf_path
