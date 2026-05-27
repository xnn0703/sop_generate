"""小部件：列表编辑器（多行文本，每行一项，超长红字提示）"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette, QTextOption
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from core.validator import _cn_len


class ListEditor(QWidget):
    """每行一项的列表编辑器。超长/超数量在标签上红字提示。"""

    changed = Signal()

    def __init__(self, title: str, max_items: int, max_len_cn: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.max_items = max_items
        self.max_len_cn = max_len_cn

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
        self.edit.setPlaceholderText(f"每行一项，最多 {max_items} 项，单项 ≤ {max_len_cn} 汉字")
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
        items = self.items()
        n = len(items)
        bad: list[str] = []
        if n > self.max_items:
            bad.append(f"{n}/{self.max_items} 项 超")
        else:
            bad.append(f"{n}/{self.max_items} 项")
        long_items = [i for i, it in enumerate(items, start=1) if _cn_len(it) > self.max_len_cn]
        if long_items:
            bad.append(f"第 {','.join(map(str, long_items))} 项超长")

        msg = "  ".join(bad)
        is_error = (n > self.max_items) or bool(long_items)
        color = "#c00" if is_error else "#888"
        self.status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status.setText(msg)


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
        self.label = QLabel("图片（拖入文件或点击下方编辑文件名）")
        self.label.setStyleSheet("font-weight: bold;")
        self.status = QLabel("0/2 张")
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
        color = "#888" if 1 <= n <= 2 else "#c00"
        self.status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status.setText(f"{n}/2 张")

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
