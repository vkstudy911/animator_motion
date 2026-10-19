"""Timeline widget for AI Doodle Studio.

A modern, compact, professional animation timeline strip inspired by sleek
mobile and desktop animation software:
- Dark navy surface with subtle blue border glow.
- Compact playback transport row at top-left.
- Quick frame actions and frame info badge.
- Right-side compact utility icons (Onion, Audio, Settings, Overflow menu).
- Horizontally scrollable frame strip with rounded thumbnail cards.
- Selected frame with bright magenta outline (#ec4899) and pill badge.
- Trailing '+ Add Frame' card with dashed border.
- Collapsible secondary settings bar (FPS, loop, onion, reorder).
- Minimizable audio track hidden by default when no audio is loaded.
"""

import os
import struct
import wave
from typing import List, Optional

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_CONTAINER,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_BORDER,
    COLOR_BORDER_SUBTLE,
    COLOR_GLASS_BG,
    COLOR_GLASS_BORDER,
    COLOR_PANEL_BG,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    THEME_GLASS_BG_BOTTOM,
    THEME_GLASS_BG_TOP,
    THEME_GLASS_BORDER,
    THEME_GLASS_HIGHLIGHT,
    THEME_GLASS_SHADOW,
)


class AudioWaveformWidget(QWidget):
    """Visualizes loaded audio waveform with playback position marker."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        self.samples: List[float] = []
        self.audio_name: Optional[str] = None
        self.current_ratio: float = 0.0

    def set_audio(self, name: str, samples: List[float]) -> None:
        self.audio_name = name
        self.samples = samples
        self.update()

    def clear_audio(self) -> None:
        self.audio_name = None
        self.samples = []
        self.current_ratio = 0.0
        self.update()

    def set_playhead_ratio(self, ratio: float) -> None:
        self.current_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setBrush(QColor(20, 20, 24, 130))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        painter.drawRoundedRect(r, 6, 6)

        if not self.samples:
            painter.setPen(QColor(114, 111, 106))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No audio track (click Audio to add)")
            painter.end()
            return

        w = self.width()
        h = self.height()
        mid_y = h / 2.0
        num = len(self.samples)

        painter.setPen(QPen(QColor(170, 167, 161, 150), 1.5))
        for i, s in enumerate(self.samples):
            x = (i / float(num)) * w
            bar_h = s * (mid_y - 2)
            painter.drawLine(QPointF(x, mid_y - bar_h), QPointF(x, mid_y + bar_h))

        if self.audio_name:
            painter.setPen(QColor(242, 240, 236))
            font = painter.font()
            font.setPointSize(8)
            painter.setFont(font)
            painter.drawText(6, 15, self.audio_name)

        playhead_x = self.current_ratio * w
        painter.setPen(QPen(QColor(231, 111, 81), 2.0))
        painter.drawLine(QPointF(playhead_x, 0), QPointF(playhead_x, h))
        painter.end()


class FrameThumbnailWidget(QWidget):
    """Clickable rounded thumbnail card with frame number badge and selection highlight."""

    clicked = Signal(int)
    rename_requested = Signal(int)

    CARD_W = 100
    CARD_H = 74

    def __init__(
        self,
        index: int,
        pixmap: QPixmap,
        name: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.index = index
        self.pixmap = pixmap
        self.name = name
        self.selected = False
        self.hovered = False
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        info = f"Frame {self.index + 1}"
        if self.name:
            info += f" ({self.name})"
        info += "\n• Click to select\n• Double-click to rename\n• Right-click for actions"
        self.setToolTip(info)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap
        self.update()

    def set_name(self, name: Optional[str]) -> None:
        self.name = name
        self._update_tooltip()
        self.update()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self.update()

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.rename_requested.emit(self.index)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        safe_rect = QRect(4, 4, w - 8, h - 22)

        # Dynamic canvas_rect preserving exact frame aspect ratio
        pw = self.pixmap.width() if self.pixmap and not self.pixmap.isNull() else 16
        ph = self.pixmap.height() if self.pixmap and not self.pixmap.isNull() else 9
        scaled_size = QSize(pw, ph).scaled(safe_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        canvas_rect = QRect(
            safe_rect.x() + (safe_rect.width() - scaled_size.width()) // 2,
            safe_rect.y() + (safe_rect.height() - scaled_size.height()) // 2,
            scaled_size.width(),
            scaled_size.height(),
        )
        radius = min(6.0, canvas_rect.height() / 4.0)

        # Draw thumbnail canvas content inside rounded canvas_rect
        path = QPainterPath()
        path.addRoundedRect(canvas_rect, radius, radius)
        painter.save()
        painter.setClipPath(path)

        # 1. Subtle checkerboard strictly within canvas_rect (for transparent canvases)
        c1 = QColor(242, 240, 236)
        c2 = QColor(222, 220, 216)
        cell = 6
        for cy in range(canvas_rect.top(), canvas_rect.bottom() + 1, cell):
            for cx in range(canvas_rect.left(), canvas_rect.right() + 1, cell):
                color = c1 if ((cx // cell) + (cy // cell)) % 2 == 0 else c2
                painter.fillRect(cx, cy, cell, cell, color)

        # 2. Scaled artwork composite filling canvas_rect
        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                canvas_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            px = canvas_rect.x() + (canvas_rect.width() - scaled.width()) // 2
            py = canvas_rect.y() + (canvas_rect.height() - scaled.height()) // 2
            painter.drawPixmap(px, py, scaled)

        painter.restore()

        # 3. Canvas border outline and selection glow
        # 3. Canvas border outline and selection glow
        if self.selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(160, 120, 255, 45))
            painter.drawRoundedRect(canvas_rect.adjusted(-2, -2, 2, 2), radius + 2, radius + 2)
            border_pen = QPen(QColor(160, 120, 255), 2.0)  # Studio Obsidian Neon Violet
        elif self.hovered:
            border_pen = QPen(QColor(208, 188, 255, 120), 1.2)  # Soft hover border
        else:
            border_pen = QPen(QColor(255, 255, 255, 26), 1.0)  # Low-contrast glass border

        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(canvas_rect, radius, radius)

        # Draw keyframe indicator diamond in top right of selected frame
        if self.selected:
            diamond_cx = canvas_rect.right() - 8
            diamond_cy = canvas_rect.top() + 8
            diamond_path = QPainterPath()
            diamond_path.moveTo(diamond_cx, diamond_cy - 4)
            diamond_path.lineTo(diamond_cx + 4, diamond_cy)
            diamond_path.lineTo(diamond_cx, diamond_cy + 4)
            diamond_path.lineTo(diamond_cx - 4, diamond_cy)
            diamond_path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 176, 205))  # Vivid magenta keyframe diamond
            painter.drawPath(diamond_path)

        # 4. Bottom-left badge for frame number
        num_str = str(self.index + 1)
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_w = fm.horizontalAdvance(num_str)
        badge_w = max(18, text_w + 8)
        badge_h = 15
        badge_rect = QRect(canvas_rect.left(), canvas_rect.bottom() + 3, badge_w, badge_h)

        badge_bg = QColor(160, 120, 255) if self.selected else QColor(36, 36, 42, 220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(badge_bg)
        painter.drawRoundedRect(badge_rect, 4, 4)

        if not self.selected:
            painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
            painter.drawRoundedRect(badge_rect, 4, 4)

        text_color = QColor(255, 255, 255) if self.selected else QColor(170, 167, 161)
        painter.setPen(text_color)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, num_str)

        # 5. Optional frame name next to badge
        if self.name:
            font.setBold(False)
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QColor(170, 167, 161))
            name_x = badge_rect.right() + 4
            name_w = canvas_rect.right() - name_x
            if name_w > 12:
                name_rect = QRect(name_x, canvas_rect.bottom() + 3, name_w, badge_h)
                elided = fm.elidedText(self.name, Qt.TextElideMode.ElideRight, name_w)
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        painter.end()


class AddFrameCardWidget(QWidget):
    """Clickable card at the end of the thumbnail strip to quickly append a new frame."""

    clicked = Signal()

    CARD_W = 100
    CARD_H = 74

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.hovered = False
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Add New Frame (+)")

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        safe_rect = QRect(4, 4, w - 8, h - 22)
        scaled_size = QSize(16, 9).scaled(safe_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
        canvas_rect = QRect(
            safe_rect.x() + (safe_rect.width() - scaled_size.width()) // 2,
            safe_rect.y() + (safe_rect.height() - scaled_size.height()) // 2,
            scaled_size.width(),
            scaled_size.height(),
        )
        radius = min(6.0, canvas_rect.height() / 4.0)

        if self.hovered:
            pen = QPen(QColor(231, 111, 81, 200), 1.5, Qt.PenStyle.DashLine)
            bg = QColor(231, 111, 81, 26)
        else:
            pen = QPen(QColor(255, 255, 255, 30), 1.5, Qt.PenStyle.DashLine)
            bg = QColor(255, 255, 255, 8)

        painter.setPen(pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(canvas_rect, radius, radius)

        # Centered plus sign
        plus_color = QColor(231, 111, 81) if self.hovered else QColor(110, 107, 102)
        painter.setPen(plus_color)
        font = painter.font()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(canvas_rect, Qt.AlignmentFlag.AlignCenter, "+")

        painter.end()


class TimelineWidget(QWidget):
    """Bottom timeline panel with modern frame strip, compact transport, and responsive settings."""

    frame_selected = Signal(int)
    add_frame_clicked = Signal()
    duplicate_frame_clicked = Signal()
    delete_frame_clicked = Signal()
    rename_frame_clicked = Signal(int)
    move_frame_left_clicked = Signal(int)
    move_frame_right_clicked = Signal(int)

    play_pause_clicked = Signal()
    stop_clicked = Signal()
    first_frame_clicked = Signal()
    last_frame_clicked = Signal()
    step_forward_clicked = Signal()
    step_backward_clicked = Signal()
    fps_value_changed = Signal(int)
    onion_skin_toggled = Signal(bool)
    onion_settings_requested = Signal()
    loop_mode_changed = Signal(str)
    audio_loaded = Signal(str)
    audio_cleared = Signal()
    audio_mute_toggled = Signal(bool)
    audio_volume_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._thumb_widgets: List[FrameThumbnailWidget] = []
        self._add_card: Optional[AddFrameCardWidget] = None
        self._current_index: int = 0
        self._total_frames: int = 1
        self._onion_enabled: bool = False
        self.audio_file_path: Optional[str] = None
        self._setup_ui()
        self._apply_styles()

    def _apply_styles(self) -> None:
        self.setStyleSheet(f"""
            TimelineWidget {{
                background-color: transparent;
            }}
            TimelineWidget QToolButton {{
                background-color: rgba(255, 255, 255, 0.06);
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
                padding: 0;
                margin: 0;
                font-size: 11px;
                font-weight: 500;
            }}
            TimelineWidget QToolButton:hover {{
                background-color: rgba(255, 255, 255, 0.13);
                border-color: rgba(255, 255, 255, 0.22);
                color: #ffffff;
            }}
            TimelineWidget QToolButton:pressed {{
                background-color: rgba(255, 255, 255, 0.04);
            }}
            TimelineWidget QToolButton:checked {{
                background-color: rgba(231, 111, 81, 0.22);
                border-color: {COLOR_ACCENT};
                color: #ffffff;
            }}
            TimelineWidget QToolButton:disabled {{
                background-color: rgba(255, 255, 255, 0.02);
                border-color: rgba(255, 255, 255, 0.04);
                color: {COLOR_TEXT_DISABLED};
            }}
        """)

    def paintEvent(self, event) -> None:
        """Render floating glass container with soft shadow, translucent gradient and top highlight."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        card_rect = QRectF(3.0, 3.0, w - 6.0, h - 6.0)
        radius = 14.0

        # Soft black shadow
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 25))
        p.drawRoundedRect(card_rect.adjusted(-2, 0, 2, 4), radius + 2, radius + 2)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(card_rect.adjusted(0, 1, 0, 3), radius, radius)

        # Translucent glass fill with subtle vertical gradient
        grad = QLinearGradient(0, card_rect.top(), 0, card_rect.bottom())
        grad.setColorAt(0.0, THEME_GLASS_BG_TOP)
        grad.setColorAt(1.0, THEME_GLASS_BG_BOTTOM)
        p.setBrush(grad)
        p.setPen(QPen(THEME_GLASS_BORDER, 1.0))
        p.drawRoundedRect(card_rect, radius, radius)

        # Inner highlight line at panel top
        p.setPen(QPen(THEME_GLASS_HIGHLIGHT, 1.0))
        p.drawLine(
            QPointF(card_rect.left() + radius, card_rect.top() + 1.0),
            QPointF(card_rect.right() - radius, card_rect.top() + 1.0),
        )
        p.end()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(4)

        # ── 1. Top Header Bar ──
        self.top_bar = QHBoxLayout()
        self.top_bar.setContentsMargins(0, 0, 0, 0)
        self.top_bar.setSpacing(4)

        # Left: Playback controls
        self.first_btn = QToolButton()
        self.first_btn.setText("|◀")
        self.first_btn.setToolTip("Go to First Frame (Home)")
        self.first_btn.setFixedSize(28, 26)
        self.first_btn.clicked.connect(self.first_frame_clicked)
        self.top_bar.addWidget(self.first_btn)

        self.prev_btn = QToolButton()
        self.prev_btn.setText("◀")
        self.prev_btn.setToolTip("Previous Frame (←)")
        self.prev_btn.setFixedSize(26, 26)
        self.prev_btn.clicked.connect(self.step_backward_clicked)
        self.top_bar.addWidget(self.prev_btn)

        self.play_btn = QToolButton()
        self.play_btn.setText("▶ Play")
        self.play_btn.setToolTip("Play / Pause Animation (Space)")
        self.play_btn.setFixedHeight(26)
        self.play_btn.setMinimumWidth(66)
        self.play_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: {COLOR_ACCENT_CONTAINER};
                border: 1px solid {COLOR_ACCENT};
                border-radius: 6px;
                color: #FFFFFF;
                font-weight: 700;
                padding: 0 8px;
            }}
            QToolButton:hover {{
                background-color: {COLOR_ACCENT};
                border-color: {COLOR_ACCENT_HOVER};
                color: #10131D;
            }}
            QToolButton:pressed {{
                background-color: {COLOR_ACCENT_PRESSED};
                color: #FFFFFF;
            }}
        """)
        self.play_btn.clicked.connect(self.play_pause_clicked)
        self.top_bar.addWidget(self.play_btn)

        self.next_btn = QToolButton()
        self.next_btn.setText("▶")
        self.next_btn.setToolTip("Next Frame (→)")
        self.next_btn.setFixedSize(26, 26)
        self.next_btn.clicked.connect(self.step_forward_clicked)
        self.top_bar.addWidget(self.next_btn)

        self.last_btn = QToolButton()
        self.last_btn.setText("▶|")
        self.last_btn.setToolTip("Go to Last Frame (End)")
        self.last_btn.setFixedSize(28, 26)
        self.last_btn.clicked.connect(self.last_frame_clicked)
        self.top_bar.addWidget(self.last_btn)

        self.stop_btn = QToolButton()
        self.stop_btn.setText("Stop")
        self.stop_btn.setToolTip("Stop and Rewind")
        self.stop_btn.setFixedHeight(26)
        self.stop_btn.clicked.connect(self.stop_clicked)
        self.top_bar.addWidget(self.stop_btn)

        self.top_bar.addSpacing(6)

        # Center: Frame counter badge & primary actions
        self.frame_info = QLabel("Frame 1 of 1")
        self.frame_info.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_ACCENT};
                background-color: rgba(28, 31, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        self.top_bar.addWidget(self.frame_info)

        self.add_btn = QToolButton()
        self.add_btn.setText("+ Frame")
        self.add_btn.setToolTip("Create a new blank frame after current (Ctrl+Shift+N)")
        self.add_btn.setFixedHeight(26)
        self.add_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: rgba(208, 188, 255, 0.16);
                color: {COLOR_ACCENT};
                font-weight: 600;
                border: 1px solid rgba(208, 188, 255, 0.35);
                border-radius: 6px;
                padding: 0 8px;
            }}
            QToolButton:hover {{
                background-color: {COLOR_ACCENT};
                border-color: {COLOR_ACCENT};
                color: #10131D;
            }}
            QToolButton:pressed {{
                background-color: {COLOR_ACCENT_PRESSED};
                color: #FFFFFF;
            }}
        """)
        self.add_btn.clicked.connect(self.add_frame_clicked)
        self.top_bar.addWidget(self.add_btn)

        self.dup_btn = QToolButton()
        self.dup_btn.setText("Dup")
        self.dup_btn.setToolTip("Duplicate current frame (Ctrl+D)")
        self.dup_btn.setFixedHeight(26)
        self.dup_btn.clicked.connect(self.duplicate_frame_clicked)
        self.top_bar.addWidget(self.dup_btn)

        self.del_btn = QToolButton()
        self.del_btn.setText("Del")
        self.del_btn.setToolTip("Delete current frame (Delete)")
        self.del_btn.setFixedHeight(26)
        self.del_btn.clicked.connect(self.delete_frame_clicked)
        self.top_bar.addWidget(self.del_btn)

        self.top_bar.addStretch()

        # Right: Utility icons (Onion, Audio, Settings, Overflow)
        self.onion_btn = QToolButton()
        self.onion_btn.setText("Onion")
        self.onion_btn.setCheckable(True)
        self.onion_btn.setToolTip("Toggle Onion Skinning (O)")
        self.onion_btn.setFixedHeight(26)
        self.onion_btn.toggled.connect(self._on_onion_toggled)
        self.top_bar.addWidget(self.onion_btn)

        self.audio_mute_btn = QToolButton()
        self.audio_mute_btn.setText("Mute")
        self.audio_mute_btn.setToolTip("Mute / Unmute Audio")
        self.audio_mute_btn.setCheckable(True)
        self.audio_mute_btn.setFixedHeight(26)
        self.audio_mute_btn.toggled.connect(self._on_audio_mute_toggled)
        self.top_bar.addWidget(self.audio_mute_btn)

        self.audio_btn = QToolButton()
        self.audio_btn.setText("Audio")
        self.audio_btn.setToolTip("Audio Track (Import / Toggle Waveform)")
        self.audio_btn.setFixedHeight(26)
        self.audio_btn.clicked.connect(self._on_audio_btn_clicked)
        self.top_bar.addWidget(self.audio_btn)

        self.settings_btn = QToolButton()
        self.settings_btn.setText("Config")
        self.settings_btn.setCheckable(True)
        self.settings_btn.setToolTip("Timeline & Animation Settings (FPS, Loop, Onion)")
        self.settings_btn.setFixedHeight(26)
        self.settings_btn.toggled.connect(self._toggle_settings_bar)
        self.top_bar.addWidget(self.settings_btn)

        self.overflow_btn = QToolButton()
        self.overflow_btn.setText("•••")
        self.overflow_btn.setToolTip("More Frame Actions...")
        self.overflow_btn.setFixedSize(26, 26)
        self.overflow_btn.clicked.connect(self._show_overflow_menu)
        self.top_bar.addWidget(self.overflow_btn)

        main_layout.addLayout(self.top_bar)

        # ── 2. Collapsible Secondary Settings Bar ──
        self.settings_bar = QWidget()
        settings_layout = QHBoxLayout(self.settings_bar)
        settings_layout.setContentsMargins(4, 2, 4, 2)
        settings_layout.setSpacing(6)
        self.settings_bar.setStyleSheet(f"""
            QWidget {{
                background-color: #262626;
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
            }}
        """)

        lbl_fps = QLabel("FPS:")
        lbl_fps.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        settings_layout.addWidget(lbl_fps)

        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(1, 60)
        self.fps_spinbox.setValue(12)
        self.fps_spinbox.setFixedWidth(52)
        self.fps_spinbox.setFixedHeight(24)
        self.fps_spinbox.valueChanged.connect(self.fps_value_changed)
        settings_layout.addWidget(self.fps_spinbox)

        self.loop_combo = QComboBox()
        self.loop_combo.addItem("Loop", "loop")
        self.loop_combo.addItem("Once", "once")
        self.loop_combo.addItem("Ping-Pong", "ping_pong")
        self.loop_combo.setToolTip("Playback Loop Mode")
        self.loop_combo.setFixedHeight(24)
        self.loop_combo.setMinimumWidth(85)
        self.loop_combo.currentIndexChanged.connect(lambda: self.loop_mode_changed.emit(self.loop_combo.currentData()))
        settings_layout.addWidget(self.loop_combo)

        self.onion_settings_btn = QToolButton()
        self.onion_settings_btn.setText("Onion Config")
        self.onion_settings_btn.setToolTip("Configure Onion Skin Tint & Frames")
        self.onion_settings_btn.setFixedHeight(24)
        self.onion_settings_btn.clicked.connect(self.onion_settings_requested)
        settings_layout.addWidget(self.onion_settings_btn)

        sep_s = QFrame()
        sep_s.setFrameShape(QFrame.Shape.VLine)
        sep_s.setFixedWidth(2)
        settings_layout.addWidget(sep_s)

        self.rename_btn = QToolButton()
        self.rename_btn.setText("Rename")
        self.rename_btn.setToolTip("Rename current frame (F2)")
        self.rename_btn.setFixedHeight(24)
        self.rename_btn.clicked.connect(lambda: self.rename_frame_clicked.emit(self._current_index))
        settings_layout.addWidget(self.rename_btn)

        self.move_left_btn = QToolButton()
        self.move_left_btn.setText("◀ Move Left")
        self.move_left_btn.setToolTip("Move Frame Left")
        self.move_left_btn.setFixedHeight(24)
        self.move_left_btn.clicked.connect(lambda: self.move_frame_left_clicked.emit(self._current_index))
        settings_layout.addWidget(self.move_left_btn)

        self.move_right_btn = QToolButton()
        self.move_right_btn.setText("Move Right ▶")
        self.move_right_btn.setToolTip("Move Frame Right")
        self.move_right_btn.setFixedHeight(24)
        self.move_right_btn.clicked.connect(lambda: self.move_frame_right_clicked.emit(self._current_index))
        settings_layout.addWidget(self.move_right_btn)

        settings_layout.addStretch()

        lbl_vol = QLabel("Vol:")
        lbl_vol.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px;")
        settings_layout.addWidget(lbl_vol)

        self.audio_vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_vol_slider.setRange(0, 100)
        self.audio_vol_slider.setValue(80)
        self.audio_vol_slider.setFixedWidth(60)
        self.audio_vol_slider.setToolTip("Audio Volume")
        self.audio_vol_slider.valueChanged.connect(self.audio_volume_changed)
        settings_layout.addWidget(self.audio_vol_slider)

        self.settings_bar.setVisible(False)
        main_layout.addWidget(self.settings_bar)

        # ── 3. Frame Thumbnails Scroll Area ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFixedHeight(88)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 5px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #383838;
                min-width: 24px;
                border-radius: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #505050;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: transparent;
            }
        """)
        self.scroll_area.viewport().setStyleSheet("background-color: transparent;")

        self.thumb_container = QWidget()
        self.thumb_container.setStyleSheet("background-color: transparent;")
        self.thumb_layout = QHBoxLayout(self.thumb_container)
        self.thumb_layout.setContentsMargins(2, 2, 2, 2)
        self.thumb_layout.setSpacing(8)
        self.thumb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.thumb_container)
        main_layout.addWidget(self.scroll_area)

        # ── 4. Collapsible Audio Track (hidden by default) ──
        self.audio_track_widget = QWidget()
        audio_layout = QHBoxLayout(self.audio_track_widget)
        audio_layout.setContentsMargins(4, 2, 4, 2)
        audio_layout.setSpacing(6)
        self.audio_track_widget.setStyleSheet("""
            QWidget {
                background-color: #0b1120;
                border: 1px solid #1e293b;
                border-radius: 6px;
            }
        """)

        self.waveform_widget = AudioWaveformWidget()
        audio_layout.addWidget(self.waveform_widget, 1)

        self.audio_clear_btn = QToolButton()
        self.audio_clear_btn.setText("✖")
        self.audio_clear_btn.setToolTip("Remove Audio Track")
        self.audio_clear_btn.setFixedSize(22, 22)
        self.audio_clear_btn.clicked.connect(self._on_clear_audio_clicked)
        audio_layout.addWidget(self.audio_clear_btn)

        self.audio_track_widget.setVisible(False)
        main_layout.addWidget(self.audio_track_widget)

    def _toggle_settings_bar(self, checked: bool) -> None:
        self.settings_bar.setVisible(checked)

    def _on_audio_btn_clicked(self) -> None:
        if self.audio_file_path:
            self.audio_track_widget.setVisible(not self.audio_track_widget.isVisible())
        else:
            self._on_load_audio_clicked()

    def _on_load_audio_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Audio Track", "",
            "Audio Files (*.wav *.mp3 *.ogg *.m4a *.flac);;All Files (*)",
        )
        if path:
            self.audio_file_path = path
            samples = self._extract_waveform(path)
            self.waveform_widget.set_audio(os.path.basename(path), samples)
            self.audio_track_widget.setVisible(True)
            self.audio_loaded.emit(path)

    def _on_clear_audio_clicked(self) -> None:
        self.audio_file_path = None
        self.waveform_widget.clear_audio()
        self.audio_track_widget.setVisible(False)
        self.audio_cleared.emit()

    def _on_audio_mute_toggled(self, checked: bool) -> None:
        self.audio_mute_btn.setText("Muted" if checked else "Mute")
        self.audio_mute_toggled.emit(checked)

    def _extract_waveform(self, path: str, num_samples: int = 150) -> List[float]:
        ext = os.path.splitext(path)[1].lower()
        if ext == ".wav":
            try:
                with wave.open(path, "rb") as wf:
                    sampwidth = wf.getsampwidth()
                    nframes = wf.getnframes()
                    if nframes > 0:
                        raw = wf.readframes(min(nframes, 2000000))
                        if sampwidth == 2:
                            data = struct.unpack(f"<{len(raw)//2}h", raw)
                        elif sampwidth == 1:
                            data = [b - 128 for b in raw]
                        else:
                            return [0.4] * num_samples
                        step = max(1, len(data) // num_samples)
                        samples = []
                        for i in range(0, min(len(data), step * num_samples), step):
                            chunk = data[i:i+step]
                            v = max(abs(x) for x in chunk) / (32768.0 if sampwidth == 2 else 128.0)
                            samples.append(min(1.0, v))
                        return samples
            except Exception:
                pass
        import math
        return [0.2 + 0.6 * abs(math.sin(i * 0.2)) for i in range(num_samples)]

    def _on_onion_toggled(self, checked: bool) -> None:
        self._onion_enabled = checked
        self.onion_skin_toggled.emit(checked)

    def set_playing_state(self, is_playing: bool) -> None:
        """Update play button appearance based on playback state."""
        self.play_btn.setText("⏸ Pause" if is_playing else "▶ Play")

    def set_fps(self, fps: int) -> None:
        """Update FPS spinbox without triggering signal."""
        self.fps_spinbox.blockSignals(True)
        self.fps_spinbox.setValue(fps)
        self.fps_spinbox.blockSignals(False)

    def set_onion_skin_checked(self, checked: bool) -> None:
        """Set onion skin toggle state without triggering signal."""
        self.onion_btn.blockSignals(True)
        self.onion_btn.setChecked(checked)
        self.onion_btn.blockSignals(False)
        self._onion_enabled = checked

    def refresh_thumbnails(self, frames, current_index: int = 0) -> None:
        """Rebuild all thumbnail widgets from the frame list."""
        for w in self._thumb_widgets:
            self.thumb_layout.removeWidget(w)
            w.hide()
            w.setParent(None)
            w.deleteLater()
        self._thumb_widgets.clear()

        if self._add_card is not None:
            self.thumb_layout.removeWidget(self._add_card)
            self._add_card.hide()
            self._add_card.setParent(None)
            self._add_card.deleteLater()
            self._add_card = None

        self._total_frames = max(1, len(frames))

        for idx, frame in enumerate(frames):
            tw = FrameThumbnailWidget(
                index=idx,
                pixmap=frame.get_thumbnail(),
                name=getattr(frame, "name", None),
            )
            tw.clicked.connect(self._on_thumb_clicked)
            tw.rename_requested.connect(self.rename_frame_clicked)
            tw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tw.customContextMenuRequested.connect(
                lambda pos, i=idx: self._show_context_menu(i, pos)
            )
            self._thumb_widgets.append(tw)
            self.thumb_layout.addWidget(tw)
            tw.show()

        # Add the trailing '+ Add Frame' card
        self._add_card = AddFrameCardWidget()
        self._add_card.clicked.connect(self.add_frame_clicked)
        self.thumb_layout.addWidget(self._add_card)
        self._add_card.show()

        self._current_index = current_index
        self._update_selection(current_index)
        self._update_button_states()
        self._update_frame_info(current_index, len(frames), frames)
        self._scroll_to_frame(current_index)

    def update_single_thumbnail(self, index: int, frame) -> None:
        """Update a single thumbnail without rebuilding the strip."""
        if 0 <= index < len(self._thumb_widgets):
            self._thumb_widgets[index].set_pixmap(frame.get_thumbnail())
            self._thumb_widgets[index].set_name(getattr(frame, "name", None))

    def highlight_frame(self, index: int, total_frames: int, frames: Optional[List] = None) -> None:
        """Update selection highlight to the specified frame and auto-scroll."""
        self._current_index = index
        self._total_frames = max(1, total_frames)
        self._update_selection(index)
        self._update_button_states()
        self._update_frame_info(index, total_frames, frames)
        self._scroll_to_frame(index)
        ratio = float(index) / float(max(1, total_frames - 1)) if total_frames > 1 else 0.0
        self.waveform_widget.set_playhead_ratio(ratio)

    def _update_selection(self, selected_index: int) -> None:
        for tw in self._thumb_widgets:
            tw.set_selected(tw.index == selected_index)

    def _update_button_states(self) -> None:
        can_delete = self._total_frames > 1
        self.del_btn.setEnabled(can_delete)
        self.move_left_btn.setEnabled(self._current_index > 0)
        self.move_right_btn.setEnabled(self._current_index < self._total_frames - 1)

    def _update_frame_info(self, index: int, total: int, frames: Optional[List] = None) -> None:
        total_val = max(1, total)
        current_num = index + 1
        name_suffix = ""
        if frames and 0 <= index < len(frames):
            frame_name = getattr(frames[index], "name", None)
            if frame_name:
                name_suffix = f" • \"{frame_name}\""
        elif 0 <= index < len(self._thumb_widgets):
            frame_name = self._thumb_widgets[index].name
            if frame_name:
                name_suffix = f" • \"{frame_name}\""

        self.frame_info.setText(f"{current_num} / {total_val}{name_suffix}")

    def _scroll_to_frame(self, index: int) -> None:
        """Auto-scroll the frame strip to make the selected frame visible."""
        if 0 <= index < len(self._thumb_widgets):
            self.thumb_container.adjustSize()
            widget = self._thumb_widgets[index]
            self.scroll_area.ensureWidgetVisible(widget, 50, 0)

    def _on_thumb_clicked(self, index: int) -> None:
        self._current_index = index
        self._update_selection(index)
        self._update_button_states()
        self.frame_selected.emit(index)

    def _show_overflow_menu(self) -> None:
        """Show overflow popup menu for secondary actions."""
        menu = QMenu(self)

        act_add = QAction("+ Add New Frame (Ctrl+Shift+N)", menu)
        act_add.triggered.connect(self.add_frame_clicked)
        menu.addAction(act_add)

        act_dup = QAction("⊞ Duplicate Current Frame (Ctrl+D)", menu)
        act_dup.triggered.connect(self.duplicate_frame_clicked)
        menu.addAction(act_dup)

        act_del = QAction("🗑 Delete Current Frame (Del)", menu)
        act_del.setEnabled(self._total_frames > 1)
        act_del.triggered.connect(self.delete_frame_clicked)
        menu.addAction(act_del)

        menu.addSeparator()

        act_rename = QAction("✏ Rename Frame (F2)...", menu)
        act_rename.triggered.connect(lambda: self.rename_frame_clicked.emit(self._current_index))
        menu.addAction(act_rename)

        act_left = QAction("◀ Move Frame Left", menu)
        act_left.setEnabled(self._current_index > 0)
        act_left.triggered.connect(lambda: self.move_frame_left_clicked.emit(self._current_index))
        menu.addAction(act_left)

        act_right = QAction("Move Frame Right ▶", menu)
        act_right.setEnabled(self._current_index < self._total_frames - 1)
        act_right.triggered.connect(lambda: self.move_frame_right_clicked.emit(self._current_index))
        menu.addAction(act_right)

        menu.addSeparator()

        act_settings = QAction("🎛 Toggle Advanced Settings", menu)
        act_settings.triggered.connect(lambda: self.settings_btn.toggle())
        menu.addAction(act_settings)

        act_onion_cfg = QAction("⚙ Onion Skin Configuration...", menu)
        act_onion_cfg.triggered.connect(self.onion_settings_requested)
        menu.addAction(act_onion_cfg)

        pos = self.overflow_btn.mapToGlobal(self.overflow_btn.rect().bottomLeft())
        menu.exec(pos)

    def _show_context_menu(self, index: int, pos) -> None:
        """Show right-click context menu for a frame thumbnail."""
        menu = QMenu(self)

        act_rename = QAction("✏ Rename Frame (F2)...", menu)
        act_rename.triggered.connect(lambda: self.rename_frame_clicked.emit(index))
        menu.addAction(act_rename)

        menu.addSeparator()

        act_insert_before = QAction("Insert Frame Before", menu)
        act_insert_before.triggered.connect(lambda: self._context_insert_before(index))
        menu.addAction(act_insert_before)

        act_insert_after = QAction("Insert Frame After", menu)
        act_insert_after.triggered.connect(lambda: self._context_insert_after(index))
        menu.addAction(act_insert_after)

        menu.addSeparator()

        act_move_left = QAction("◀ Move Frame Left", menu)
        act_move_left.setEnabled(index > 0)
        act_move_left.triggered.connect(lambda: self.move_frame_left_clicked.emit(index))
        menu.addAction(act_move_left)

        act_move_right = QAction("Move Frame Right ▶", menu)
        act_move_right.setEnabled(index < self._total_frames - 1)
        act_move_right.triggered.connect(lambda: self.move_frame_right_clicked.emit(index))
        menu.addAction(act_move_right)

        menu.addSeparator()

        act_duplicate = QAction("⊞ Duplicate Frame", menu)
        act_duplicate.triggered.connect(self.duplicate_frame_clicked)
        menu.addAction(act_duplicate)

        act_delete = QAction("🗑 Delete Frame", menu)
        act_delete.setEnabled(self._total_frames > 1)
        act_delete.triggered.connect(self.delete_frame_clicked)
        menu.addAction(act_delete)

        menu.exec(self._thumb_widgets[index].mapToGlobal(pos))

    def _context_insert_before(self, index: int) -> None:
        self.frame_selected.emit(max(0, index - 1))
        self.add_frame_clicked.emit()

    def _context_insert_after(self, index: int) -> None:
        self.frame_selected.emit(index)
        self.add_frame_clicked.emit()
