"""v1.0.x → v1.1.0 数据迁移

旧结构：
    products/<model>.yaml + assets/images/<model>/*

新结构：
    sop_packages/<model>/{product.yaml, images/}

迁移完成后老目录改名为 _legacy_v1_backup/（保留 1 个月可回滚）。
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from core.paths import (
    LEGACY_BACKUP, LEGACY_IMAGES_DIR, LEGACY_PRODUCTS_DIR, SOP_PACKAGES_DIR,
    sop_package_dir,
)


LEGACY_RETENTION_DAYS = 30


def _next_backup_root() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = LEGACY_BACKUP / ts
    counter = 1
    while backup_root.exists():
        counter += 1
        backup_root = LEGACY_BACKUP / f"{ts}_{counter}"
    return backup_root


def migrate_legacy_data() -> dict:
    """把 v1.0.x 的 products/ 和 assets/images/ 合并到 sop_packages/。

    返回 {"migrated": [...], "skipped": [...], "backup_dir": str}
    """
    if not LEGACY_PRODUCTS_DIR.exists():
        return {"migrated": [], "skipped": [], "backup_dir": ""}

    SOP_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)

    migrated: list[str] = []
    skipped:  list[str] = []

    for yaml_file in sorted(LEGACY_PRODUCTS_DIR.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        model = yaml_file.stem
        pkg = sop_package_dir(model)
        if pkg.exists():
            skipped.append(model)
            continue

        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "images").mkdir(exist_ok=True)

        # 复制 YAML
        shutil.copy2(yaml_file, pkg / "product.yaml")

        # 复制图片
        old_imgs = LEGACY_IMAGES_DIR / model
        if old_imgs.is_dir():
            for img in sorted(old_imgs.iterdir()):
                if img.is_file():
                    shutil.copy2(img, pkg / "images" / img.name)

        migrated.append(model)

    # 把老目录搬到 _legacy_v1_backup/<timestamp>/。
    # 即使全部同名跳过，也要搬走旧目录，避免下次启动继续弹迁移提示。
    if migrated or skipped:
        backup_root = _next_backup_root()
        backup_root.mkdir(parents=True, exist_ok=True)
        if LEGACY_PRODUCTS_DIR.exists():
            shutil.move(str(LEGACY_PRODUCTS_DIR), str(backup_root / "products"))
        if LEGACY_IMAGES_DIR.exists():
            # 注意 assets/images 的父目录 assets 也搬走
            assets = LEGACY_IMAGES_DIR.parent
            if assets.exists():
                shutil.move(str(assets), str(backup_root / "assets"))
        # 加个标记文件
        (backup_root / "README.txt").write_text(
            f"v1.0.x 数据备份\n创建时间：{datetime.now().isoformat()}\n"
            f"保留期：{LEGACY_RETENTION_DAYS} 天，超期可手动删除整个 _legacy_v1_backup 目录\n",
            encoding="utf-8",
        )
        backup_str = str(backup_root)
    else:
        backup_str = ""

    return {"migrated": migrated, "skipped": skipped, "backup_dir": backup_str}


def cleanup_expired_legacy() -> list[str]:
    """删除超过 LEGACY_RETENTION_DAYS 天的备份子目录。"""
    if not LEGACY_BACKUP.exists():
        return []
    cutoff = datetime.now() - timedelta(days=LEGACY_RETENTION_DAYS)
    removed: list[str] = []
    for sub in LEGACY_BACKUP.iterdir():
        if not sub.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(sub.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            shutil.rmtree(sub, ignore_errors=True)
            removed.append(sub.name)
    return removed
