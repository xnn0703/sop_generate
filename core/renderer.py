"""Jinja2 渲染封装。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import paths
from .paths import ASSETS_DIR, OUTPUT_DIR, TEMPLATES_DIR  # noqa: F401（向后兼容导出）
from .validator import OPS_PER_PAGE, PROCESSES_PER_FLOW_PAGE


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
}


def _normalize_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """填充缺省字段，避免 StrictUndefined 在模板里炸。"""
    out: list[dict[str, Any]] = []
    for p in processes:
        merged = {**_PROC_DEFAULTS, **p}
        out.append(merged)
    return out


def _expand_process_pages(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把工序列表展开为渲染页列表。
    operations 超过单页容量时自动拆成多页：第 1 页含完整结构（图、工具、材料、注意事项），
    续页只显示 operations 续写，工序号保持不变，标记 (续 N/M)。
    """
    pages: list[dict[str, Any]] = []
    for proc_idx, proc in enumerate(processes, start=1):
        ops = proc.get("operations") or []
        chunks = [ops[i:i + OPS_PER_PAGE] for i in range(0, len(ops), OPS_PER_PAGE)] or [[]]
        total = len(chunks)
        for sub_i, chunk in enumerate(chunks, start=1):
            pages.append({
                **proc,
                "_proc_index":     proc_idx,
                "_ops_chunk":      chunk,
                "_sub_index":      sub_i,
                "_sub_total":      total,
                "_is_continuation": sub_i > 1,
            })
    return pages


def _split_flow_chunks(processes: list[dict[str, Any]],
                        per_page: int = PROCESSES_PER_FLOW_PAGE) -> list[list[dict[str, Any]]]:
    """把工序按每页 per_page 个切片，用于工艺流程图分页渲染。"""
    return [processes[i:i + per_page] for i in range(0, len(processes), per_page)] or [[]]


def render_manual(data: ProductData, image_base: str | None = None) -> str:
    """渲染完整 HTML。

    image_base: HTML 中图片 src 前缀，默认指向项目内 assets/images/<model>/。
    """
    env = _make_env()
    template = env.get_template("manual.html.j2")

    if image_base is None:
        # 默认：HTML 输出在 output/，图片在 assets/images/<model>/
        model = data.product.get("model", "")
        image_base = f"../assets/images/{model}"

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
    """渲染并写入 HTML 文件。返回最终路径。"""
    html = render_manual(data, image_base=image_base)

    if output_path is None:
        model = data.product.get("model", "manual")
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = paths.OUTPUT_DIR / f"{model}.html"

    output_path.write_text(html, encoding="utf-8")
    return output_path
