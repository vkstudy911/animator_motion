"""Canvas format, aspect ratio presets, and image resizing engine."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter


class ResizeMode(Enum):
    SCALE = "scale"
    CROP = "crop"
    PAD = "pad"


@dataclass(frozen=True)
class CanvasPreset:
    name: str
    category: str
    ratio: str
    width: int
    height: int
    orientation: str  # "landscape", "portrait", "square"

    @property
    def dimensions_str(self) -> str:
        return f"{self.width}×{self.height}"


CANVAS_PRESETS: List[CanvasPreset] = [
    # Landscape
    CanvasPreset("16:9 (1280×720)", "Landscape", "16:9", 1280, 720, "landscape"),
    CanvasPreset("16:9 (1920×1080)", "Landscape", "16:9", 1920, 1080, "landscape"),
    CanvasPreset("4:3 (1024×768)", "Landscape", "4:3", 1024, 768, "landscape"),
    CanvasPreset("4:3 (1440×1080)", "Landscape", "4:3", 1440, 1080, "landscape"),
    CanvasPreset("3:2 (1800×1200)", "Landscape", "3:2", 1800, 1200, "landscape"),
    # Portrait
    CanvasPreset("9:16 (720×1280)", "Portrait", "9:16", 720, 1280, "portrait"),
    CanvasPreset("9:16 (1080×1920)", "Portrait", "9:16", 1080, 1920, "portrait"),
    CanvasPreset("4:5 (1080×1350)", "Portrait", "4:5", 1080, 1350, "portrait"),
    CanvasPreset("3:4 (1080×1440)", "Portrait", "3:4", 1080, 1440, "portrait"),
    # Square
    CanvasPreset("1:1 (1080×1080)", "Square", "1:1", 1080, 1080, "square"),
    CanvasPreset("1:1 (1024×1024)", "Square", "1:1", 1024, 1024, "square"),
    # Social
    CanvasPreset("YouTube (1920×1080)", "Social", "16:9", 1920, 1080, "landscape"),
    CanvasPreset("Instagram Post (1080×1080)", "Social", "1:1", 1080, 1080, "square"),
    CanvasPreset("Instagram Portrait (1080×1350)", "Social", "4:5", 1080, 1350, "portrait"),
    CanvasPreset("Instagram Story / Reels (1080×1920)", "Social", "9:16", 1080, 1920, "portrait"),
    CanvasPreset("TikTok (1080×1920)", "Social", "9:16", 1080, 1920, "portrait"),
    CanvasPreset("YouTube Shorts (1080×1920)", "Social", "9:16", 1080, 1920, "portrait"),
    # Other
    CanvasPreset("A4 Landscape (1754×1240)", "Other", "A4", 1754, 1240, "landscape"),
    CanvasPreset("A4 Portrait (1240×1754)", "Other", "A4", 1240, 1754, "portrait"),
]


def get_orientation(width: int, height: int) -> str:
    if width > height:
        return "landscape"
    elif height > width:
        return "portrait"
    return "square"


def get_ratio_label(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "Custom"

    # Known common standard ratios
    ratio = width / height
    if math.isclose(ratio, 16 / 9, rel_tol=0.01):
        return "16:9"
    if math.isclose(ratio, 9 / 16, rel_tol=0.01):
        return "9:16"
    if math.isclose(ratio, 1.0, rel_tol=0.01):
        return "1:1"
    if math.isclose(ratio, 4 / 3, rel_tol=0.01):
        return "4:3"
    if math.isclose(ratio, 3 / 4, rel_tol=0.01):
        return "3:4"
    if math.isclose(ratio, 3 / 2, rel_tol=0.01):
        return "3:2"
    if math.isclose(ratio, 2 / 3, rel_tol=0.01):
        return "2:3"
    if math.isclose(ratio, 4 / 5, rel_tol=0.01):
        return "4:5"
    if (width, height) in ((1754, 1240), (1240, 1754)):
        return "A4"

    # Simplified integer GCD
    g = math.gcd(width, height)
    gw = width // g
    gh = height // g
    if gw <= 16 and gh <= 16:
        return f"{gw}:{gh}"

    return f"{width}×{height}"


def resize_image(image: QImage, new_w: int, new_h: int, mode: ResizeMode) -> QImage:
    """Resize image buffer according to specified mode (SCALE, CROP, or PAD)."""
    if image.isNull() or image.width() == 0 or image.height() == 0:
        res = QImage(new_w, new_h, QImage.Format.Format_ARGB32_Premultiplied)
        res.fill(Qt.GlobalColor.transparent)
        return res

    old_w = image.width()
    old_h = image.height()

    if old_w == new_w and old_h == new_h:
        return image.copy()

    dest = QImage(new_w, new_h, QImage.Format.Format_ARGB32_Premultiplied)
    dest.fill(Qt.GlobalColor.transparent)
    painter = QPainter(dest)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    if mode == ResizeMode.SCALE:
        # Scale to fit inside new dimensions while strictly preserving aspect ratio, centered
        scaled = image.scaled(
            new_w,
            new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (new_w - scaled.width()) // 2
        y = (new_h - scaled.height()) // 2
        painter.drawImage(x, y, scaled)

    elif mode == ResizeMode.CROP:
        # Center original image at 1:1 scale; excess is cropped
        x = (new_w - old_w) // 2
        y = (new_h - old_h) // 2
        painter.drawImage(x, y, image)

    elif mode == ResizeMode.PAD:
        # Keep original image centered with blank/transparent padding
        x = (new_w - old_w) // 2
        y = (new_h - old_h) // 2
        painter.drawImage(x, y, image)

    painter.end()
    return dest
