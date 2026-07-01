"""图片布局编辑器：在固定图片画布内拖拽/缩放图片。"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGraphicsItem, QGraphicsPixmapItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from core.process_utils import apply_default_image_layouts, normalize_images


CANVAS_W = 1000.0
CANVAS_H = 850.0
MIN_BOX = 60.0


def _pct_to_rect(layout: dict[str, float | int]) -> QRectF:
    return QRectF(
        layout["x"] / 100.0 * CANVAS_W,
        layout["y"] / 100.0 * CANVAS_H,
        layout["w"] / 100.0 * CANVAS_W,
        layout["h"] / 100.0 * CANVAS_H,
    )


def _rect_to_pct(rect: QRectF, rotation: int) -> dict[str, float | int]:
    return {
        "x": round(rect.x() / CANVAS_W * 100.0, 3),
        "y": round(rect.y() / CANVAS_H * 100.0, 3),
        "w": round(rect.width() / CANVAS_W * 100.0, 3),
        "h": round(rect.height() / CANVAS_H * 100.0, 3),
        "rotation": rotation % 360,
    }


def _rotated_aspect(pixmap: QPixmap, rotation: int) -> float:
    if pixmap.isNull():
        return 1.0
    width = pixmap.width()
    height = pixmap.height()
    if rotation % 180:
        width, height = height, width
    if height <= 0:
        return 1.0
    return max(0.05, width / height)


def _fit_rect_to_aspect(rect: QRectF, aspect: float) -> QRectF:
    """把布局框收缩成图片真实可见框，避免编辑器里出现一圈空白外框。"""
    if rect.width() <= 0 or rect.height() <= 0:
        rect = QRectF(0, 0, CANVAS_W, CANVAS_H)

    box_aspect = rect.width() / rect.height()
    if box_aspect > aspect:
        width = rect.height() * aspect
        height = rect.height()
        x = rect.x() + (rect.width() - width) / 2
        y = rect.y()
    else:
        width = rect.width()
        height = rect.width() / aspect
        x = rect.x()
        y = rect.y() + (rect.height() - height) / 2

    min_scale = max(MIN_BOX / max(width, 1.0), MIN_BOX / max(height, 1.0), 1.0)
    width *= min_scale
    height *= min_scale
    if width > CANVAS_W or height > CANVAS_H:
        scale = min(CANVAS_W / width, CANVAS_H / height)
        width *= scale
        height *= scale

    x = max(0.0, min(CANVAS_W - width, x))
    y = max(0.0, min(CANVAS_H - height, y))
    return QRectF(x, y, width, height)


class ImageBoxItem(QGraphicsRectItem):
    """可拖拽、右下角可等比缩放、可 90 度旋转的图片。"""

    def __init__(self, file: str, pixmap: QPixmap, rect: QRectF, rotation: int = 0) -> None:
        super().__init__(0, 0, rect.width(), rect.height())
        self.file = file
        self.rotation_degrees = rotation % 360
        self._resizing = False
        self._hovered = False
        self._resize_start_rect = QRectF()
        self._resize_start_scene_pos = QPointF()
        self._original_pixmap = pixmap
        self._pix = QGraphicsPixmapItem(self)
        self._handle = QGraphicsRectItem(self)
        self.setPos(rect.x(), rect.y())
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setBrush(QBrush(Qt.NoBrush))
        self.setCursor(Qt.OpenHandCursor)
        self._pix.setTransformationMode(Qt.SmoothTransformation)
        self._sync_visual()

    def _active(self) -> bool:
        return self.isSelected() or self._hovered or self._resizing

    def _rotated_pixmap(self) -> QPixmap:
        if self.rotation_degrees == 0 or self._original_pixmap.isNull():
            return self._original_pixmap
        return self._original_pixmap.transformed(
            QTransform().rotate(self.rotation_degrees),
            Qt.SmoothTransformation,
        )

    def _sync_visual(self, transform_mode: Qt.TransformationMode = Qt.SmoothTransformation) -> None:
        rect = self.rect()
        active = self._active()
        self.setPen(QPen(QColor("#1f6feb"), 2) if active else QPen(Qt.NoPen))
        pix = self._rotated_pixmap()
        if not pix.isNull():
            scaled = pix.scaled(
                max(1, int(rect.width())),
                max(1, int(rect.height())),
                Qt.KeepAspectRatio,
                transform_mode,
            )
            self._pix.setPixmap(scaled)
            self._pix.setPos(
                (rect.width() - scaled.width()) / 2,
                (rect.height() - scaled.height()) / 2,
            )
        size = 18
        self._handle.setRect(rect.width() - size, rect.height() - size, size, size)
        self._handle.setBrush(QBrush(QColor("#1f6feb")))
        self._handle.setPen(QPen(QColor("#fff"), 1))
        self._handle.setVisible(active)

    def _scale_to(self, scale: float) -> None:
        start = self._resize_start_rect if self._resizing else self.rect()
        min_scale = max(MIN_BOX / max(start.width(), 1.0), MIN_BOX / max(start.height(), 1.0))
        max_scale = min(
            (CANVAS_W - self.pos().x()) / max(start.width(), 1.0),
            (CANVAS_H - self.pos().y()) / max(start.height(), 1.0),
        )
        scale = max(min_scale, min(max_scale, scale))
        self.setRect(0, 0, start.width() * scale, start.height() * scale)

    def _clamp_position(self) -> None:
        rect = self.rect()
        x = max(0.0, min(CANVAS_W - rect.width(), self.pos().x()))
        y = max(0.0, min(CANVAS_H - rect.height(), self.pos().y()))
        self.setPos(x, y)

    def rotate_by(self, delta: int) -> None:
        center = self.sceneBoundingRect().center()
        self.rotation_degrees = (self.rotation_degrees + delta) % 360
        aspect = _rotated_aspect(self._original_pixmap, self.rotation_degrees)
        area = max(MIN_BOX * MIN_BOX, self.rect().width() * self.rect().height())
        width = math.sqrt(area * aspect)
        height = width / aspect
        if width > CANVAS_W or height > CANVAS_H:
            scale = min(CANVAS_W / width, CANVAS_H / height)
            width *= scale
            height *= scale
        width = max(MIN_BOX, min(CANVAS_W, width))
        height = max(MIN_BOX, min(CANVAS_H, height))
        self.setRect(0, 0, width, height)
        self.setPos(center.x() - width / 2, center.y() - height / 2)
        self._clamp_position()
        self._sync_visual()

    def itemChange(self, change, value):  # noqa: N802（Qt override）
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            pos = QPointF(value)
            rect = self.rect()
            x = max(0.0, min(CANVAS_W - rect.width(), pos.x()))
            y = max(0.0, min(CANVAS_H - rect.height(), pos.y()))
            return QPointF(x, y)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self._sync_visual()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self._sync_visual()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event) -> None:  # noqa: N802
        rect = self.rect()
        if event.pos().x() >= rect.width() - 24 and event.pos().y() >= rect.height() - 24:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.OpenHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.setCursor(Qt.OpenHandCursor)
        self._sync_visual()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        rect = self.rect()
        if event.pos().x() >= rect.width() - 24 and event.pos().y() >= rect.height() - 24:
            self._resizing = True
            self._resize_start_rect = QRectF(rect)
            self._resize_start_scene_pos = event.scenePos()
            self.setSelected(True)
            event.accept()
            return
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            delta = event.scenePos() - self._resize_start_scene_pos
            start = self._resize_start_rect
            scale = max(
                (start.width() + delta.x()) / max(start.width(), 1.0),
                (start.height() + delta.y()) / max(start.height(), 1.0),
            )
            self._scale_to(scale)
            self._sync_visual(Qt.FastTransformation)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._resizing = False
        self.setCursor(Qt.OpenHandCursor)
        self._sync_visual()
        super().mouseReleaseEvent(event)

    def layout_percent(self) -> dict[str, float | int]:
        r = QRectF(self.pos().x(), self.pos().y(), self.rect().width(), self.rect().height())
        return _rect_to_pct(r, self.rotation_degrees)


class ImageLayoutDialog(QDialog):
    """编辑当前工序图片布局。"""

    def __init__(self, images: list[Any], image_dir: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("图片布局编辑")
        self.resize(980, 820)
        self._image_dir = image_dir
        self._source_images = normalize_images(images)
        self._items: list[ImageBoxItem] = []
        self._clear_layout = False

        layout = QVBoxLayout(self)
        hint = QLabel("拖动图片调整位置；拖动右下角蓝色方块等比缩放；可左转/右转 90°。图片不能超出画布。")
        hint.setStyleSheet("color:#555;")
        layout.addWidget(hint)

        self.scene = QGraphicsScene(0, 0, CANVAS_W, CANVAS_H, self)
        self.scene.setBackgroundBrush(QBrush(QColor("#f8fafc")))
        border = self.scene.addRect(0, 0, CANVAS_W, CANVAS_H, QPen(QColor("#111"), 2))
        border.setZValue(-10)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        layout.addWidget(self.view, 1)

        btns = QHBoxLayout()
        auto_btn = QPushButton("自动排布")
        auto_btn.clicked.connect(self.reset_auto)
        clear_btn = QPushButton("清除手动布局")
        clear_btn.clicked.connect(self.clear_layouts)
        rotate_left_btn = QPushButton("左转 90°")
        rotate_left_btn.clicked.connect(lambda: self.rotate_selected(-90))
        rotate_right_btn = QPushButton("右转 90°")
        rotate_right_btn.clicked.connect(lambda: self.rotate_selected(90))
        btns.addWidget(auto_btn)
        btns.addWidget(clear_btn)
        btns.addWidget(rotate_left_btn)
        btns.addWidget(rotate_right_btn)
        btns.addStretch()
        layout.addLayout(btns)

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        self._load_items(self._source_images)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _pixmap_for(self, file: str) -> QPixmap:
        path = self._image_dir / file
        pix = QPixmap(str(path))
        if not pix.isNull():
            return pix
        pix = QPixmap(280, 180)
        pix.fill(QColor("#e5e7eb"))
        return pix

    def _load_items(self, images: list[dict[str, Any]]) -> None:
        for item in self._items:
            self.scene.removeItem(item)
        self._items.clear()
        for img in apply_default_image_layouts(images):
            pixmap = self._pixmap_for(img["file"])
            rotation = int(img["_layout"].get("rotation", 0) or 0)
            rect = _fit_rect_to_aspect(_pct_to_rect(img["_layout"]), _rotated_aspect(pixmap, rotation))
            item = ImageBoxItem(img["file"], pixmap, rect, rotation)
            self.scene.addItem(item)
            self._items.append(item)
        if self._items:
            self._items[0].setSelected(True)

    def reset_auto(self, keep_clear_flag: bool = False) -> None:
        images = [{"file": img["file"]} for img in self._source_images]
        if not keep_clear_flag:
            self._clear_layout = False
        self._load_items(images)

    def clear_layouts(self) -> None:
        self._clear_layout = True
        self.reset_auto(keep_clear_flag=True)
        QMessageBox.information(self, "已清除", "点击确定后，将清除当前工序图片的手动布局。")

    def rotate_selected(self, delta: int) -> None:
        selected = [item for item in self._items if item.isSelected()]
        if not selected and self._items:
            selected = [self._items[0]]
            selected[0].setSelected(True)
        for item in selected:
            item.rotate_by(delta)
        self._clear_layout = False

    def result_images(self) -> list[Any]:
        if self._clear_layout:
            return [item.file for item in self._items]
        return [
            {"file": item.file, "layout": item.layout_percent()}
            for item in self._items
        ]
