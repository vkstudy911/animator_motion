"""Top Application Bar for AI Doodle Studio (Studio Obsidian).

Adopts the Studio Obsidian / Motion Doodle pro creative suite layout:
- Left Zone: Brand icon & title breadcrumb (Motion Doodle / Project Name — Edited) + Aspect Ratio Pill.
- Center Zone: Quick Actions & Tools Command Bar (⌘K) + Workspace Switcher (Canvas / Timeline / Nodes).
- Right Zone: History (Undo/Redo), Onion Skin pill, Preview hero trigger, Export CTA (⌘E), Settings, AI Dock toggle.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_CONTAINER,
    COLOR_ACCENT_HOVER,
    COLOR_GLASS_BORDER,
    COLOR_GLASS_BORDER_HOVER,
    COLOR_GLASS_BORDER_SUBTLE,
    COLOR_ON_ACCENT_CONTAINER,
    COLOR_PANEL_BG,
    COLOR_PANEL_CONTAINER,
    COLOR_SECONDARY,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HIGH,
    COLOR_SURFACE_HIGHEST,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)

SVG_BRAND = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" fill="none">'
    '<defs>'
    '<linearGradient id="grad-v" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">'
    '<stop offset="0%" stop-color="#D0BCFF"/>'
    '<stop offset="50%" stop-color="#A078FF"/>'
    '<stop offset="100%" stop-color="#4CD7F6"/>'
    '</linearGradient>'
    '</defs>'
    '<rect x="3" y="3" width="26" height="26" rx="7" fill="#1C1F2A" stroke="url(#grad-v)" stroke-width="1.8"/>'
    '<rect x="7" y="9" width="12" height="14" rx="2.5" fill="#32343F" opacity="0.5" transform="rotate(-12 7 9)"/>'
    '<rect x="10" y="8" width="12" height="14" rx="2.5" fill="#272A34" stroke="#4CD7F6" stroke-width="1.2" opacity="0.8" transform="rotate(-4 10 8)"/>'
    '<rect x="13" y="8" width="12" height="14" rx="2.5" fill="#181B25" stroke="url(#grad-v)" stroke-width="1.5"/>'
    '<polygon points="17,12 23,15 17,18" fill="#4CD7F6"/>'
    '</svg>'
)


def _render_svg(svg_str: str, size: int = 16) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class TopToolbar(QToolBar):
    """Studio Obsidian Top Navigation & Global Controls Header."""

    new_project_triggered = Signal()
    open_project_triggered = Signal()
    save_project_triggered = Signal()
    undo_triggered = Signal()
    redo_triggered = Signal()
    zoom_in_triggered = Signal()
    zoom_out_triggered = Signal()
    zoom_reset_triggered = Signal()
    zoom_fit_triggered = Signal()
    play_pause_triggered = Signal()
    preview_triggered = Signal()
    stop_triggered = Signal()
    fps_changed = Signal(int)
    onion_skin_toggled = Signal(bool)
    grid_toggled = Signal(bool)
    canvas_format_triggered = Signal()
    ai_assistant_toggled = Signal(bool)
    command_palette_triggered = Signal()
    export_triggered = Signal()
    settings_triggered = Signal()
    workspace_changed = Signal(str)  # "canvas", "timeline", "nodes"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Main Top Bar", parent)
        self.setMovable(False)
        self.setFloatable(False)
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            TopToolbar {{
                background-color: {COLOR_PANEL_BG};
                border-bottom: 1px solid {COLOR_GLASS_BORDER_SUBTLE};
                padding: 0 8px;
                margin: 0;
                spacing: 0;
            }}
        """)
        # Actions for menu/shortcut and test compatibility
        self.act_format = QAction("Format: 16:9", self)
        self.act_format.triggered.connect(self.canvas_format_triggered)

        self.act_onion = QAction("Onion Skin", self)
        self.act_onion.setCheckable(True)
        self.act_onion.triggered.connect(self.onion_skin_toggled)

        self.act_ai_chat = QAction("AI Assistant", self)
        self.act_ai_chat.setCheckable(True)
        self.act_ai_chat.setChecked(True)
        self.act_ai_chat.triggered.connect(self.ai_assistant_toggled)

        self._build_ui()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(10)

        # ── Zone 1: Left Zone (Brand, Project Name, Format Badge) ──
        left_layout = QHBoxLayout()
        left_layout.setSpacing(8)

        # Brand Icon
        brand_icon_lbl = QLabel()
        brand_icon_lbl.setPixmap(_render_svg(SVG_BRAND, 24).pixmap(24, 24))
        brand_icon_lbl.setToolTip("AI Doodle Studio (Motion Doodle)")
        left_layout.addWidget(brand_icon_lbl)

        # Title Breadcrumb
        self.brand_title_lbl = QLabel("Motion Doodle")
        self.brand_title_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {COLOR_ACCENT};")
        left_layout.addWidget(self.brand_title_lbl)

        sep_slash = QLabel("/")
        sep_slash.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_MUTED};")
        left_layout.addWidget(sep_slash)

        self.project_name_lbl = QLabel("Untitled Project")
        self.project_name_lbl.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {COLOR_TEXT_PRIMARY};")
        left_layout.addWidget(self.project_name_lbl)

        self.mod_badge = QLabel("— Edited")
        self.mod_badge.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED};")
        left_layout.addWidget(self.mod_badge)

        # Canvas Format Pill (Clickable)
        self.format_btn = QPushButton("16:9")
        self.format_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.format_btn.setToolTip("Change Canvas Aspect Ratio & Format")
        self.format_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PANEL_CONTAINER};
                color: {COLOR_ACCENT};
                border: 1px solid rgba(208, 188, 255, 0.25);
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HIGH};
                border-color: {COLOR_ACCENT};
            }}
        """)
        self.format_btn.clicked.connect(self.canvas_format_triggered)
        left_layout.addWidget(self.format_btn)

        layout.addLayout(left_layout)
        layout.addStretch()

        # ── Zone 2: Center Zone (Command Bar ⌘K + Workspace Switcher) ──
        center_layout = QHBoxLayout()
        center_layout.setSpacing(10)

        # Quick Actions & Tools Command Bar
        self.cmd_bar_btn = QPushButton("🔍  Quick Actions & Tools")
        self.cmd_bar_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cmd_bar_btn.setToolTip("Search Commands & Tools (Ctrl+K / ⌘K)")
        self.cmd_bar_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_PANEL_CONTAINER};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 4px 12px;
                font-size: 11px;
                color: {COLOR_TEXT_SECONDARY};
                text-align: left;
                min-width: 180px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HIGH};
                border-color: rgba(208, 188, 255, 0.40);
                color: #ffffff;
            }}
        """)
        self.cmd_bar_btn.clicked.connect(self.command_palette_triggered)
        center_layout.addWidget(self.cmd_bar_btn)

        # Segmented Workspace Switcher: Canvas | Timeline | Nodes
        ws_frame = QFrame()
        ws_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_CONTAINER};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 2px;
            }}
        """)
        ws_layout = QHBoxLayout(ws_frame)
        ws_layout.setContentsMargins(2, 2, 2, 2)
        ws_layout.setSpacing(2)

        self.ws_group = QButtonGroup(self)
        self.ws_group.setExclusive(True)

        self.btn_ws_canvas = QPushButton("Canvas")
        self.btn_ws_canvas.setCheckable(True)
        self.btn_ws_canvas.setChecked(True)
        self.btn_ws_canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ws_group.addButton(self.btn_ws_canvas)

        self.btn_ws_timeline = QPushButton("Timeline")
        self.btn_ws_timeline.setCheckable(True)
        self.btn_ws_timeline.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ws_group.addButton(self.btn_ws_timeline)

        self.btn_ws_nodes = QPushButton("Nodes")
        self.btn_ws_nodes.setCheckable(True)
        self.btn_ws_nodes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ws_group.addButton(self.btn_ws_nodes)

        ws_btn_style = f"""
            QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 500;
                color: {COLOR_TEXT_SECONDARY};
            }}
            QPushButton:hover {{
                color: {COLOR_TEXT_PRIMARY};
                background-color: rgba(255, 255, 255, 0.05);
            }}
            QPushButton:checked {{
                background-color: {COLOR_SURFACE_HIGH};
                border-color: rgba(208, 188, 255, 0.35);
                color: {COLOR_ACCENT};
                font-weight: 700;
            }}
        """
        for b in (self.btn_ws_canvas, self.btn_ws_timeline, self.btn_ws_nodes):
            b.setStyleSheet(ws_btn_style)

        self.btn_ws_canvas.clicked.connect(lambda: self.workspace_changed.emit("canvas"))
        self.btn_ws_timeline.clicked.connect(lambda: self.workspace_changed.emit("timeline"))
        self.btn_ws_nodes.clicked.connect(lambda: self.workspace_changed.emit("nodes"))

        ws_layout.addWidget(self.btn_ws_canvas)
        ws_layout.addWidget(self.btn_ws_timeline)
        ws_layout.addWidget(self.btn_ws_nodes)
        center_layout.addWidget(ws_frame)

        layout.addLayout(center_layout)
        layout.addStretch()

        # ── Zone 3: Right Zone (Undo/Redo, Onion, Preview, Export, Settings, AI) ──
        right_layout = QHBoxLayout()
        right_layout.setSpacing(6)

        # Undo / Redo
        self.btn_undo = QToolButton()
        self.btn_undo.setText("↶")
        self.btn_undo.setToolTip("Undo (Ctrl+Z / ⌘Z)")
        self.btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self.undo_triggered)
        right_layout.addWidget(self.btn_undo)

        self.btn_redo = QToolButton()
        self.btn_redo.setText("↷")
        self.btn_redo.setToolTip("Redo (Ctrl+Y / ⇧⌘Z)")
        self.btn_redo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self.redo_triggered)
        right_layout.addWidget(self.btn_redo)

        # Onion Skin Toggle Pill
        self.btn_onion = QPushButton("Onion Skin")
        self.btn_onion.setCheckable(True)
        self.btn_onion.setChecked(False)
        self.btn_onion.setToolTip("Toggle Onion Skin (O)")
        self.btn_onion.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_onion.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SURFACE_ELEVATED};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HOVER};
            }}
            QPushButton:checked {{
                background-color: rgba(76, 215, 246, 0.15);
                border-color: {COLOR_SECONDARY};
                color: {COLOR_SECONDARY};
                font-weight: 600;
            }}
        """)
        self.btn_onion.toggled.connect(self.onion_skin_toggled)
        right_layout.addWidget(self.btn_onion)

        # Preview Trigger Button
        self.btn_preview = QPushButton("▶ Preview")
        self.btn_preview.setToolTip("Preview Animation Playback (Space)")
        self.btn_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SURFACE_ELEVATED};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                color: {COLOR_ACCENT};
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HOVER};
                border-color: {COLOR_ACCENT};
            }}
        """)
        self.btn_preview.clicked.connect(self.preview_triggered)
        right_layout.addWidget(self.btn_preview)

        # Export CTA Button (Obsidian Hero Glow)
        self.btn_export = QPushButton("Export ⌘E")
        self.btn_export.setToolTip("Export Animation to MP4, GIF, or Sequence (Ctrl+E)")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_CONTAINER};
                color: #ffffff;
                font-size: 11px;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: #10131D;
            }}
        """)
        self.btn_export.clicked.connect(self.export_triggered)
        right_layout.addWidget(self.btn_export)

        # Settings Button
        self.btn_settings = QToolButton()
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("AI & Project Settings")
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(self.settings_triggered)
        right_layout.addWidget(self.btn_settings)

        # AI Assistant Toggle Button
        self.btn_ai = QPushButton("✨ AI")
        self.btn_ai.setCheckable(True)
        self.btn_ai.setChecked(True)
        self.btn_ai.setToolTip("Toggle AI Assistant Panel (Ctrl+Shift+A)")
        self.btn_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ai.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_SURFACE_ELEVATED};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
                color: {COLOR_ACCENT};
            }}
            QPushButton:hover {{
                background-color: {COLOR_SURFACE_HOVER};
                border-color: {COLOR_ACCENT};
            }}
            QPushButton:checked {{
                background-color: rgba(208, 188, 255, 0.20);
                border-color: {COLOR_ACCENT};
                color: #ffffff;
                font-weight: 700;
            }}
        """)
        self.btn_ai.toggled.connect(self.ai_assistant_toggled)
        right_layout.addWidget(self.btn_ai)

        layout.addLayout(right_layout)
        self.addWidget(central_widget)

    # ── State Updating Helpers ──

    def set_undo_enabled(self, enabled: bool) -> None:
        self.btn_undo.setEnabled(enabled)

    def set_redo_enabled(self, enabled: bool) -> None:
        self.btn_redo.setEnabled(enabled)

    def set_playing(self, is_playing: bool) -> None:
        if is_playing:
            self.btn_preview.setText("⏸ Pause")
            self.btn_preview.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT_CONTAINER};
                    color: #ffffff;
                    border: 1px solid {COLOR_ACCENT};
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            self.btn_preview.setText("▶ Preview")
            self.btn_preview.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_SURFACE_ELEVATED};
                    border: 1px solid {COLOR_GLASS_BORDER};
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    color: {COLOR_ACCENT};
                }}
                QPushButton:hover {{
                    background-color: {COLOR_SURFACE_HOVER};
                    border-color: {COLOR_ACCENT};
                }}
            """)

    def set_project_info(self, name: str, modified: bool, aspect_ratio_str: str = "16:9") -> None:
        self.project_name_lbl.setText(name or "Untitled Project")
        self.mod_badge.setText("— Edited" if modified else "— Saved")
        self.mod_badge.setStyleSheet(
            f"font-size: 10px; color: {COLOR_ACCENT if modified else COLOR_TEXT_MUTED};"
        )
        self.format_btn.setText(aspect_ratio_str or "16:9")

    def set_onion_skin_active(self, active: bool, count: int = 1) -> None:
        self.btn_onion.blockSignals(True)
        self.btn_onion.setChecked(active)
        self.btn_onion.setText(f"Onion: {count}F" if active else "Onion Skin")
        self.btn_onion.blockSignals(False)
        self.act_onion.blockSignals(True)
        self.act_onion.setChecked(active)
        self.act_onion.blockSignals(False)

    def set_playing_state(self, is_playing: bool) -> None:
        self.set_playing(is_playing)

    def set_onion_skin_checked(self, checked: bool) -> None:
        self.set_onion_skin_active(checked)

    def set_canvas_format_label(self, label: str) -> None:
        text = label or "16:9"
        self.format_btn.setText(text)
        self.act_format.setText(f"Format: {text}")

    def set_fps(self, fps: int) -> None:
        self._fps = fps

    def set_ai_assistant_checked(self, checked: bool) -> None:
        self.btn_ai.blockSignals(True)
        self.btn_ai.setChecked(checked)
        self.btn_ai.blockSignals(False)
        self.act_ai_chat.blockSignals(True)
        self.act_ai_chat.setChecked(checked)
        self.act_ai_chat.blockSignals(False)

    def set_workspace(self, mode: str) -> None:
        self.btn_ws_canvas.setChecked(mode == "canvas")
        self.btn_ws_timeline.setChecked(mode == "timeline")
        self.btn_ws_nodes.setChecked(mode == "nodes")
