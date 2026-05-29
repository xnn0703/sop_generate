"""小部件：列表编辑器（多行文本，每行一项，超长红字提示）"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QTextOption
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

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
        self.images: list[str] = []
        self._on_drop_callback = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        self.label = QLabel("图片（拖入文件；超过 4 张自动分页显示，每页 4 张 2×2）")
        self.label.setStyleSheet("font-weight: bold;")
        self.status = QLabel("0 张")
        self.status.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(self.label)
        header.addStretch()
        header.addWidget(self.status)
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

    def set_images(self, images: list[str]) -> None:
        self.images = list(images)
        self.edit.blockSignals(True)
        self.edit.setPlainText("\n".join(images))
        self.edit.blockSignals(False)
        self._refresh_status()

    def items(self) -> list[str]:
        return [
            line.strip()
            for line in self.edit.toPlainText().splitlines()
            if line.strip()
        ]

    def _on_text(self) -> None:
        self._refresh_status()
        self.changed.emit()

    def _refresh_status(self) -> None:
        n = len(self.items())
        pages = max(1, -(-n // 4)) if n else 0
        msg = f"{n} 张" + (f"（将分 {pages} 页）" if n > 4 else "")
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
                    if fname not in cur:
                        cur.append(fname)
                        self.set_images(cur)
        self.changed.emit()
        event.acceptProposedAction()
