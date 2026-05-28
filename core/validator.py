"""YAML 字段约束校验。

约束阈值集中在本模块顶部，便于 GUI 实时高亮和 CLI 校验复用。
所有错误信息使用中文。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# =============== 字段约束 ===============
# 长度类不再硬限：单元格 overflow:hidden 自动裁切；只校验"数量"类硬约束。
OPS_PER_PAGE         = 6    # 单页能放下的操作说明 条数（超过自动拆页）
MAX_OPS              = 18   # 操作说明 条数上限（最多拆 3 页）
MAX_NOTES            = 4    # 注意事项 条数上限（超过请拆工序）
MAX_TOOLS            = 4    # 工具设备 项数上限
MAX_MATS             = 4    # 作业材料 项数上限
MAX_IMAGES           = 2    # 图片张数上限（多图建议拆工序）
MIN_IMAGES           = 1    # 图片张数下限
MAX_PROCESSES        = 32   # 工序总数上限（流程图会自动分页）
PROCESSES_PER_FLOW_PAGE = 10  # 工艺流程图单页最多节点数（A3 纵向，留出超长工序名换行余量）

DATE_RE    = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
VERSION_RE = re.compile(r"^[A-Z]/\d+$")
MODEL_RE   = re.compile(r"^[A-Za-z0-9_-]+$")


class ValidationError(Exception):
    """校验失败异常。errors 为字符串列表（中文）。"""

    def __init__(self, errors: list[str], warnings: list[str] | None = None) -> None:
        self.errors = errors
        self.warnings = warnings or []
        super().__init__("\n".join(errors))


@dataclass
class ValidationResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def _cn_len(s: str) -> int:
    """汉字按 1 计、半角字符按 0.5 计的近似字符长度。"""
    n = 0.0
    for ch in s:
        if '一' <= ch <= '鿿' or ch in '，。；：、（）！？""''':
            n += 1
        else:
            n += 0.5
    return int(round(n))


def validate(data: dict[str, Any], yaml_path: Path | None = None) -> ValidationResult:
    """校验 YAML 字典。返回 ValidationResult。

    yaml_path 用于解析图片相对路径（assets/images/<model>/ 是否存在）。
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ===== product 段 =====
    if not isinstance(data, dict):
        errors.append("YAML 根必须是字典")
        return ValidationResult(errors, warnings)

    product = data.get("product")
    if not isinstance(product, dict):
        errors.append("缺少 product 段")
        return ValidationResult(errors, warnings)

    required = ["model", "name", "company", "doc_id", "version", "publish_date", "effective_date"]
    for k in required:
        if not product.get(k):
            errors.append(f"product.{k} 缺失或为空")

    model = product.get("model", "")
    if model and not MODEL_RE.match(model):
        errors.append(f"product.model 只能含字母数字/下划线/横线，得到 {model!r}")

    for k in ("publish_date", "effective_date"):
        v = product.get(k, "")
        if v and not DATE_RE.match(str(v)):
            errors.append(f"product.{k} 格式应为 YYYY-M-D，得到 {v!r}")

    version = product.get("version", "")
    if version and not VERSION_RE.match(version):
        warnings.append(f"product.version 建议形如 A/0、B/1，得到 {version!r}")

    # ===== processes 段 =====
    processes = data.get("processes")
    if not isinstance(processes, list) or not processes:
        errors.append("processes 必须是非空列表")
        return ValidationResult(errors, warnings)

    if len(processes) > MAX_PROCESSES:
        errors.append(f"processes 数量 {len(processes)} 超过上限 {MAX_PROCESSES}")

    img_root: Path | None = None
    if yaml_path and model:
        img_root = yaml_path.parent.parent / "assets" / "images" / model

    for i, proc in enumerate(processes, start=1):
        prefix = f"processes[{i}]({proc.get('name', '<无名>')})"

        if not isinstance(proc, dict):
            errors.append(f"{prefix} 必须是字典")
            continue

        pname = proc.get("name", "")
        if not pname:
            errors.append(f"{prefix}.name 缺失")

        ops = proc.get("operations") or []
        if not ops:
            errors.append(f"{prefix}.operations 不能为空")
        if len(ops) > MAX_OPS:
            errors.append(f"{prefix}.operations 条数 {len(ops)} 超过上限 {MAX_OPS}")
        elif len(ops) > OPS_PER_PAGE:
            n_pages = (len(ops) + OPS_PER_PAGE - 1) // OPS_PER_PAGE
            warnings.append(f"{prefix}.operations 条数 {len(ops)} 超过单页容量 {OPS_PER_PAGE}，将自动拆成 {n_pages} 页")

        notes = proc.get("notes") or []
        if len(notes) > MAX_NOTES:
            errors.append(f"{prefix}.notes 条数 {len(notes)} 超过上限 {MAX_NOTES}")

        for key, limit in (("tools", MAX_TOOLS), ("materials", MAX_MATS)):
            items = proc.get(key) or []
            if len(items) > limit:
                errors.append(f"{prefix}.{key} 项数 {len(items)} 超过上限 {limit}")

        images = proc.get("images") or []
        if len(images) > MAX_IMAGES:
            errors.append(
                f"{prefix}.images 张数 {len(images)} 超过上限 {MAX_IMAGES}；"
                "建议把当前工序拆成多道工序，每道 1-2 张图（多图会影响显示效果）"
            )
        elif len(images) < MIN_IMAGES:
            errors.append(f"{prefix}.images 至少需要 {MIN_IMAGES} 张")
        if img_root is not None:
            for img in images:
                if not (img_root / img).exists():
                    errors.append(f"{prefix} 图片不存在：{img_root / img}")

    return ValidationResult(errors, warnings)
