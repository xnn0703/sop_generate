"""GUI 的数据模型层 — 封装 SOP 工程包的增删改查

v1.1.0 新结构：每个 SOP 一个独立工程文件夹
    sop_packages/<model>/
    ├── product.yaml      （含 _meta 修改追溯）
    ├── images/
    └── output/
"""
from __future__ import annotations

import copy
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from core.paths import (
    SOP_PACKAGES_DIR, sop_package_dir, sop_yaml_path, sop_images_dir,
    sop_output_dir,
)
from core.process_utils import normalize_process_sequence

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
    "level": 1,
    "work_time_min": "",
    "operations": [],
    "notes": [],
    "images": [],
    "tools": [],
    "materials": [],
}


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _ensure_meta(d: dict, user: str) -> dict:
    """确保 dict 含 _meta 字段并填好创建信息。返回 _meta dict。"""
    if "_meta" not in d:
        d["_meta"] = {
            "created_by": user,
            "created_at": _now_iso(),
            "last_modified_by": user,
            "last_modified_at": _now_iso(),
        }
    return d["_meta"]


def _update_modified(d: dict, user: str) -> None:
    meta = _ensure_meta(d, user)
    meta["last_modified_by"] = user
    meta["last_modified_at"] = _now_iso()


def _strip_meta_for_compare(d: dict) -> dict:
    """剥离 _meta 字段后用于比较两个版本是否真有改动。"""
    out = {k: v for k, v in d.items() if k != "_meta"}
    return out


def _process_identity(d: dict) -> str | None:
    """用自动追溯里的 created_at 识别同一道工序，避免拖拽排序误判为内容修改。"""
    meta = d.get("_meta") or {}
    key = meta.get("created_at")
    return str(key) if key else None


@dataclass
class Product:
    """一个 SOP 产品（对应 sop_packages/<model>/）"""
    model: str
    product: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_PRODUCT))
    processes: list[dict[str, Any]] = field(default_factory=list)
    _snapshot: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    @property
    def path(self) -> Path:
        return sop_yaml_path(self.model)

    @property
    def package_dir(self) -> Path:
        return sop_package_dir(self.model)

    @property
    def image_dir(self) -> Path:
        return sop_images_dir(self.model)

    @property
    def output_dir(self) -> Path:
        return sop_output_dir(self.model)

    @classmethod
    def load(cls, model_or_path) -> Product:
        """从型号名或 product.yaml 路径加载。"""
        if isinstance(model_or_path, Path):
            yaml_path = model_or_path
            # 从路径推断 model
            if yaml_path.name == "product.yaml":
                model = yaml_path.parent.name
            else:
                # 兼容 v1.0.x: products/XESA01.yaml
                model = yaml_path.stem
        else:
            model = model_or_path
            yaml_path = sop_yaml_path(model)

        if not yaml_path.exists():
            raise FileNotFoundError(f"SOP 工程文件不存在: {yaml_path}")

        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        prod = cls(
            model=model,
            product=raw.get("product", copy.deepcopy(DEFAULT_PRODUCT)),
            processes=raw.get("processes", []),
        )
        normalize_process_sequence(prod.processes)
        # 记快照用于"是否修改"判定；自动补默认 level 不算用户修改
        prod._snapshot = copy.deepcopy({"product": prod.product, "processes": prod.processes})
        return prod

    def save(self, current_user: str) -> None:
        """保存到磁盘，并按需更新 _meta 修改追溯字段。

        策略：对比 _snapshot 和当前数据，只更新真正改动过的段的 _meta。
        """
        if not current_user:
            raise ValueError("用户名未设置，无法保存")
        normalize_process_sequence(self.processes)

        # ===== 比较 product 段 =====
        snap_product = self._snapshot.get("product", {})
        cur_product = self.product
        # 比较时剥离 _meta
        if _strip_meta_for_compare(cur_product) != _strip_meta_for_compare(snap_product):
            _update_modified(cur_product, current_user)
        elif "_meta" not in cur_product:
            # 即使没改也补全 _meta（首次保存）
            _ensure_meta(cur_product, current_user)

        # ===== 比较各工序 =====
        snap_procs = self._snapshot.get("processes", [])
        snap_by_identity = {
            ident: snap
            for snap in snap_procs
            if (ident := _process_identity(snap))
        }
        for i, proc in enumerate(self.processes):
            ident = _process_identity(proc)
            snap = snap_by_identity.get(ident) if ident else None
            if snap is None and len(self.processes) == len(snap_procs) and i < len(snap_procs):
                snap = snap_procs[i]
            if snap is None:
                # 新增的工序
                _ensure_meta(proc, current_user)
                _update_modified(proc, current_user)
            else:
                if _strip_meta_for_compare(proc) != _strip_meta_for_compare(snap):
                    _update_modified(proc, current_user)
                elif "_meta" not in proc:
                    # 复制原 _meta 或新建
                    proc["_meta"] = snap.get("_meta") or {
                        "created_by": current_user,
                        "created_at": _now_iso(),
                        "last_modified_by": current_user,
                        "last_modified_at": _now_iso(),
                    }

        # ===== 写文件 =====
        self.package_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)
        data = {"product": self.product, "processes": self.processes}
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False, width=120)

        # 更新快照
        self._snapshot = copy.deepcopy(data)

    def ensure_image_dir(self) -> Path:
        self.image_dir.mkdir(parents=True, exist_ok=True)
        return self.image_dir

    def import_image(self, src: Path) -> str:
        """复制图片到本 SOP 工程的 images 目录。"""
        self.ensure_image_dir()
        dst = self.image_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        return src.name

    def to_dict(self) -> dict[str, Any]:
        return {"product": self.product, "processes": self.processes}


def list_products() -> list[str]:
    """返回所有 SOP 工程包的 model 名（按字母排序）。"""
    SOP_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for d in sorted(SOP_PACKAGES_DIR.iterdir()):
        if d.is_dir() and (d / "product.yaml").exists() and not d.name.startswith("_"):
            out.append(d.name)
    return out


def new_product(model: str) -> Product:
    """创建新 SOP 工程包骨架，返回 Product 对象（未保存）。"""
    if (SOP_PACKAGES_DIR / model).exists():
        raise ValueError(f"产品 {model} 已存在")
    product = copy.deepcopy(DEFAULT_PRODUCT)
    product["model"] = model
    p = Product(model=model, product=product, processes=[])
    return p


def delete_product(model: str) -> Path:
    """删除整个 SOP 工程包目录。
    返回被删除目录的父级（成功标识）。如果 model 不存在抛 FileNotFoundError。
    """
    pkg = sop_package_dir(model)
    if not pkg.exists() or not pkg.is_dir():
        raise FileNotFoundError(f"SOP 工程不存在：{pkg}")
    shutil.rmtree(pkg)
    return pkg.parent


def clone_product(src: Product, new_model: str) -> Product:
    """基于现有产品派生新产品（保留工序结构，清空图片，清空 _meta）。"""
    if (SOP_PACKAGES_DIR / new_model).exists():
        raise ValueError(f"产品 {new_model} 已存在")
    new_prod = copy.deepcopy(src.product)
    new_prod["model"] = new_model
    new_prod.pop("_meta", None)
    new_procs = copy.deepcopy(src.processes)
    for p in new_procs:
        p["images"] = []
        p.pop("_meta", None)
        p.setdefault("level", 1)
        p.setdefault("work_time_min", "")
    return Product(model=new_model, product=new_prod, processes=new_procs)


def import_legacy(src_dir: Path) -> dict[str, list[str]]:
    """从 v1.0.x 目录（含 products/ 和 assets/images/）导入到新结构 sop_packages/。

    兼容两种结构：
      - 老 sop_generate-win/（含 products/ + assets/images/）
      - 直接传 products/ 目录（图片须用户单独放）

    返回：imported / skipped 列表。
    """
    if not src_dir.exists():
        raise ValueError(f"目录不存在：{src_dir}")

    # 定位老的 products / images
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

    imported: list[str] = []
    skipped:  list[str] = []
    img_count = 0
    img_skipped = 0

    SOP_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    for yaml_file in sorted(src_products.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        model = yaml_file.stem
        pkg_dir = SOP_PACKAGES_DIR / model
        if pkg_dir.exists():
            skipped.append(model)
            continue

        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "images").mkdir(exist_ok=True)
        # 复制 YAML
        shutil.copy2(yaml_file, pkg_dir / "product.yaml")

        # 复制图片
        old_img_dir = src_images / model if src_images.is_dir() else None
        if old_img_dir and old_img_dir.is_dir():
            for img in sorted(old_img_dir.iterdir()):
                if img.is_file():
                    dst = pkg_dir / "images" / img.name
                    if dst.exists():
                        img_skipped += 1
                        continue
                    shutil.copy2(img, dst)
                    img_count += 1
        imported.append(model)

    return {
        "imported_products":  imported,
        "skipped_products":   skipped,
        "imported_images":    [str(img_count)],
        "skipped_images":     [str(img_skipped)],
    }
