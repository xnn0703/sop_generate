"""小部件：列表编辑器、工序列表、图片列表。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPalette, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QMessageBox,
    QPushButton, QPlainTextEdit, QVBoxLayout, QWidget,
)

from core.process_utils import image_file


class ProcessListWidget(QListWidget):
    """支持父子工序块拖拽的列表。

    控件本身不直接改 model，避免 Qt 默认只移动单行；主窗口收到 blockDropped
    后按当前 processes 结构整体移动父级及其子级。
    """

    blockDropped = Signal(object, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._press_pos: QPoint | None = None
        self._drag_source_id: object | None = None
        self._dragging = False
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.NoDragDrop)

    def _target_row_from_pos(self, pos: QPoint) -> int:
        row = self.indexAt(pos).row()
        if row < 0:
            if self.count() == 0:
                return 0
            first_rect = self.visualItemRect(self.item(0))
            return 0 if pos.y() < first_rect.top() else self.count()

        rect = self.visualItemRect(self.item(row))
        if pos.y() > rect.center().y():
            row += 1
        return max(0, min(row, self.count()))

    def mousePressEvent(self, event) -> None:  # noqa: N802（Qt override）
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            self._press_pos = QPoint(event.pos())
            self._drag_source_id = item.data(Qt.UserRole) if item is not None else None
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802（Qt override）
        if (
            event.buttons() & Qt.LeftButton
            and self._press_pos is not None
            and self._drag_source_id is not None
        ):
            if (event.pos() - self._press_pos).manhattanLength() >= 6:
                self._dragging = True
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802（Qt override）
        source_id = self._drag_source_id
        dragging = self._dragging
        self._press_pos = None
        self._drag_source_id = None
        self._dragging = False

        if event.button() == Qt.LeftButton and dragging and source_id is not None:
            self.blockDropped.emit(source_id, self._target_row_from_pos(event.pos()))
            event.accept()
            return
        super().mouseReleaseEvent(event)

class ListEditor(QWidget):
    """每行一项的列表编辑器。无硬限，超出 per_page 时灰字提示会自动分页。"""

    changed = Signal()

    def __init__(self, title: str, max_items: int | None = None,
                 max_len_cn: int | None = None,   # 兼容旧调用，已不使用
                 per_page: int | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.per_page = per_page or max_items   # 把旧的 max_items 当作 per_page 显示

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: bold;")
        self.status = QLabel("")
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.label)
        header.addStretch()
        header.addWidget(self.status)
        layout.addLayout(header)

        self.edit = QPlainTextEdit()
        self.edit.setWordWrapMode(QTextOption.WordWrap)
        if self.per_page:
            self.edit.setPlaceholderText(f"每行一项；超过 {self.per_page} 条会自动分页显示")
        else:
            self.edit.setPlaceholderText("每行一项")
        self.edit.textChanged.connect(self._on_changed)
        layout.addWidget(self.edit)

    def set_items(self, items: list[str]) -> None:
        self.edit.blockSignals(True)
        self.edit.setPlainText("\n".join(items))
        self.edit.blockSignals(False)
        self._refresh_status()

    def items(self) -> list[str]:
        return [
            line.strip()
            for line in self.edit.toPlainText().splitlines()
            if line.strip()
        ]

    def _on_changed(self) -> None:
        self._refresh_status()
        self.changed.emit()

    def _refresh_status(self) -> None:
        n = len(self.items())
        if self.per_page:
            pages = max(1, -(-n // self.per_page)) if n else 0
            msg = f"{n} 项"
            if n > self.per_page:
                msg += f"（将分 {pages} 页）"
            self.status.setStyleSheet("color: #888; font-size: 11px;")
            self.status.setText(msg)
        else:
            self.status.setText(f"{n} 项")


class ImageListEditor(QWidget):
    """图片列表编辑器：拖入图片自动复制到产品目录。"""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.images: list[Any] = []
        self._on_drop_callback = None
        self._image_dir_provider = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.label = QLabel("图片（拖入文件；超过 4 张自动分页显示，每页 4 张 2×2）")
        self.label.setStyleSheet("font-weight: bold;")
        self.status = QLabel("0 张")
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        self.layout_btn = QPushButton("编辑布局")
        self.layout_btn.clicked.connect(self._edit_layout)
        header.addWidget(self.label)
        header.addStretch()
        header.addWidget(self.status)
        header.addWidget(self.layout_btn)
        layout.addLayout(header)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("每行一个图片文件名（位于 assets/images/<MODEL>/）")
        self.edit.setAcceptDrops(True)
        self.edit.textChanged.connect(self._on_text)
        self.edit.dragEnterEvent = self._drag_enter   # type: ignore
        self.edit.dropEvent = self._drop_event        # type: ignore
        layout.addWidget(self.edit)

    def set_drop_callback(self, cb) -> None:
        """cb(src_path: Path) -> str(filename in product image dir)"""
        self._on_drop_callback = cb

    def set_image_dir_provider(self, cb) -> None:
        """cb() -> Path or None"""
        self._image_dir_provider = cb

    def set_images(self, images: list[Any]) -> None:
        self.images = list(images)
        self.edit.blockSignals(True)
        self.edit.setPlainText("\n".join(image_file(img) for img in images if image_file(img)))
        self.edit.blockSignals(False)
        self._refresh_status()

    def items(self) -> list[Any]:
        existing = {image_file(img): img for img in self.images if image_file(img)}
        out: list[Any] = []
        for line in self.edit.toPlainText().splitlines():
            fname = line.strip()
            if not fname:
                continue
            out.append(existing.get(fname, fname))
        return out

    def _on_text(self) -> None:
        self._refresh_status()
        self.changed.emit()

    def _refresh_status(self) -> None:
        n = len(self.items())
        pages = max(1, -(-n // 4)) if n else 0
        msg = f"{n} 张" + (f"（将分 {pages} 页）" if n > 4 else "")
        if any(isinstance(img, dict) and img.get("layout") for img in self.items()):
            msg += " · 手动布局"
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        self.status.setText(msg)

    def _drag_enter(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event) -> None:
        from pathlib import Path
        if not event.mimeData().hasUrls():
            return
        if not self._on_drop_callback:
            return
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                fname = self._on_drop_callback(p)
                if fname:
                    cur = self.items()
                    if fname not in [image_file(img) for img in cur]:
                        cur.append(fname)
                        self.set_images(cur)
        self.changed.emit()
        event.acceptProposedAction()

    def _edit_layout(self) -> None:
        images = self.items()
        if not images:
            QMessageBox.information(self, "暂无图片", "请先拖入或填写图片文件名，再编辑图片布局。")
            return
        if not self._image_dir_provider:
            return
        img_dir = self._image_dir_provider()
        if img_dir is None:
            return
        from gui.image_layout import ImageLayoutDialog

        dlg = ImageLayoutDialog(images, Path(img_dir), self)
        if dlg.exec():
            self.set_images(dlg.result_images())
            self.changed.emit()
