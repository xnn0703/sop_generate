"""Jinja2 渲染封装。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import paths
from .paths import ASSETS_DIR, OUTPUT_DIR, TEMPLATES_DIR  # noqa: F401（向后兼容导出）


# ===== Jinja2 自定义 filter =====
_CIRCLED = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]

def _circled(n: int) -> str:
    if 1 <= n <= len(_CIRCLED):
        return _CIRCLED[n - 1]
    return f"({n})"


def _make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(paths.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    env.filters["circled"] = _circled
    return env


@dataclass
class ProductData:
    product: dict[str, Any]
    processes: list[dict[str, Any]]
    raw: dict[str, Any]


def load_yaml(path: Path) -> ProductData:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return ProductData(
        product=raw.get("product", {}),
        processes=raw.get("processes", []),
        raw=raw,
    )


def render_manual(data: ProductData, image_base: str | None = None) -> str:
    """渲染完整 HTML。

    image_base: HTML 中图片 src 前缀，默认指向项目内 assets/images/<model>/。
    传入相对路径（如 'assets/images/XESA01'）便于浏览器和 Edge headless 解析。
    """
    env = _make_env()
    template = env.get_template("manual.html.j2")

    if image_base is None:
        # 默认：HTML 输出在 output/，图片在 assets/images/<model>/
        model = data.product.get("model", "")
        image_base = f"../assets/images/{model}"

    return template.render(
        product=data.product,
        processes=data.processes,
        image_base=image_base,
    )


def write_html(data: ProductData, output_path: Path | None = None,
               image_base: str | None = None) -> Path:
    """渲染并写入 HTML 文件。返回最终路径。"""
    html = render_manual(data, image_base=image_base)

    if output_path is None:
        model = data.product.get("model", "manual")
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = paths.OUTPUT_DIR / f"{model}.html"

    output_path.write_text(html, encoding="utf-8")
    return output_path
