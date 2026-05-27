#!/usr/bin/env python3
"""sop_generate CLI 入口。

用法：
    python gen.py products/XESA01.yaml                # 仅生成 HTML
    python gen.py products/XESA01.yaml --pdf          # 生成 HTML + PDF
    python gen.py products/XESA01.yaml --check        # 仅校验，不渲染
    python gen.py products/*.yaml --pdf               # 批量
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import (
    ValidationError,
    export_pdf,
    find_browser,
    load_yaml,
    validate,
)
from core.renderer import OUTPUT_DIR, write_html


def _process_one(yaml_path: Path, *, do_pdf: bool, check_only: bool) -> bool:
    print(f"\n=== {yaml_path} ===")
    if not yaml_path.exists():
        print(f"  ✗ 文件不存在", file=sys.stderr)
        return False

    try:
        data = load_yaml(yaml_path)
    except Exception as e:
        print(f"  ✗ YAML 解析失败：{e}", file=sys.stderr)
        return False

    # 校验
    result = validate(data.raw, yaml_path=yaml_path)
    for w in result.warnings:
        print(f"  ⚠ 警告：{w}")
    if not result.ok:
        for err in result.errors:
            print(f"  ✗ {err}", file=sys.stderr)
        return False
    print(f"  ✓ 校验通过（{len(result.warnings)} 条警告）")

    if check_only:
        return True

    # 渲染 HTML
    html_path = write_html(data)
    print(f"  ✓ HTML → {html_path}")

    # 导出 PDF
    if do_pdf:
        try:
            pdf_path = export_pdf(html_path)
            print(f"  ✓ PDF  → {pdf_path}")
        except Exception as e:
            print(f"  ✗ PDF 导出失败：{e}", file=sys.stderr)
            return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="sop_generate · 作业指导书生成器"
    )
    parser.add_argument(
        "yaml_files",
        nargs="+",
        type=Path,
        help="一个或多个产品 YAML 文件（支持通配符）",
    )
    parser.add_argument("--pdf", action="store_true", help="同时导出 PDF")
    parser.add_argument("--check", action="store_true",
                        help="仅校验 YAML，不渲染、不导出")
    args = parser.parse_args()

    if args.check and args.pdf:
        parser.error("--check 与 --pdf 互斥")

    if args.pdf:
        browser = find_browser()
        if browser:
            print(f"[info] 使用浏览器：{browser}")
        else:
            print("[warn] 未找到 Chrome / Edge，--pdf 将在首次失败时报错",
                  file=sys.stderr)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ok_count = 0
    fail_count = 0
    for yaml_path in args.yaml_files:
        if _process_one(yaml_path, do_pdf=args.pdf, check_only=args.check):
            ok_count += 1
        else:
            fail_count += 1

    print(f"\n完成：{ok_count} 成功 / {fail_count} 失败")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
