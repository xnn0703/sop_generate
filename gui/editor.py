"""单个工序的编辑面板"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit, QScrollArea,
    QVBoxLayout, QWidget,
)

from gui.widgets import ImageListEditor, ListEditor


class ProcessEditor(QWidget):
    """编辑单个 process 字典。"""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._proc: dict[str, Any] | None = None
        self._product_dir_provider = None  # 提供当前 Product 的图片目录

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        v = QVBoxLayout(body)

        # 工序名 + 关键工序
        head = QGroupBox("工序")
        head_layout = QFormLayout(head)
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._mark_changed)
        head_layout.addRow("工序名", self.name_edit)
        self.key_check = QCheckBox("关键工序（★）")
        self.key_check.toggled.connect(self._mark_changed)
        head_layout.addRow("", self.key_check)
        v.addWidget(head)

        # 操作说明（超过 6 条自动拆页，最多 18 条）
        self.ops_editor = ListEditor(
            "操作说明（>6 条会自动拆页，建议拆成多工序更清晰）", max_items=18)
        self.ops_editor.changed.connect(self._mark_changed)
        v.addWidget(self.ops_editor)

        # 注意事项
        self.notes_editor = ListEditor("注意事项", max_items=4)
        self.notes_editor.changed.connect(self._mark_changed)
        v.addWidget(self.notes_editor)

        # 工具 + 材料
        tm = QHBoxLayout()
        self.tools_editor = ListEditor("工具设备", max_items=4)
        self.tools_editor.changed.connect(self._mark_changed)
        self.mats_editor = ListEditor("作业材料", max_items=4)
        self.mats_editor.changed.connect(self._mark_changed)
        tm.addWidget(self.tools_editor)
        tm.addWidget(self.mats_editor)
        v.addLayout(tm)

        # 图片
        self.img_editor = ImageListEditor()
        self.img_editor.changed.connect(self._mark_changed)
        v.addWidget(self.img_editor)

        # 修改追溯标签（底部）
        from PySide6.QtWidgets import QLabel
        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet("color: #888; font-size: 11px; padding-top: 6px;")
        v.addWidget(self._meta_label)

        v.addStretch()

    def set_product_image_dir_provider(self, fn) -> None:
        """fn() -> Path or None，提供当前产品的图片目录。"""
        self._product_dir_provider = fn

        def drop_cb(src: Path) -> str | None:
            from gui.model import Product  # noqa: F401
            # 调用方需保证 fn 返回的目录存在
            dst_dir = fn()
            if dst_dir is None:
                return None
            import shutil
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            if not dst.exists():
                shutil.copy2(src, dst)
            return src.name

        self.img_editor.set_drop_callback(drop_cb)

    def load(self, proc: dict[str, Any]) -> None:
        self._proc = proc
        self.name_edit.blockSignals(True); self.name_edit.setText(proc.get("name", "")); self.name_edit.blockSignals(False)
        self.key_check.blockSignals(True); self.key_check.setChecked(bool(proc.get("key", False))); self.key_check.blockSignals(False)
        self.ops_editor.set_items(proc.get("operations") or [])
        self.notes_editor.set_items(proc.get("notes") or [])
        self.tools_editor.set_items(proc.get("tools") or [])
        self.mats_editor.set_items(proc.get("materials") or [])
        self.img_editor.set_images(proc.get("images") or [])
        # 显示修改追溯
        meta = proc.get("_meta") or {}
        if hasattr(self, "_meta_label"):
            cby = meta.get("created_by", "—")
            cat = meta.get("created_at", "")[:16].replace("T", " ")
            mby = meta.get("last_modified_by", "—")
            mat = meta.get("last_modified_at", "")[:16].replace("T", " ")
            self._meta_label.setText(
                f"创建：{cby}  {cat}　│　最后修改：{mby}  {mat}"
            )

    def commit(self) -> None:
        """把编辑器内容写回 _proc 字典（in-place）。"""
        if self._proc is None:
            return
        self._proc["name"] = self.name_edit.text().strip()
        self._proc["key"] = self.key_check.isChecked()
        self._proc["operations"] = self.ops_editor.items()
        self._proc["notes"] = self.notes_editor.items()
        self._proc["tools"] = self.tools_editor.items()
        self._proc["materials"] = self.mats_editor.items()
        self._proc["images"] = self.img_editor.items()

    def _mark_changed(self) -> None:
        self.commit()
        self.changed.emit()


class ProductMetaEditor(QWidget):
    """编辑 product 元信息（封面用）。"""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._product: dict[str, Any] | None = None

        form = QFormLayout(self)
        self.fields: dict[str, QLineEdit] = {}
        for key, label in (
            ("model", "产品型号"),
            ("name", "产品名称"),
            ("company", "公司名"),
            ("doc_id", "文件编号"),
            ("version", "版本"),
            ("publish_date", "发布日期"),
            ("effective_date", "实施日期"),
        ):
            le = QLineEdit()
            le.textChanged.connect(self._on_changed)
            form.addRow(label, le)
            self.fields[key] = le

    def load(self, product: dict[str, Any]) -> None:
        self._product = product
        for k, le in self.fields.items():
            le.blockSignals(True)
            le.setText(str(product.get(k, "")))
            le.blockSignals(False)

    def commit(self) -> None:
        if self._product is None:
            return
        for k, le in self.fields.items():
            self._product[k] = le.text().strip()

    def _on_changed(self) -> None:
        self.commit()
        self.changed.emit()
