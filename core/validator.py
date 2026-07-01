"""YAML 字段校验

v1.1.0 起：移除所有数量/字符长度硬限制。
- 字段超出单页容量 → 自动分页（renderer 处理）
- 单元格 overflow:hidden 兜底
- 仅校验基础必填字段、格式、图片存在性
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .process_utils import image_file, process_has_own_content


# =============== 单页容量（用于自动分页计算）===============
OPS_PER_PAGE   = 6    # 操作说明 每页
NOTES_PER_PAGE = 4    # 注意事项 每页
TOOLS_PER_PAGE = 4    # 工具设备 每页
MATS_PER_PAGE  = 4    # 作业材料 每页
IMAGES_PER_PAGE = 4   # 图片 每页（4 张 2×2）
PROCESSES_PER_FLOW_PAGE = 8   # 工艺流程图 每页

DATE_RE    = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
VERSION_RE = re.compile(r"^[A-Z]/\d+$")
# 文件系统不允许的字符（用作文件夹/文件名时）
FS_FORBIDDEN = set('\\/:*?"<>|')


def _check_filename_safe(name: str) -> str | None:
    """检查字符串是否能安全用作文件夹/文件名。返回错误信息或 None。"""
    bad = sorted({c for c in name if c in FS_FORBIDDEN or ord(c) < 32})
    if bad:
        return f"含文件系统不允许的字符 {''.join(bad)!r}"
    if name.startswith(".") or name.endswith(".") or name.endswith(" "):
        return "不能以 . 开头或以 . / 空格结尾"
    if name.lower() in {"con","prn","aux","nul","com1","com2","com3","com4",
                        "com5","com6","com7","com8","com9","lpt1","lpt2",
                        "lpt3","lpt4","lpt5","lpt6","lpt7","lpt8","lpt9"}:
        return f"是 Windows 保留名，请换一个"
    return None


class ValidationError(Exception):
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


def validate(data: dict[str, Any], yaml_path: Path | None = None) -> ValidationResult:
    """校验 YAML 字典。仅校验基础必填、格式、图片存在性；不再硬限数量。"""
    errors: list[str] = []
    warnings: list[str] = []

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
    if model:
        err = _check_filename_safe(model)
        if err:
            errors.append(f"product.model {err}：{model!r}")

    for k in ("publish_date", "effective_date"):
        v = product.get(k, "")
        if v and not DATE_RE.match(str(v)):
            errors.append(f"product.{k} 格式应为 YYYY-M-D，得到 {v!r}")

    version = product.get("version", "")
    if version and not VERSION_RE.match(version):
        warnings.append(f"product.version 建议形如 A/0、B/1，得到 {version!r}")

    processes = data.get("processes")
    if not isinstance(processes, list) or not processes:
        errors.append("processes 必须是非空列表")
        return ValidationResult(errors, warnings)

    # 定位图片目录（v1.1.0 / v1.0.x 兼容）
    img_root: Path | None = None
    if yaml_path:
        if yaml_path.name == "product.yaml":
            img_root = yaml_path.parent / "images"
        elif yaml_path.parent.name == "products" and model:
            img_root = yaml_path.parent.parent / "assets" / "images" / model

    for i, proc in enumerate(processes, start=1):
        prefix = f"processes[{i}]({proc.get('name', '<无名>')})"
        if not isinstance(proc, dict):
            errors.append(f"{prefix} 必须是字典")
            continue
        if not proc.get("name"):
            errors.append(f"{prefix}.name 缺失")
        if not (proc.get("operations") or []):
            warnings.append(f"{prefix}.operations 为空，将按草稿占位导出")
        if not process_has_own_content(proc):
            warnings.append(f"{prefix} 内容全部为空，将按草稿占位导出")

        level = proc.get("level", 1)
        try:
            level_int = int(level)
        except (TypeError, ValueError):
            errors.append(f"{prefix}.level 应为 1、2、3，得到 {level!r}")
        else:
            if level_int not in (1, 2, 3):
                errors.append(f"{prefix}.level 应为 1、2、3，得到 {level!r}")

        work_time = proc.get("work_time_min")
        if work_time not in (None, ""):
            try:
                work_time_int = int(work_time)
            except (TypeError, ValueError):
                errors.append(f"{prefix}.work_time_min 应为分钟数字，得到 {work_time!r}")
            else:
                if work_time_int < 0:
                    errors.append(f"{prefix}.work_time_min 不能为负数，得到 {work_time!r}")

        images = proc.get("images") or []
        # 允许工序没有图片（v1.1.0 起去除"至少 1 张"的硬性要求）
        if not isinstance(images, list):
            errors.append(f"{prefix}.images 应为列表")
            images = []
        for img in images:
            fname = image_file(img)
            if isinstance(img, dict) and isinstance(img.get("layout"), dict):
                rotation = img["layout"].get("rotation", 0)
                try:
                    rotation_int = int(rotation)
                except (TypeError, ValueError):
                    errors.append(f"{prefix}.images.{fname or '<空>'}.layout.rotation 应为 0/90/180/270，得到 {rotation!r}")
                else:
                    if rotation_int % 360 not in (0, 90, 180, 270):
                        errors.append(f"{prefix}.images.{fname or '<空>'}.layout.rotation 应为 0/90/180/270，得到 {rotation!r}")
        if img_root is not None:
            for img in images:
                fname = image_file(img)
                if not fname:
                    errors.append(f"{prefix} 图片条目缺少 file：{img!r}")
                    continue
                if not (img_root / fname).exists():
                    errors.append(f"{prefix} 图片不存在：{img_root / fname}")

        # 容量超出提示（不是错误，渲染时会自动分页）
        for fname, limit, name in [
            ("operations", OPS_PER_PAGE,   "操作说明"),
            ("notes",      NOTES_PER_PAGE, "注意事项"),
            ("tools",      TOOLS_PER_PAGE, "工具设备"),
            ("materials",  MATS_PER_PAGE,  "作业材料"),
            ("images",     IMAGES_PER_PAGE, "图片"),
        ]:
            n = len(proc.get(fname) or [])
            if n > limit:
                pages = (n + limit - 1) // limit
                warnings.append(
                    f"{prefix}.{name} 共 {n} 条，超过单页 {limit}，将自动分 {pages} 页显示"
                )

    return ValidationResult(errors, warnings)
