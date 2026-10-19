"""AI Chatbot panel for AI Doodle Studio.

Provides an interactive creative assistant dock with:
- Connection status indicator (Offline / Connected / Error)
- Settings configuration dialog launcher
- Scrollable chat history with distinct user and assistant message bubbles
- Quick action chips for common tracking and animation tasks
- Action Plan Cards with Preview, Apply, Regenerate, and Cancel controls
- Multiline prompt input with Shift+Enter for newlines and Enter to send
- Media attachment support and cancellation of active requests
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QByteArray, QEvent, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ai.actions import AIJob, validate_action_plan
from app.ai.provider import AIResponse
from app.ai.service import AIService, ConnectionStatus
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_SUBTLE,
    COLOR_DANGER,
    COLOR_GLASS_BG,
    COLOR_GLASS_BORDER,
    COLOR_GLASS_BORDER_HOVER,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)

# Modern SVG Icons
SVG_SPARKLE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="#E76F51" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/>'
    '</svg>'
)

SVG_GEAR = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="3"/>'
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z"/>'
    '</svg>'
)

SVG_CLOSE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="18" y1="6" x2="6" y2="18"/>'
    '<line x1="6" y1="6" x2="18" y2="18"/>'
    '</svg>'
)

SVG_PAPERCLIP = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>'
    '</svg>'
)

SVG_SEND = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="22" y1="2" x2="11" y2="13"/>'
    '<polygon points="22 2 15 22 11 13 2 9 22 2"/>'
    '</svg>'
)


def _render_svg_icon(svg_str: str, size: int = 16, color: Optional[str] = None) -> QIcon:
    if color:
        svg_str = svg_str.replace('stroke="currentColor"', f'stroke="{color}"')
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class ActionPlanCardWidget(QFrame):
    """Interactive card displaying structured AI editing plans with Preview, Apply, Regenerate, Cancel."""

    preview_clicked = Signal(object)     # AIJob
    apply_clicked = Signal(object)       # AIJob
    regenerate_clicked = Signal(object)  # AIJob
    cancel_clicked = Signal(object)      # AIJob

    def __init__(self, job: AIJob, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.job = job
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            ActionPlanCardWidget {{
                background-color: rgba(35, 35, 42, 0.95);
                border: 1px solid {COLOR_ACCENT};
                border-radius: 10px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Plan Header
        top_row = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(_render_svg_icon(SVG_SPARKLE, 16).pixmap(16, 16))
        top_row.addWidget(icon_lbl)

        title_lbl = QLabel("AI Action Plan")
        title_lbl.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {COLOR_ACCENT};")
        top_row.addWidget(title_lbl)
        top_row.addStretch()

        track_tag = QLabel(self.job.layer_track_name or "Project")
        track_tag.setStyleSheet("""
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            color: #EDE8E3;
        """)
        top_row.addWidget(track_tag)
        layout.addLayout(top_row)

        # Summary text
        summary_lbl = QLabel(self.job.summary)
        summary_lbl.setWordWrap(True)
        summary_lbl.setStyleSheet("font-size: 11px; color: #EDE8E3; line-height: 1.3;")
        layout.addWidget(summary_lbl)

        # Details table/list
        if self.job.action_steps:
            steps_box = QFrame()
            steps_box.setStyleSheet("background: rgba(0, 0, 0, 0.30); border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.05);")
            steps_layout = QVBoxLayout(steps_box)
            steps_layout.setSpacing(4)
            steps_layout.setContentsMargins(8, 8, 8, 8)

            for step in self.job.action_steps:
                step_lbl = QLabel(f"• {step}")
                step_lbl.setWordWrap(True)
                step_lbl.setStyleSheet("font-size: 11px; color: #EDE8E3; background: transparent; border: none;")
                steps_layout.addWidget(step_lbl)
            layout.addWidget(steps_box)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255, 255, 255, 0.06);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.12);
            }}
        """)
        self.preview_btn.clicked.connect(lambda: self.preview_clicked.emit(self.job))
        btn_row.addWidget(self.preview_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setToolTip("Execute changes onto a dedicated layer track")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                border: none;
                border-radius: 5px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: 600;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
        """)
        self.apply_btn.clicked.connect(lambda: self.apply_clicked.emit(self.job))
        btn_row.addWidget(self.apply_btn)

        btn_row.addStretch()

        self.regen_btn = QPushButton("Regen")
        self.regen_btn.setToolTip("Regenerate this action plan")
        self.regen_btn.setStyleSheet("font-size: 10px; color: #A8A29E; background: transparent; border: none;")
        self.regen_btn.clicked.connect(lambda: self.regenerate_clicked.emit(self.job))
        btn_row.addWidget(self.regen_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setToolTip("Dismiss plan without modifying project")
        self.cancel_btn.setStyleSheet("font-size: 10px; color: #78716C; background: transparent; border: none;")
        self.cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self.job))
        btn_row.addWidget(self.cancel_btn)

        layout.addLayout(btn_row)


class ErrorBubbleWidget(QFrame):
    """In-chat error bubble with clear explanation, error icon, Retry button, and optional Settings action."""

    retry_clicked = Signal(str, object)  # (retry_prompt, retry_media)
    settings_clicked = Signal()

    def __init__(
        self,
        error_text: str,
        retry_prompt: str = "",
        retry_media: Optional[str] = None,
        show_settings_btn: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.error_text = error_text
        self.retry_prompt = retry_prompt
        self.retry_media = retry_media
        self._setup_ui(show_settings_btn)

    def _setup_ui(self, show_settings_btn: bool) -> None:
        self.setStyleSheet(f"""
            ErrorBubbleWidget {{
                background-color: rgba(231, 111, 81, 0.10);
                border: 1px solid rgba(231, 111, 81, 0.40);
                border-radius: 8px;
                margin-right: 20px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        err_lbl = QLabel(f"⚠️ {self.error_text}")
        err_lbl.setWordWrap(True)
        err_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        err_lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_PRIMARY}; line-height: 1.3;")
        layout.addWidget(err_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.retry_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
        """)
        self.retry_btn.clicked.connect(lambda: self.retry_clicked.emit(self.retry_prompt, self.retry_media))
        btn_row.addWidget(self.retry_btn)

        if show_settings_btn:
            self.settings_btn = QPushButton("AI Settings")
            self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.settings_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.08);
                    border: 1px solid {COLOR_GLASS_BORDER};
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    color: {COLOR_TEXT_PRIMARY};
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.15);
                }}
            """)
            self.settings_btn.clicked.connect(self.settings_clicked.emit)
            btn_row.addWidget(self.settings_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)


class ChatPromptEdit(QPlainTextEdit):
    """Custom multiline prompt editor where Enter sends and Shift+Enter adds a newline."""

    return_pressed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setPlaceholderText("Ask about the project or describe an animation…")
        self.setMaximumHeight(88)
        self.setMinimumHeight(38)
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 11px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPlainTextEdit:focus {{
                border-color: {COLOR_ACCENT};
                background-color: rgba(255, 255, 255, 0.08);
            }}
        """)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.return_pressed.emit()
                event.accept()
        else:
            super().keyPressEvent(event)


class AIChatWidget(QWidget):
    """Right-side collapsible AI Assistant chat dock."""

    close_requested = Signal()
    settings_requested = Signal()
    apply_job_requested = Signal(object)    # AIJob
    preview_job_requested = Signal(object)  # AIJob

    def __init__(self, ai_service: AIService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.ai_service = ai_service
        self._attached_media_path: Optional[str] = None
        self._current_context_provider = None
        self._last_prompt: str = ""
        self._last_media: Optional[str] = None
        self._setup_ui()
        self._connect_service_signals()

    def set_context_provider(self, provider_callable) -> None:
        """Assign callback that returns a dict of current project state context."""
        self._current_context_provider = provider_callable

    def _setup_ui(self) -> None:
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"""
            AIChatWidget {{
                background-color: {COLOR_GLASS_BG};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # ── 1. Header Bar ──
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        # Assistant Sparkle Icon + Title
        icon_lbl = QLabel()
        icon_lbl.setPixmap(_render_svg_icon(SVG_SPARKLE, 16).pixmap(16, 16))
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("AI Assistant")
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #EDE8E3;")
        header_layout.addWidget(title_lbl)

        # Status indicator dot
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #E9C46A; font-size: 12px; margin-left: 2px;")
        self.status_dot.setToolTip("Offline Mode")
        header_layout.addWidget(self.status_dot)

        header_layout.addStretch()

        # Settings Button
        self.settings_btn = QToolButton()
        self.settings_btn.setIcon(_render_svg_icon(SVG_GEAR, 14))
        self.settings_btn.setToolTip("AI Provider Settings")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 3px;
                color: {COLOR_TEXT_SECONDARY};
            }}
            QToolButton:hover {{
                background: rgba(255, 255, 255, 0.08);
                border-color: {COLOR_GLASS_BORDER};
                color: #ffffff;
            }}
        """)
        self.settings_btn.clicked.connect(self.settings_requested)
        header_layout.addWidget(self.settings_btn)

        # Close/Collapse Button
        self.close_btn = QToolButton()
        self.close_btn.setIcon(_render_svg_icon(SVG_CLOSE, 14))
        self.close_btn.setToolTip("Close AI Assistant")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 3px;
                color: {COLOR_TEXT_SECONDARY};
            }}
            QToolButton:hover {{
                background: rgba(255, 255, 255, 0.08);
                border-color: {COLOR_GLASS_BORDER};
                color: #ffffff;
            }}
        """)
        self.close_btn.clicked.connect(self.close_requested)
        header_layout.addWidget(self.close_btn)

        main_layout.addLayout(header_layout)

        # Subtle separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: none; border-top: 1px solid {COLOR_GLASS_BORDER};")
        main_layout.addWidget(sep)

        # ── 2. Scrollable Chat History ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setContentsMargins(0, 4, 0, 4)
        self.messages_layout.setSpacing(10)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_container)
        main_layout.addWidget(self.scroll_area, 1)

        # ── 3. Quick Action Chips Flow ──
        chips_frame = QFrame()
        chips_frame.setStyleSheet("background: transparent;")
        chips_layout = QVBoxLayout(chips_frame)
        chips_layout.setContentsMargins(0, 0, 0, 0)
        chips_layout.setSpacing(4)

        chips_header = QLabel("Quick Actions:")
        chips_header.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLOR_TEXT_MUTED}; background: transparent; border: none;")
        chips_layout.addWidget(chips_header)

        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setFixedHeight(62)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chips_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 4px;
                background: transparent;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 2px;
            }
        """)

        chips_inner = QWidget()
        chips_inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(chips_inner)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        inner_layout.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(5)
        row2 = QHBoxLayout()
        row2.setSpacing(5)

        chip_items = [
            ("Track Point", "Track selected point", row1),
            ("Track Hand", "Track hand", row1),
            ("Track Face", "Track face", row1),
            ("Motion Trail", "Add motion trail", row1),
            ("Glowing Eyes", "Add glowing eyes", row2),
            ("Captions", "Add captions", row2),
            ("Animation Ideas", "Animation ideas", row2),
            ("Tool Help", "Help with tools", row2),
        ]

        for label, prompt_val, target_row in chip_items:
            chip_btn = QPushButton(label)
            chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chip_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 11px;
                    padding: 3px 9px;
                    font-size: 10px;
                    font-weight: 500;
                    color: {COLOR_TEXT_SECONDARY};
                }}
                QPushButton:hover {{
                    background: rgba(231, 111, 81, 0.18);
                    border-color: {COLOR_ACCENT};
                    color: #ffffff;
                }}
            """)
            chip_btn.clicked.connect(lambda _, p=prompt_val: self._on_chip_clicked(p))
            target_row.addWidget(chip_btn)

        row1.addStretch()
        row2.addStretch()
        inner_layout.addLayout(row1)
        inner_layout.addLayout(row2)
        chips_scroll.setWidget(chips_inner)
        chips_layout.addWidget(chips_scroll)
        main_layout.addWidget(chips_frame)

        # ── 4. Attachment preview indicator ──
        self.attach_preview_lbl = QLabel("")
        self.attach_preview_lbl.setVisible(False)
        self.attach_preview_lbl.setStyleSheet(f"""
            font-size: 10px;
            color: {COLOR_ACCENT};
            background: rgba(231, 111, 81, 0.12);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        main_layout.addWidget(self.attach_preview_lbl)

        # ── 5. Input Area ──
        input_box = QFrame()
        input_box.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.03);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(4)

        self.prompt_edit = ChatPromptEdit()
        self.prompt_edit.return_pressed.connect(self.send_message)
        input_layout.addWidget(self.prompt_edit)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)

        # Attach media button
        self.attach_btn = QToolButton()
        self.attach_btn.setIcon(_render_svg_icon(SVG_PAPERCLIP, 14))
        self.attach_btn.setToolTip("Attach reference image or frame")
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setStyleSheet(f"""
            QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 5px;
                padding: 4px;
                color: {COLOR_TEXT_SECONDARY};
            }}
            QToolButton:hover {{
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }}
        """)
        self.attach_btn.clicked.connect(self._on_attach_media)
        controls_row.addWidget(self.attach_btn)

        # Status / Busy label
        self.busy_label = QLabel("")
        self.busy_label.setStyleSheet("font-size: 10px; color: #A8A29E;")
        controls_row.addWidget(self.busy_label)
        controls_row.addStretch()

        # Cancel button (shown while processing)
        self.cancel_request_btn = QPushButton("Cancel")
        self.cancel_request_btn.setVisible(False)
        self.cancel_request_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(217, 83, 79, 0.20);
                border: 1px solid {COLOR_DANGER};
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background: rgba(217, 83, 79, 0.40);
            }}
        """)
        self.cancel_request_btn.clicked.connect(self._on_cancel_request)
        controls_row.addWidget(self.cancel_request_btn)

        # Send Button
        self.send_btn = QPushButton()
        self.send_btn.setIcon(_render_svg_icon(SVG_SEND, 14, color="#ffffff"))
        self.send_btn.setText(" Send")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                color: #ffffff;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_HOVER};
            }}
            QPushButton:disabled {{
                background-color: rgba(255, 255, 255, 0.05);
                color: #55534E;
            }}
        """)
        self.send_btn.clicked.connect(lambda: self.send_message())
        controls_row.addWidget(self.send_btn)

        input_layout.addLayout(controls_row)
        main_layout.addWidget(input_box)

        # Initial Welcome Message
        self._add_assistant_message(
            "Hi, I can help you create, track, and animate effects. Describe what you want to make."
        )

        # Sync initial status
        self._update_status_indicator(self.ai_service.status.value)

    def _connect_service_signals(self) -> None:
        self.ai_service.status_changed.connect(self._update_status_indicator)
        self.ai_service.request_started.connect(self._on_request_started)
        self.ai_service.response_received.connect(self._on_response_received)
        self.ai_service.error_occurred.connect(self._on_error_occurred)

    def _update_status_indicator(self, status_val: str) -> None:
        if status_val == ConnectionStatus.CONNECTED.value:
            self.status_dot.setStyleSheet("color: #2A9D8F; font-size: 12px;")
            self.status_dot.setToolTip("Connected to AI Provider")
        elif status_val == ConnectionStatus.ERROR.value:
            self.status_dot.setStyleSheet("color: #E76F51; font-size: 12px;")
            self.status_dot.setToolTip("AI Provider Connection Error")
        else:
            self.status_dot.setStyleSheet("color: #E9C46A; font-size: 12px;")
            self.status_dot.setToolTip("Offline Mode (Deterministic reasoning active)")

    def _on_chip_clicked(self, chip_text: str) -> None:
        self.prompt_edit.setPlainText(chip_text)
        self.send_message()

    def _on_attach_media(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Reference Media",
            "",
            "Images & Videos (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov);;All Files (*)",
        )
        if path:
            self._attached_media_path = path
            fname = os.path.basename(path)
            self.attach_preview_lbl.setText(f"📎 Attached: {fname}")
            self.attach_preview_lbl.setVisible(True)

    def send_message(self, prompt_text: Optional[str] = None) -> None:
        """Unified message send handler for Enter key, Send button, quick chips, and Retry."""
        text = (prompt_text if prompt_text is not None else self.prompt_edit.toPlainText()).strip()
        if not text and not self._attached_media_path:
            return

        if prompt_text is None:
            self.prompt_edit.clear()

        # Cache for retry
        self._last_prompt = text
        self._last_media = self._attached_media_path

        # Immediately add user message
        display_msg = text or f"[Attached media: {os.path.basename(self._attached_media_path or '')}]"
        self._add_user_message(display_msg)

        media_to_send = self._attached_media_path
        self._attached_media_path = None
        self.attach_preview_lbl.setVisible(False)

        # Show assistant typing state
        self._set_typing_state(True)

        # Validate provider is configured
        if not self.ai_service.is_configured():
            self._reset_typing_state()
            self._add_error_bubble(
                "Connect an AI provider in AI Assistant Settings to start chatting.",
                retry_prompt=text,
                retry_media=media_to_send,
                show_settings_btn=True,
            )
            return

        ctx = self._current_context_provider() if self._current_context_provider else {}
        self.ai_service.send_prompt(
            prompt=text,
            context=ctx,
            media_path=media_to_send,
        )

    def _on_retry(self, prompt: str, media_path: Optional[str] = None) -> None:
        if media_path:
            self._attached_media_path = media_path
        self.send_message(prompt)

    def _set_typing_state(self, is_typing: bool) -> None:
        if is_typing:
            self.busy_label.setText("Thinking...")
            self.send_btn.setEnabled(False)
            self.cancel_request_btn.setVisible(True)
        else:
            self._reset_typing_state()

    def _reset_typing_state(self) -> None:
        self.busy_label.setText("")
        self.send_btn.setEnabled(True)
        self.cancel_request_btn.setVisible(False)

    def _on_cancel_request(self) -> None:
        self.ai_service.cancel_current_request()
        self._reset_typing_state()

    def _on_request_started(self) -> None:
        self._set_typing_state(True)

    def _on_response_received(self, response: AIResponse) -> None:
        self._reset_typing_state()

        if response.is_action and response.action_plan:
            ctx = self._current_context_provider() if self._current_context_provider else {}
            total_f = ctx.get("frame_count", 1)
            ok, err, job = validate_action_plan(response.action_plan, total_frames=total_f)
            if ok and job:
                self._add_action_plan_card(job)
                return

        resp_text = (response.text or "").strip()
        if not resp_text:
            resp_text = "The provider returned an empty response. Try again or change the model."
        self._add_assistant_message(resp_text)

    def _on_error_occurred(self, err_text: str) -> None:
        self._reset_typing_state()
        clean_err = err_text.strip() or "An unexpected error occurred while communicating with the AI provider."
        self._add_error_bubble(
            clean_err,
            retry_prompt=self._last_prompt,
            retry_media=self._last_media,
        )

    def _add_user_message(self, text: str) -> None:
        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_ACCENT_SUBTLE};
                border: 1px solid rgba(231, 111, 81, 0.40);
                border-radius: 8px;
                padding: 8px;
                margin-left: 28px;
            }}
        """)
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(8, 6, 8, 6)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 11px; color: #FFFFFF;")
        layout.addWidget(lbl)

        # Insert above bottom stretch
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _add_assistant_message(self, text: str) -> None:
        bubble = QFrame()
        bubble.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 8px;
                margin-right: 20px;
            }}
        """)
        layout = QVBoxLayout(bubble)
        layout.setContentsMargins(8, 6, 8, 6)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_PRIMARY}; line-height: 1.4;")
        layout.addWidget(lbl)

        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _add_error_bubble(
        self,
        text: str,
        retry_prompt: str = "",
        retry_media: Optional[str] = None,
        show_settings_btn: bool = False,
    ) -> None:
        bubble = ErrorBubbleWidget(
            error_text=text,
            retry_prompt=retry_prompt,
            retry_media=retry_media,
            show_settings_btn=show_settings_btn,
        )
        bubble.retry_clicked.connect(self._on_retry)
        bubble.settings_clicked.connect(self.settings_requested.emit)

        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _add_action_plan_card(self, job: AIJob) -> None:
        card = ActionPlanCardWidget(job)
        card.preview_clicked.connect(self.preview_job_requested)
        card.apply_clicked.connect(self._on_apply_job)
        card.regenerate_clicked.connect(self._on_regenerate_job)
        card.cancel_clicked.connect(lambda j: self._remove_card(card))

        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, card)
        self._scroll_to_bottom()

    def _on_apply_job(self, job: AIJob) -> None:
        self.apply_job_requested.emit(job)
        self._add_assistant_message(f"✓ Applied '{job.layer_track_name}' across frames {job.frame_range[0]}–{job.frame_range[1]}. You can undo this change with Ctrl+Z.")

    def _on_regenerate_job(self, job: AIJob) -> None:
        self.ai_service.send_prompt(
            prompt=f"Regenerate action plan for: {job.user_prompt or job.summary}",
            context=self._current_context_provider() if self._current_context_provider else {},
        )

    def _remove_card(self, card: QWidget) -> None:
        card.setVisible(False)
        self.messages_layout.removeWidget(card)
        card.deleteLater()

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            15,
            lambda: self.scroll_area.verticalScrollBar().setValue(
                self.scroll_area.verticalScrollBar().maximum()
            ),
        )
