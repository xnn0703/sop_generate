"""当前用户名管理（v1.1.0 起强制必填）

保存到 app_dir/config/current_user.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import CONFIG_DIR

USER_FILE = CONFIG_DIR / "current_user.json"


def get_current_user() -> str:
    """返回当前用户名；未设置返回空串。"""
    if not USER_FILE.exists():
        return ""
    try:
        data = json.loads(USER_FILE.read_text(encoding="utf-8"))
        return (data.get("name") or "").strip()
    except (OSError, json.JSONDecodeError):
        return ""


def set_current_user(name: str) -> None:
    """设置当前用户名（空字符串会被拒绝）。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("用户名不能为空")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_FILE.write_text(
        json.dumps({"name": name}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_user_set() -> bool:
    return bool(get_current_user())
