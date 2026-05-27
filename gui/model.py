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
    "company": "南京软赫电子科技有限公司",
    "doc_id": "SH-ZY-04",
    "version": "A/0",
    "publish_date": "2026-3-30",
    "effective_date": "2026-4-1",
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


def clone_product(src: Product, new_model: str) -> Product:
    """基于现有产品派生新产品（保留工序结构，清空图片）。"""
    new_path = PRODUCTS_DIR / f"{new_model}.yaml"
    new_prod = copy.deepcopy(src.product)
    new_prod["model"] = new_model
    new_procs = copy.deepcopy(src.processes)
    for p in new_procs:
        p["images"] = []  # 提示用户重新选图
    return Product(path=new_path, product=new_prod, processes=new_procs)
