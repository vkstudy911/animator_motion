"""Canvas container widget with Studio Obsidian HUD overlay.

Encapsulates the DrawingCanvas inside an adaptive viewport with
real-time HUD metadata display and floating controls:
- Top-Left: Zoom Pill ([-], zoom %, [+], Fit, Aspect Ratio)
- Top-Center: Document Specs Pill (Artboard, Resolution, FPS)
- Top-Right: Quick Display Toggles (Onion Skin, Grid, Snapping)
- Bottom-Left: Floating Keyframe Watermark (Active Frame Indicator)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.drawing.canvas import DrawingCanvas
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_CONTAINER,
    COLOR_BORDER,
    COLOR_GLASS_BORDER,
    COLOR_PANEL_BG,
    COLOR_PANEL_CONTAINER,
    COLOR_SECONDARY,
    COLOR_SURFACE_HIGH,
    COLOR_SURFACE_HIGHEST,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class CanvasContainer(QWidget):
    """Viewport container wrapping the DrawingCanvas with floating Studio Obsidian HUD controls."""

    def __init__(self, canvas: DrawingCanvas, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        # Main layout holds the canvas filling entire area
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)

        # ── 1. Top-Left: Zoom Navigation Pill ──
        self.zoom_pill = QFrame(self)
        self.zoom_pill.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(28, 31, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                padding: 2px 5px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
            }}
        """)
        z_layout = QHBoxLayout(self.zoom_pill)
        z_layout.setContentsMargins(6, 2, 6, 2)
        z_layout.setSpacing(4)

        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedSize(18, 18)
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        self.btn_zoom_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        z_layout.addWidget(self.btn_zoom_out)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 11px; font-weight: 700; background: transparent; border: none;"
        )
        z_layout.addWidget(self.zoom_label)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedSize(18, 18)
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl++)")
        self.btn_zoom_in.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        z_layout.addWidget(self.btn_zoom_in)

        sep_z = QFrame()
        sep_z.setFrameShape(QFrame.Shape.VLine)
        sep_z.setStyleSheet(f"background-color: {COLOR_GLASS_BORDER}; border: none;")
        sep_z.setFixedWidth(1)
        z_layout.addWidget(sep_z)

        self.btn_fit = QPushButton("Fit")
        self.btn_fit.setToolTip("Fit Canvas to Viewport (Ctrl+0)")
        self.btn_fit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fit.clicked.connect(self.canvas.zoom_fit)
        z_layout.addWidget(self.btn_fit)

        self.format_pill = QLabel("16:9")
        self.format_pill.setStyleSheet(f"""
            QLabel {{
                background-color: rgba(208, 188, 255, 0.15);
                color: {COLOR_ACCENT};
                border: 1px solid rgba(208, 188, 255, 0.30);
                border-radius: 4px;
                padding: 1px 5px;
                font-size: 10px;
                font-weight: 700;
            }}
        """)
        z_layout.addWidget(self.format_pill)

        # ── 2. Top-Center: Document Specs Pill ──
        self.specs_pill = QFrame(self)
        self.specs_pill.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(28, 31, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
            }}
        """)
        s_layout = QHBoxLayout(self.specs_pill)
        s_layout.setContentsMargins(10, 3, 10, 3)
        s_layout.setSpacing(6)

        self.artboard_dot = QLabel("●")
        self.artboard_dot.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 8px; background: transparent; border: none;")
        s_layout.addWidget(self.artboard_dot)

        self.specs_label = QLabel("Artboard 1 · 1920×1080 · 12 FPS")
        self.specs_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 500; background: transparent; border: none;"
        )
        s_layout.addWidget(self.specs_label)

        # ── 3. Top-Right: Quick Display Toggles ──
        self.toggles_pill = QFrame(self)
        self.toggles_pill.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(28, 31, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLOR_TEXT_SECONDARY};
                font-size: 11px;
                font-weight: 600;
                padding: 2px 7px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.12);
                color: #FFFFFF;
            }}
            QPushButton:checked {{
                background-color: rgba(208, 188, 255, 0.20);
                color: {COLOR_ACCENT};
                border: 1px solid rgba(208, 188, 255, 0.35);
            }}
        """)
        t_layout = QHBoxLayout(self.toggles_pill)
        t_layout.setContentsMargins(6, 2, 6, 2)
        t_layout.setSpacing(4)

        self.btn_grid_toggle = QPushButton("Grid")
        self.btn_grid_toggle.setCheckable(True)
        self.btn_grid_toggle.setChecked(self.canvas.show_grid)
        self.btn_grid_toggle.setToolTip("Toggle Background Alignment Grid")
        self.btn_grid_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_grid_toggle.clicked.connect(lambda checked: self.canvas.toggle_grid())
        t_layout.addWidget(self.btn_grid_toggle)

        sep_t = QFrame()
        sep_t.setFrameShape(QFrame.Shape.VLine)
        sep_t.setStyleSheet(f"background-color: {COLOR_GLASS_BORDER}; border: none;")
        sep_t.setFixedWidth(1)
        t_layout.addWidget(sep_t)

        self.btn_onion_pill = QPushButton("Onion")
        self.btn_onion_pill.setCheckable(True)
        self.btn_onion_pill.setToolTip("Toggle Onion Skin (O)")
        self.btn_onion_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_onion_pill.toggled.connect(self._on_onion_pill_toggled)
        t_layout.addWidget(self.btn_onion_pill)

        # ── 4. Bottom-Left: Frame Watermark ──
        self.frame_watermark = QFrame(self)
        self.frame_watermark.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(28, 31, 42, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
            }}
        """)
        fw_layout = QHBoxLayout(self.frame_watermark)
        fw_layout.setContentsMargins(8, 3, 8, 3)
        fw_layout.setSpacing(5)

        self.fw_dot = QLabel("●")
        self.fw_dot.setStyleSheet(f"color: {COLOR_SECONDARY}; font-size: 8px; background: transparent; border: none;")
        fw_layout.addWidget(self.fw_dot)

        self.fw_label = QLabel("Frame 01 / Active Keyframe")
        self.fw_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; font-weight: 500; background: transparent; border: none;"
        )
        fw_layout.addWidget(self.fw_label)

        # Legacy compatibility HUD label
        self.hud_label = self.fw_label

        self.update_hud(zoom=1.0, frame_idx=0, total_frames=1, width=1920, height=1080)

    def _connect_signals(self) -> None:
        self.canvas.zoom_changed.connect(self._on_zoom_changed)

    def _on_zoom_changed(self, zoom: float) -> None:
        if self.canvas.project:
            cur_frame = self.canvas.project.current_frame_index
            total = self.canvas.project.frame_count()
            w = self.canvas.project.canvas_width
            h = self.canvas.project.canvas_height
            fps = self.canvas.project.fps
        else:
            cur_frame, total, w, h, fps = 0, 1, 1920, 1080, 12
        self.update_hud(zoom=zoom, frame_idx=cur_frame, total_frames=total, width=w, height=h, fps=fps)

    def _on_onion_pill_toggled(self, checked: bool) -> None:
        if self.canvas.onion_skin_renderer:
            self.canvas.onion_skin_renderer.enabled = checked
            self.canvas.update()
        self.btn_onion_pill.setText("Onion ●" if checked else "Onion")

    def set_onion_active(self, active: bool, count: int = 1) -> None:
        self.btn_onion_pill.blockSignals(True)
        self.btn_onion_pill.setChecked(active)
        self.btn_onion_pill.setText(f"Onion: {count}F" if active else "Onion")
        self.btn_onion_pill.blockSignals(False)

    def update_hud(
        self,
        zoom: float,
        frame_idx: int,
        total_frames: int,
        width: int,
        height: int,
        fps: int = 12,
    ) -> None:
        """Update floating HUD text display across all overlay pills."""
        percent = int(zoom * 100)
        self.zoom_label.setText(f"{percent}%")
        self.specs_label.setText(f"Artboard 1 · {width}×{height} · {fps} FPS")
        self.fw_label.setText(f"Frame {frame_idx + 1:02d} / Active Keyframe")

        # Update aspect format label
        from app.core.canvas_format import get_ratio_label
        self.format_pill.setText(get_ratio_label(width, height))

        self.zoom_pill.adjustSize()
        self.specs_pill.adjustSize()
        self.toggles_pill.adjustSize()
        self.frame_watermark.adjustSize()
        self._reposition_hud()

    def _reposition_hud(self) -> None:
        """Anchor HUD pills around the canvas stage."""
        margin = 12
        top_y = margin

        # Top-Left: Zoom
        self.zoom_pill.move(margin, top_y)

        # Top-Center: Specs
        center_x = (self.width() - self.specs_pill.width()) // 2
        if center_x > self.zoom_pill.x() + self.zoom_pill.width() + 10:
            self.specs_pill.move(center_x, top_y)
            self.specs_pill.show()
        else:
            self.specs_pill.hide()

        # Top-Right: Toggles
        right_x = self.width() - self.toggles_pill.width() - margin
        if right_x > 0:
            self.toggles_pill.move(right_x, top_y)

        # Bottom-Left: Frame Watermark
        bot_y = self.height() - self.frame_watermark.height() - margin
        if bot_y > 0:
            self.frame_watermark.move(margin, bot_y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_hud()
