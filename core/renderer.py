"""Jinja2 渲染封装。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import paths
from .paths import OUTPUT_DIR, TEMPLATES_DIR  # noqa: F401（向后兼容导出）
from .validator import (
    OPS_PER_PAGE, NOTES_PER_PAGE, TOOLS_PER_PAGE, MATS_PER_PAGE,
    IMAGES_PER_PAGE, PROCESSES_PER_FLOW_PAGE,
)


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


_PROC_DEFAULTS: dict[str, Any] = {
    "key": False,
    "operations": [],
    "notes": [],
    "images": [],
    "tools": [],
    "materials": [],
    "_meta": None,
}


def _normalize_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """填充缺省字段，避免 StrictUndefined 在模板里炸。"""
    out: list[dict[str, Any]] = []
    for p in processes:
        merged = {**_PROC_DEFAULTS, **p}
        out.append(merged)
    return out


def _expand_process_pages(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """齐头分页：每道工序按 max(各字段需要页数) 拆成多页，每页同时显示
    operations / notes / tools / materials / images 各自的当前批次。
    """
    pages: list[dict[str, Any]] = []
    for proc_idx, proc in enumerate(processes, start=1):
        ops    = proc.get("operations") or []
        notes  = proc.get("notes") or []
        tools  = proc.get("tools") or []
        mats   = proc.get("materials") or []
        images = proc.get("images") or []

        def _pages(items: list, per: int) -> int:
            return max(1, -(-len(items) // per)) if items else 1

        total = max(
            _pages(ops, OPS_PER_PAGE),
            _pages(notes, NOTES_PER_PAGE),
            _pages(tools, TOOLS_PER_PAGE),
            _pages(mats, MATS_PER_PAGE),
            _pages(images, IMAGES_PER_PAGE),
        )

        def _slice(items: list, per: int, page_i: int) -> list:
            start = (page_i - 1) * per
            return items[start:start + per]

        for page_i in range(1, total + 1):
            pages.append({
                **proc,
                "_proc_index":      proc_idx,
                "_sub_index":       page_i,
                "_sub_total":       total,
                "_is_continuation": page_i > 1,
                "_ops_chunk":       _slice(ops,    OPS_PER_PAGE,    page_i),
                "_notes_chunk":     _slice(notes,  NOTES_PER_PAGE,  page_i),
                "_tools_chunk":     _slice(tools,  TOOLS_PER_PAGE,  page_i),
                "_mats_chunk":      _slice(mats,   MATS_PER_PAGE,   page_i),
                "_images_chunk":    _slice(images, IMAGES_PER_PAGE, page_i),
                "_ops_start_index": (page_i - 1) * OPS_PER_PAGE + 1,
                "_notes_start_index": (page_i - 1) * NOTES_PER_PAGE + 1,
                "_tools_start_index": (page_i - 1) * TOOLS_PER_PAGE + 1,
                "_mats_start_index":  (page_i - 1) * MATS_PER_PAGE + 1,
            })
    return pages


def _split_flow_chunks(processes: list[dict[str, Any]],
                        per_page: int = PROCESSES_PER_FLOW_PAGE) -> list[list[dict[str, Any]]]:
    """把工序按每页 per_page 个切片，用于工艺流程图分页渲染。"""
    return [processes[i:i + per_page] for i in range(0, len(processes), per_page)] or [[]]


def render_manual(data: ProductData, image_base: str | None = None) -> str:
    """渲染完整 HTML。

    image_base: HTML 中图片 src 前缀。
      默认（v1.1.0）：HTML 在 sop_packages/<model>/output/，图片在 sop_packages/<model>/images/
      → 相对路径 ../images
    """
    env = _make_env()
    template = env.get_template("manual.html.j2")

    if image_base is None:
        image_base = "../images"

    procs = _normalize_processes(data.processes)
    process_pages = _expand_process_pages(procs)
    flow_chunks   = _split_flow_chunks(procs)

    return template.render(
        product=data.product,
        processes=procs,                  # 目录页用规范化后的列表
        process_pages=process_pages,      # 工序详情页用展开后的
        flow_chunks=flow_chunks,          # 工艺流程图分页
        image_base=image_base,
    )


def write_html(data: ProductData, output_path: Path | None = None,
               image_base: str | None = None) -> Path:
    """渲染并写入 HTML 文件。返回最终路径。

    默认输出到 sop_packages/<model>/output/<model>.html
    """
    html = render_manual(data, image_base=image_base)

    if output_path is None:
        model = data.product.get("model", "manual")
        out_dir = paths.sop_output_dir(model)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{model}.html"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
