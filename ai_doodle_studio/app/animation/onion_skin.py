"""Onion skinning renderer for AI Doodle Studio.

Provides customizable ghost frame rendering for preceding and succeeding frames
with configurable alpha opacity, frame distances, and color tinting.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from app.core.frame import Frame


class OnionSkinRenderer:
    """Renders tinted preceding and following animation frames behind current frame."""

    def __init__(
        self,
        enabled: bool = False,
        frames_before: int = 2,
        frames_after: int = 1,
        before_opacity: float = 0.35,
        after_opacity: float = 0.25,
        before_color: Optional[QColor] = None,
        after_color: Optional[QColor] = None,
    ) -> None:
        self.enabled: bool = enabled
        self.frames_before: int = max(0, min(5, frames_before))
        self.frames_after: int = max(0, min(5, frames_after))
        self.before_opacity: float = max(0.05, min(1.0, before_opacity))
        self.after_opacity: float = max(0.05, min(1.0, after_opacity))

        # Distinct colors for past (red/orange) and future (green/cyan) frames
        self.before_color: QColor = before_color or QColor(235, 75, 75)
        self.after_color: QColor = after_color or QColor(75, 200, 100)

    def toggle(self) -> bool:
        """Toggle onion skin visibility."""
        self.enabled = not self.enabled
        return self.enabled

    def apply_settings(self, settings: dict) -> None:
        """Apply a settings dictionary to this renderer."""
        if "enabled" in settings:
            self.enabled = bool(settings["enabled"])
        if "frames_before" in settings:
            self.frames_before = max(0, min(5, int(settings["frames_before"])))
        if "frames_after" in settings:
            self.frames_after = max(0, min(5, int(settings["frames_after"])))
        if "opacity" in settings:
            op = max(0.05, min(1.0, float(settings["opacity"])))
            self.before_opacity = op
            self.after_opacity = op
        if "tint_before" in settings:
            val = settings["tint_before"]
            c = QColor(val) if not isinstance(val, QColor) else val
            if c.isValid():
                self.before_color = c
        if "tint_after" in settings:
            val = settings["tint_after"]
            c = QColor(val) if not isinstance(val, QColor) else val
            if c.isValid():
                self.after_color = c

    def render_onion_skin(
        self,
        painter: QPainter,
        current_index: int,
        frames: List[Frame],
        dest_rect: QRectF,
    ) -> None:
        """Composite preceding and succeeding frames onto canvas destination rect."""
        if not self.enabled or not frames or len(frames) <= 1:
            return

        total = len(frames)

        # 1. Render preceding frames (oldest to newest before current)
        for step in range(self.frames_before, 0, -1):
            idx = current_index - step
            if 0 <= idx < total:
                # Fade opacity the further away the frame is
                decay = 1.0 - ((step - 1) / max(1, self.frames_before)) * 0.5
                opacity = self.before_opacity * decay
                frame_img = (
                    frames[idx].get_foreground_composite()
                    if hasattr(frames[idx], "get_foreground_composite")
                    else frames[idx].get_image()
                )
                self._draw_tinted_frame(
                    painter=painter,
                    frame_image=frame_img,
                    tint_color=self.before_color,
                    opacity=opacity,
                    dest_rect=dest_rect,
                )

        # 2. Render succeeding frames (furthest to nearest after current)
        for step in range(self.frames_after, 0, -1):
            idx = current_index + step
            if 0 <= idx < total:
                decay = 1.0 - ((step - 1) / max(1, self.frames_after)) * 0.5
                opacity = self.after_opacity * decay
                frame_img = (
                    frames[idx].get_foreground_composite()
                    if hasattr(frames[idx], "get_foreground_composite")
                    else frames[idx].get_image()
                )
                self._draw_tinted_frame(
                    painter=painter,
                    frame_image=frame_img,
                    tint_color=self.after_color,
                    opacity=opacity,
                    dest_rect=dest_rect,
                )

    def _draw_tinted_frame(
        self,
        painter: QPainter,
        frame_image: QImage,
        tint_color: QColor,
        opacity: float,
        dest_rect: QRectF,
    ) -> None:
        """Render a single frame tinted with the designated color and opacity."""
        if frame_image.isNull() or opacity <= 0.0:
            return

        # Prepare tinted copy
        tinted = QImage(frame_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        tinted.fill(Qt.GlobalColor.transparent)

        tp = QPainter(tinted)
        tp.drawImage(0, 0, frame_image)
        tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        tp.fillRect(tinted.rect(), tint_color)
        tp.end()

        painter.save()
        painter.setOpacity(opacity)
        painter.drawImage(dest_rect, tinted)
        painter.restore()
