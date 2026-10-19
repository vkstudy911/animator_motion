"""Nodes Workspace placeholder for AI Doodle Studio (Studio Obsidian).

Provides a polished, professional empty state for the future procedural
motion graphics, shader effects, and node compositing pipeline.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_CONTAINER,
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


class NodesWorkspaceWidget(QWidget):
    """Empty state canvas for future Nodes & Compositing Graph."""

    return_to_canvas_requested = Signal()
    return_to_canvas = return_to_canvas_requested

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("node_card")
        card.setFixedWidth(460)
        card.setStyleSheet(f"""
            QFrame#node_card {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Node Graph Icon Container
        icon_frame = QFrame()
        icon_frame.setFixedSize(64, 64)
        icon_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_PANEL_CONTAINER};
                border: 1px solid rgba(208, 188, 255, 0.40);
                border-radius: 16px;
            }}
        """)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_lbl = QLabel("🎛️")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        icon_layout.addWidget(icon_lbl)
        card_layout.addWidget(icon_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title_lbl = QLabel("Nodes & Compositing Graph")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLOR_TEXT_PRIMARY}; background: transparent; border: none;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title_lbl)

        # Status Tag
        tag_lbl = QLabel("COMING SOON IN STUDIO OBSIDIAN")
        tag_lbl.setStyleSheet(f"""
            QLabel {{
                background: rgba(208, 188, 255, 0.15);
                color: {COLOR_ACCENT};
                border: 1px solid rgba(208, 188, 255, 0.35);
                border-radius: 10px;
                padding: 3px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.05em;
            }}
        """)
        tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(tag_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # Description
        desc_lbl = QLabel(
            "Node-based procedural animation, vector motion path warping, "
            "and generative shader graphs are currently in active development. "
            "Use the Canvas or Timeline workspaces for direct drawing and cel animation."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setStyleSheet(f"font-size: 12px; color: {COLOR_TEXT_MUTED}; line-height: 1.4; background: transparent; border: none;")
        card_layout.addWidget(desc_lbl)

        # Action Button
        return_btn = QPushButton("Return to Canvas Workspace")
        return_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_CONTAINER};
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                margin-top: 8px;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: #10131D;
            }}
        """)
        return_btn.clicked.connect(self.return_to_canvas_requested.emit)
        card_layout.addWidget(return_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(card)

    def paintEvent(self, event) -> None:
        """Render subtle background dot matrix grid."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(11, 14, 24))

        # Dot matrix grid
        painter.setPen(QPen(QColor(255, 255, 255, 12), 1.5))
        grid_size = 28
        w, h = self.width(), self.height()
        for x in range(0, w, grid_size):
            for y in range(0, h, grid_size):
                painter.drawPoint(x, y)
        painter.end()
