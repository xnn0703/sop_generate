"""工序层级、编号、工时和图片条目的通用处理。"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


MAX_PROCESS_LEVEL = 3


def normalize_level(value: Any, previous_level: int = 1, first: bool = False) -> int:
    """把 level 规范到 1..3，并避免从 1 直接跳到 3。"""
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = 1
    level = max(1, min(MAX_PROCESS_LEVEL, level))
    if first:
        return 1
    return min(level, previous_level + 1)


def image_file(entry: Any) -> str:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("file") or entry.get("name") or "")
    return ""


def _clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        out = default
    return max(minimum, min(maximum, out))


def normalize_rotation(value: Any) -> int:
    try:
        rotation = int(value)
    except (TypeError, ValueError):
        rotation = 0
    rotation = rotation % 360
    if rotation not in (0, 90, 180, 270):
        # 手写 YAML 出现非 90 度倍数时，落到最近的 90 度，避免渲染裁切。
        rotation = round(rotation / 90) * 90 % 360
    return rotation


def normalize_layout(layout: Any) -> dict[str, float | int] | None:
    if not isinstance(layout, dict):
        return None
    w = _clamp_float(layout.get("w"), 100.0, 5.0, 100.0)
    h = _clamp_float(layout.get("h"), 100.0, 5.0, 100.0)
    x = _clamp_float(layout.get("x"), 0.0, 0.0, 100.0 - w)
    y = _clamp_float(layout.get("y"), 0.0, 0.0, 100.0 - h)
    return {
        "x": round(x, 3),
        "y": round(y, 3),
        "w": round(w, 3),
        "h": round(h, 3),
        "rotation": normalize_rotation(layout.get("rotation")),
    }


def normalize_image_entry(entry: Any) -> dict[str, Any]:
    file = image_file(entry)
    layout = normalize_layout(entry.get("layout")) if isinstance(entry, dict) else None
    out: dict[str, Any] = {"file": file}
    if layout:
        out["layout"] = layout
    return out


def normalize_images(images: Any) -> list[dict[str, Any]]:
    if not isinstance(images, list):
        return []
    return [img for img in (normalize_image_entry(entry) for entry in images) if img["file"]]


def auto_image_layouts(count: int) -> list[dict[str, float]]:
    """返回图片画布内的默认百分比布局。"""
    if count <= 1:
        return [{"x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0, "rotation": 0}]
    if count == 2:
        return [
            {"x": 0.0, "y": 0.0, "w": 100.0, "h": 49.0, "rotation": 0},
            {"x": 0.0, "y": 51.0, "w": 100.0, "h": 49.0, "rotation": 0},
        ]
    return [
        {"x": 0.0, "y": 0.0, "w": 49.0, "h": 49.0, "rotation": 0},
        {"x": 51.0, "y": 0.0, "w": 49.0, "h": 49.0, "rotation": 0},
        {"x": 0.0, "y": 51.0, "w": 49.0, "h": 49.0, "rotation": 0},
        {"x": 51.0, "y": 51.0, "w": 49.0, "h": 49.0, "rotation": 0},
    ][:count]


def apply_default_image_layouts(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defaults = auto_image_layouts(len(images))
    out: list[dict[str, Any]] = []
    for idx, img in enumerate(images):
        item = deepcopy(img)
        item["_layout"] = normalize_layout(item.get("layout")) or defaults[min(idx, len(defaults) - 1)]
        out.append(item)
    return out


def has_manual_image_layout(images: list[dict[str, Any]]) -> bool:
    return any(normalize_layout(img.get("layout")) for img in images)


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(str(item).strip() for item in value if not isinstance(item, dict))


def process_has_own_content(proc: dict[str, Any]) -> bool:
    if _non_empty_list(proc.get("operations")):
        return True
    if _non_empty_list(proc.get("notes")):
        return True
    if _non_empty_list(proc.get("tools")):
        return True
    if _non_empty_list(proc.get("materials")):
        return True
    return bool(normalize_images(proc.get("images")))


def format_work_time(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return "—"
    if minutes < 0:
        return "—"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h{mins}min"
    if hours:
        return f"{hours}h"
    return f"{mins}min"


def get_process_level(proc: dict[str, Any]) -> int:
    try:
        return int(proc.get("level", 1))
    except (TypeError, ValueError):
        return 1


def normalize_process_sequence(processes: list[dict[str, Any]]) -> None:
    """原地规范工序 level，避免旧数据或手写 YAML 跳级。"""
    previous = 1
    for idx, proc in enumerate(processes):
        level = normalize_level(proc.get("level", 1), previous, first=idx == 0)
        proc["level"] = level
        previous = level


def annotate_processes(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回带 _proc_number/_level/_has_children 等渲染字段的工序副本。"""
    counters = [0, 0, 0]
    previous = 1
    out: list[dict[str, Any]] = []
    for idx, proc in enumerate(processes):
        level = normalize_level(proc.get("level", 1), previous, first=idx == 0)
        previous = level
        counters[level - 1] += 1
        for i in range(level, MAX_PROCESS_LEVEL):
            counters[i] = 0
        number = "-".join(str(n) for n in counters[:level] if n)
        item = {**proc, "level": level}
        item["_level"] = level
        item["_proc_number"] = number
        item["_work_time_text"] = format_work_time(proc.get("work_time_min"))
        item["_has_own_content"] = process_has_own_content(proc)
        item["_images_normalized"] = normalize_images(proc.get("images"))
        out.append(item)

    for i, proc in enumerate(out):
        level = proc["_level"]
        proc["_has_children"] = i + 1 < len(out) and out[i + 1]["_level"] > level
        descendants: list[dict[str, Any]] = []
        j = i + 1
        while j < len(out) and out[j]["_level"] > level:
            descendants.append(out[j])
            j += 1
        proc["_descendants"] = descendants
        proc["_summary_only"] = bool(proc["_has_children"] and not proc["_has_own_content"])
    return out


def descendant_end(processes: list[dict[str, Any]], row: int) -> int:
    """返回 row 对应工序块的右开结束位置。"""
    if row < 0 or row >= len(processes):
        return row
    level = get_process_level(processes[row])
    end = row + 1
    while end < len(processes) and get_process_level(processes[end]) > level:
        end += 1
    return end
