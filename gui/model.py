"""GUI 的数据模型层 — 封装 YAML 增删改查"""
from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.paths import IMAGES_DIR, PRODUCTS_DIR  # noqa: F401

DEFAULT_PRODUCT = {
    "model": "",
    "name": "",
    "company": "",
    "doc_id": "",
    "version": "A/0",
    "publish_date": "",
    "effective_date": "",
}

DEFAULT_PROCESS = {
    "name": "新工序",
    "key": False,
    "operations": [""],
    "notes": [],
    "images": [],
    "tools": [],
    "materials": [],
}


@dataclass
class Product:
    path: Path
    product: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_PRODUCT))
    processes: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> Product:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(
            path=path,
            product=raw.get("product", copy.deepcopy(DEFAULT_PRODUCT)),
            processes=raw.get("processes", []),
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"product": self.product, "processes": self.processes}
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False, width=120)

    @property
    def model(self) -> str:
        return self.product.get("model", "")

    @property
    def image_dir(self) -> Path:
        return IMAGES_DIR / self.model

    def ensure_image_dir(self) -> Path:
        self.image_dir.mkdir(parents=True, exist_ok=True)
        return self.image_dir

    def import_image(self, src: Path) -> str:
        """复制图片到当前产品图片目录，返回文件名。"""
        self.ensure_image_dir()
        dst = self.image_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        return src.name

    def to_dict(self) -> dict[str, Any]:
        return {"product": self.product, "processes": self.processes}


def list_products() -> list[Path]:
    """列出 products/ 下所有 yaml（排除 _schema.yaml）。"""
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        p for p in PRODUCTS_DIR.glob("*.yaml")
        if not p.name.startswith("_")
    )


def new_product(model: str) -> Product:
    """创建新产品 YAML 骨架，返回 Product 对象（未保存）。"""
    path = PRODUCTS_DIR / f"{model}.yaml"
    product = copy.deepcopy(DEFAULT_PRODUCT)
    product["model"] = model
    return Product(path=path, product=product, processes=[])


def import_legacy(src_dir: Path) -> dict[str, list[str]]:
    """从老版本/外部目录导入产品 YAML + 图片。

    src_dir 兼容两种结构：
      - 老 sop_generate-win/（含 products/ + assets/images/）
      - 直接传 products/ 目录（图片须用户单独放）

    重名 YAML 默认跳过（不覆盖用户当前数据）；同名图片同样跳过。
    返回字典：imported_yaml / imported_images / skipped_yaml / skipped_images。
    """
    if not src_dir.exists():
        raise ValueError(f"目录不存在：{src_dir}")

    # 定位 products / images
    if (src_dir / "products").is_dir():
        src_products = src_dir / "products"
        src_images   = src_dir / "assets" / "images"
    elif src_dir.name == "products" and src_dir.is_dir():
        src_products = src_dir
        src_images   = src_dir.parent / "assets" / "images"
    else:
        raise ValueError(
            f"在 {src_dir} 下未找到 products 目录。请选择老版本根目录（含 products/）"
            "或直接选 products 目录。"
        )

    imported_yaml: list[str] = []
    skipped_yaml: list[str]  = []
    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    for yaml_file in sorted(src_products.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue  # 跳过 _schema.yaml 等内部文件
        dst = PRODUCTS_DIR / yaml_file.name
        if dst.exists():
            skipped_yaml.append(yaml_file.name)
            continue
        shutil.copy2(yaml_file, dst)
        imported_yaml.append(yaml_file.name)

    imported_images: list[str] = []
    skipped_images: list[str]  = []
    if src_images.is_dir():
        for model_dir in sorted(src_images.iterdir()):
            if not model_dir.is_dir():
                continue
            dst_model = IMAGES_DIR / model_dir.name
            dst_model.mkdir(parents=True, exist_ok=True)
            for img in sorted(model_dir.iterdir()):
                if not img.is_file():
                    continue
                dst_img = dst_model / img.name
                if dst_img.exists():
                    skipped_images.append(f"{model_dir.name}/{img.name}")
                    continue
                shutil.copy2(img, dst_img)
                imported_images.append(f"{model_dir.name}/{img.name}")

    return {
        "imported_yaml":  imported_yaml,
        "imported_images": imported_images,
        "skipped_yaml":   skipped_yaml,
        "skipped_images": skipped_images,
    }


def clone_product(src: Product, new_model: str) -> Product:
    """基于现有产品派生新产品（保留工序结构，清空图片）。"""
    new_path = PRODUCTS_DIR / f"{new_model}.yaml"
    new_prod = copy.deepcopy(src.product)
    new_prod["model"] = new_model
    new_procs = copy.deepcopy(src.processes)
    for p in new_procs:
        p["images"] = []  # 提示用户重新选图
    return Product(path=new_path, product=new_prod, processes=new_procs)
