"""把 packaging/icon.svg 渲染为多尺寸 PNG，并合成 .icns / .ico。

用法：
    .venv/bin/python packaging/make_icons.py
"""
from __future__ import annotations

import struct
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

HERE = Path(__file__).resolve().parent
SVG  = HERE / "icon.svg"

PNG_DIR = HERE / "icon_pngs"
ICNS    = HERE / "icon.icns"
ICO     = HERE / "icon.ico"

# Apple iconset 需要的尺寸（含 @2x）
ICONSET_SIZES = [
    (16,  "icon_16x16.png"),
    (32,  "icon_16x16@2x.png"),
    (32,  "icon_32x32.png"),
    (64,  "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024,"icon_512x512@2x.png"),
]

# Windows ICO 推荐尺寸
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_png(size: int, out: Path) -> None:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer = QSvgRenderer(str(SVG))
    renderer.render(painter)
    painter.end()
    img.save(str(out), "PNG")


def build_icns(iconset_dir: Path, out: Path) -> bool:
    """优先用 macOS 的 iconutil。其他平台跳过。"""
    if sys.platform != "darwin":
        return False
    import subprocess
    res = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(out)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print("[warn] iconutil 失败：", res.stderr)
        return False
    return True


def build_ico(out: Path) -> None:
    """用 PIL 把多尺寸 PNG 合成 .ico。"""
    images = []
    for s in ICO_SIZES:
        tmp = PNG_DIR / f"_ico_{s}.png"
        render_png(s, tmp)
        images.append(Image.open(tmp))
    images[0].save(
        out,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=images[1:],
    )


def main() -> int:
    if not SVG.exists():
        print(f"[error] 缺少 {SVG}")
        return 1

    # 必须先实例化 QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    PNG_DIR.mkdir(parents=True, exist_ok=True)

    # ===== 生成 iconset PNG（macOS）=====
    iconset = PNG_DIR / "icon.iconset"
    iconset.mkdir(exist_ok=True)
    for size, name in ICONSET_SIZES:
        render_png(size, iconset / name)
    print(f"✓ 已生成 {len(ICONSET_SIZES)} 个 iconset PNG → {iconset}")

    # ===== 1024 主图（PySide6 项目本体可用）=====
    render_png(1024, PNG_DIR / "icon_1024.png")
    render_png(512,  PNG_DIR / "icon_512.png")
    render_png(256,  PNG_DIR / "icon_256.png")
    print(f"✓ 主图 PNG → {PNG_DIR}")

    # ===== .icns（macOS）=====
    if build_icns(iconset, ICNS):
        print(f"✓ macOS 图标 → {ICNS}")
    else:
        print("⚠ 未生成 .icns（非 macOS 或 iconutil 不可用）")

    # ===== .ico（Windows）=====
    build_ico(ICO)
    print(f"✓ Windows 图标 → {ICO}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
