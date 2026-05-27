"""统一的路径解析。

打包后（PyInstaller）：
  - 只读资源（templates）从 sys._MEIPASS 加载
  - 用户数据（products / assets / output）放在 exe 同级目录

开发态：
  - 全部相对于项目根（即 core/ 的父目录）
"""
from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    """用户数据目录（用户可编辑的 products/assets/output）。

    - macOS .app：上溯到 .app 的父目录（数据放 .app 旁边，避免写入 bundle 内部）
    - Windows / Linux 打包态：exe 所在目录
    - 开发态：项目根（core/ 的父目录）
    """
    if _is_frozen():
        exe = Path(sys.executable).resolve()
        # macOS .app bundle 内：找到 .app 自身，返回它的父目录
        for parent in (exe, *exe.parents):
            if parent.suffix == ".app":
                return parent.parent
        return exe.parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """只读资源目录（templates / 图标等）。

    - 打包态：sys._MEIPASS（PyInstaller 解包目录）
    - 开发态：项目根
    """
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return Path(__file__).resolve().parent.parent


# ===== 各子目录 =====
TEMPLATES_DIR = resource_dir() / "templates"
PRODUCTS_DIR  = app_dir() / "products"
ASSETS_DIR    = app_dir() / "assets"
IMAGES_DIR    = ASSETS_DIR / "images"
OUTPUT_DIR    = app_dir() / "output"


def ensure_user_dirs() -> None:
    """确保用户数据目录存在（打包后首次运行可能需要创建）。"""
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
