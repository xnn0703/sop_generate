# -*- mode: python ; coding: utf-8 -*-
"""sop_generate · PyInstaller 双 EXE spec（主程序 + updater 共享运行时）

构建命令（在项目根目录运行）：
    Windows:  .venv\\Scripts\\pyinstaller packaging\\build.spec --clean --noconfirm
    macOS:    .venv/bin/pyinstaller packaging/build.spec --clean --noconfirm

产物：
    Windows:  dist/sop_generate/{sop_generate.exe, updater.exe, _internal/...}
    macOS:    dist/sop_generate.app + dist/updater.app
"""
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).resolve().parent

# 从 core/__init__.py 读 __version__
_VER_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
VERSION = _VER_RE.search((PROJECT_ROOT / "core" / "__init__.py").read_text("utf-8")).group(1)

block_cipher = None

# ===== 共享数据 =====
shared_datas = [
    (str(PROJECT_ROOT / "templates"), "templates"),
    (str(PROJECT_ROOT / "products" / "_schema.yaml"), "products"),
    (str(PROJECT_ROOT / "release.config.json"), "."),
]

# ===== 隐式导入 =====
shared_hidden = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "yaml",
    "jinja2",
    "py7zr",
    "psutil",
]

shared_excludes = ["tkinter", "matplotlib", "numpy", "scipy", "pandas"]

ICON = str(PROJECT_ROOT / "packaging" / ("icon.icns" if sys.platform == "darwin" else "icon.ico"))


# ===== Analysis: 主程序 =====
a_main = Analysis(
    [str(PROJECT_ROOT / "gui" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=shared_datas,
    hiddenimports=shared_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=shared_excludes,
    cipher=block_cipher,
    noarchive=False,
)

# ===== Analysis: updater =====
a_upd = Analysis(
    [str(PROJECT_ROOT / "updater" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=shared_datas,
    hiddenimports=["py7zr", "psutil"],
    hookspath=[],
    runtime_hooks=[],
    excludes=shared_excludes,
    cipher=block_cipher,
    noarchive=False,
)

# ===== MERGE：共享运行时（让两个 EXE 共用 Python + Qt + 库）=====
MERGE((a_main, "sop_generate", "sop_generate"),
      (a_upd,  "updater",      "updater"))

# ===== PYZ + EXE: 主程序 =====
pyz_main = PYZ(a_main.pure, a_main.zipped_data, cipher=block_cipher)
exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name="sop_generate",
    debug=False, strip=False, upx=False, console=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=ICON,
)

# ===== PYZ + EXE: updater =====
pyz_upd = PYZ(a_upd.pure, a_upd.zipped_data, cipher=block_cipher)
exe_upd = EXE(
    pyz_upd,
    a_upd.scripts,
    [],
    exclude_binaries=True,
    name="updater",
    debug=False, strip=False, upx=False, console=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=ICON,
)

# ===== COLLECT: 两个 EXE + 共享依赖到同一目录 =====
coll = COLLECT(
    exe_main, a_main.binaries, a_main.zipfiles, a_main.datas,
    exe_upd,  a_upd.binaries,  a_upd.zipfiles,  a_upd.datas,
    strip=False, upx=False, upx_exclude=[],
    name="sop_generate",
)

# ===== macOS BUNDLE =====
if sys.platform == "darwin":
    # 主程序 .app
    app_main = BUNDLE(
        coll,
        name="sop_generate.app",
        icon=ICON,
        bundle_identifier="org.sop_generate.app",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
        },
    )
