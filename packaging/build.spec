# -*- mode: python ; coding: utf-8 -*-
"""sop_generate · PyInstaller 跨平台 spec

构建命令（在项目根目录运行）：
    Windows:  .venv\\Scripts\\pyinstaller packaging\\build.spec --clean --noconfirm
    macOS:    .venv/bin/pyinstaller packaging/build.spec --clean --noconfirm

产物：
    Windows:  dist/sop_generate/sop_generate.exe + _internal/
    macOS:    dist/sop_generate.app
"""
import sys
from pathlib import Path

# spec 文件运行时 cwd 是项目根（PyInstaller 习惯）
PROJECT_ROOT = Path(SPECPATH).resolve().parent

block_cipher = None

# ===== 内嵌只读资源 =====
datas = [
    (str(PROJECT_ROOT / "templates"), "templates"),
    (str(PROJECT_ROOT / "products" / "_schema.yaml"), "products"),
]

# ===== 隐式导入 =====
hiddenimports = [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
    "yaml",
    "jinja2",
]

a = Analysis(
    [str(PROJECT_ROOT / "gui" / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "scipy", "pandas"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="sop_generate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                # GUI 程序，不要黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "packaging" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="sop_generate",
)

# ===== macOS .app 包装 =====
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="sop_generate.app",
        icon=str(PROJECT_ROOT / "packaging" / "icon.icns"),
        bundle_identifier="com.softhz.sop_generate",
        info_plist={
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "NSHighResolutionCapable": True,
        },
    )
