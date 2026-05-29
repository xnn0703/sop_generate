#!/usr/bin/env python3
"""sop_generate CLI 入口（v1.1.0）

用法（三种路径都支持）：
    python gen.py DEMO01                            # 按 model 名（推荐）
    python gen.py sop_packages/DEMO01/              # 工程文件夹
    python gen.py sop_packages/DEMO01/product.yaml  # 显式 YAML
    python gen.py products/DEMO01.yaml              # v1.0.x 兼容

参数：
    --pdf        同时导出 PDF（需 Chrome/Edge）
    --check      仅校验，不渲染
    --version    显示版本号
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import (
    __version__,
    ValidationError,
    export_pdf,
    find_browser,
    load_yaml,
    validate,
)
from core.renderer import write_html
from core.paths import SOP_PACKAGES_DIR, sop_yaml_path


def _resolve_yaml(arg: str) -> Path:
    """把 CLI 参数解析为 product.yaml 的实际路径。"""
    p = Path(arg)
    # 1) 直接是文件路径
    if p.is_file() and p.suffix.lower() in (".yaml", ".yml"):
        return p
    # 2) 工程文件夹路径
    if p.is_dir() and (p / "product.yaml").is_file():
        return p / "product.yaml"
    # 3) model 名 → sop_packages/<model>/product.yaml
    candidate = sop_yaml_path(arg)
    if candidate.is_file():
        return candidate
    # 4) v1.0.x 兼容 products/<model>.yaml
    legacy = Path("products") / f"{arg}.yaml"
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(f"未找到产品：{arg}")


def _process_one(arg: str, *, do_pdf: bool, check_only: bool) -> bool:
    print(f"\n=== {arg} ===")
    try:
        yaml_path = _resolve_yaml(arg)
    except FileNotFoundError as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return False

    try:
        data = load_yaml(yaml_path)
    except Exception as e:
        print(f"  ✗ YAML 解析失败：{e}", file=sys.stderr)
        return False

    result = validate(data.raw, yaml_path=yaml_path)
    for w in result.warnings:
        print(f"  ⚠ {w}")
    if not result.ok:
        for err in result.errors:
            print(f"  ✗ {err}", file=sys.stderr)
        return False
    print(f"  ✓ 校验通过（{len(result.warnings)} 条提示）")

    if check_only:
        return True

    html_path = write_html(data)
    print(f"  ✓ HTML → {html_path}")

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
        description=f"sop_generate v{__version__} · 作业指导书生成器"
    )
    parser.add_argument("--version", action="version", version=f"sop_generate {__version__}")
    parser.add_argument(
        "targets",
        nargs="+",
        help="产品 model 名 / 工程文件夹 / YAML 文件路径，支持多个或通配符",
    )
    parser.add_argument("--pdf", action="store_true", help="同时导出 PDF")
    parser.add_argument("--check", action="store_true",
                        help="仅校验，不渲染、不导出")
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

    ok_count = 0
    fail_count = 0
    for target in args.targets:
        if _process_one(target, do_pdf=args.pdf, check_only=args.check):
            ok_count += 1
        else:
            fail_count += 1

    print(f"\n完成：{ok_count} 成功 / {fail_count} 失败")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
