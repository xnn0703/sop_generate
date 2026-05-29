"""SOP 归档：定稿后一键打包

输出结构（用户指定目标文件夹下）：
    <用户选的文件夹>/
    ├── <MODEL>_YYYYMMDD/             ← 工程文件夹（已重命名带日期）
    │   ├── product.yaml
    │   ├── images/
    │   ├── <MODEL>_YYYYMMDD.html
    │   └── <MODEL>_YYYYMMDD.pdf
    └── <MODEL>_YYYYMMDD.sopkg        ← 同名包文件（zip）
"""
from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

from core.paths import sop_package_dir
from core.renderer import load_yaml, render_manual
from core.pdf_export import export_pdf, find_browser


def archive_product(model: str, dest_dir: Path,
                    progress=None) -> dict:
    """归档一个 SOP 工程：复制 + 渲染 HTML/PDF + 打包 .sopkg。

    返回 dict：
        archive_name: <MODEL>_YYYYMMDD
        archive_dir:  目标工程文件夹
        html_path:    生成的 HTML
        pdf_path:     生成的 PDF（None 表示未生成）
        sopkg_path:   .sopkg 包
    """
    src = sop_package_dir(model)
    if not src.exists():
        raise FileNotFoundError(f"SOP 工程不存在：{src}")
    src_yaml = src / "product.yaml"
    if not src_yaml.exists():
        raise FileNotFoundError(f"product.yaml 不存在：{src_yaml}")

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    archive_name = f"{model}_{date_str}"
    archive_dir = dest_dir / archive_name

    # 如果同名已存在，加序号
    counter = 1
    while archive_dir.exists():
        counter += 1
        archive_dir = dest_dir / f"{archive_name}_{counter}"
        archive_name = archive_dir.name

    if progress: progress(f"创建归档目录 {archive_name}", 0, 4)

    # 复制工程内容（product.yaml + images/）
    archive_dir.mkdir(parents=True)
    shutil.copy2(src_yaml, archive_dir / "product.yaml")
    src_imgs = src / "images"
    if src_imgs.is_dir():
        shutil.copytree(src_imgs, archive_dir / "images")

    if progress: progress("渲染 HTML", 1, 4)

    # 渲染 HTML（指向 archive 目录里的 images/）
    data = load_yaml(archive_dir / "product.yaml")
    html_str = render_manual(data, image_base="images")
    html_path = archive_dir / f"{archive_name}.html"
    html_path.write_text(html_str, encoding="utf-8")

    # 渲染 PDF（可选，找不到浏览器就跳过）
    pdf_path: Path | None = None
    if find_browser():
        if progress: progress("渲染 PDF", 2, 4)
        try:
            pdf_path = export_pdf(html_path, archive_dir / f"{archive_name}.pdf")
        except Exception as e:
            pdf_path = None
            if progress: progress(f"PDF 导出失败：{e}", 2, 4)

    if progress: progress("打包 .sopkg", 3, 4)

    # 打包 .sopkg（含归档目录里所有内容，含 HTML/PDF）
    sopkg_path = dest_dir / f"{archive_name}.sopkg"
    with zipfile.ZipFile(sopkg_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in archive_dir.rglob("*"):
            if f.is_file():
                arcname = Path(archive_name) / f.relative_to(archive_dir)
                zf.write(f, arcname.as_posix())

    if progress: progress("完成", 4, 4)

    return {
        "archive_name": archive_name,
        "archive_dir":  archive_dir,
        "html_path":    html_path,
        "pdf_path":     pdf_path,
        "sopkg_path":   sopkg_path,
    }
