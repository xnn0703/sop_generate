"""统一的路径解析。

【v1.1.0 新结构】
打包后/开发态都遵循以下布局：

    app_dir/                       ← 应用安装目录
    ├── sop_packages/             ← 所有 SOP 工程包（每个 SOP 一个文件夹）
    │   ├── XESA01/
    │   │   ├── product.yaml      ← 产品 + 工序数据 + _meta 追溯
    │   │   ├── images/           ← 该产品所有图片
    │   │   └── output/           ← 该产品 HTML/PDF 输出
    │   └── XESA02/
    ├── config/                   ← 应用级配置
    │   └── current_user.json     ← 当前用户名（必填）
    ├── _legacy_v1_backup/        ← v1.0.x 老数据备份（自动迁移后生成）
    └── output/                   ← 公共输出（CLI 批量等场景）

【路径来源】
- 打包态：app_dir = sys.executable 的父目录（或 macOS .app 的父目录）
- 开发态：app_dir = 项目根
"""
from __future__ import annotations

import sys
from pathlib import Path


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    """用户数据目录（用户可编辑的 sop_packages/config/output 等）。

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
TEMPLATES_DIR   = resource_dir() / "templates"
SOP_PACKAGES_DIR = app_dir() / "sop_packages"      # 新：所有 SOP 工程包
CONFIG_DIR      = app_dir() / "config"             # 新：应用配置（用户名等）
LEGACY_BACKUP   = app_dir() / "_legacy_v1_backup"  # v1.0.x 数据备份位置
OUTPUT_DIR      = app_dir() / "output"             # 公共输出（CLI 批量）

# ===== v1.0.x 兼容路径（仅用于检测迁移，迁移后这些不再使用）=====
LEGACY_PRODUCTS_DIR = app_dir() / "products"
LEGACY_IMAGES_DIR   = app_dir() / "assets" / "images"

# ===== 单个 SOP 工程包内的子目录 =====
def sop_package_dir(model: str) -> Path:
    return SOP_PACKAGES_DIR / model

def sop_yaml_path(model: str) -> Path:
    return sop_package_dir(model) / "product.yaml"

def sop_images_dir(model: str) -> Path:
    return sop_package_dir(model) / "images"

def sop_output_dir(model: str) -> Path:
    return sop_package_dir(model) / "output"


def ensure_user_dirs() -> None:
    """确保应用级目录存在（打包后首次运行可能需要创建）。"""
    SOP_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def has_legacy_data() -> bool:
    """是否存在 v1.0.x 的老数据待迁移。"""
    if not LEGACY_PRODUCTS_DIR.exists():
        return False
    yamls = [p for p in LEGACY_PRODUCTS_DIR.glob("*.yaml")
             if not p.name.startswith("_")]
    return bool(yamls)
