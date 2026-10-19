"""Command Palette (Cmd/Ctrl+K) modal dialog for AI Doodle Studio (Studio Obsidian).

Provides instant search and keyboard execution across all creative tools,
canvas transforms, animation transport, frame editing, and project commands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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


@dataclass
class PaletteCommand:
    id: str
    title: str
    category: str
    shortcut: str
    callback: Callable[[], None]
    keywords: str = ""


class CommandPaletteItemWidget(QWidget):
    """Visual list row for a palette command."""

    def __init__(self, cmd: PaletteCommand, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.cmd = cmd
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Category Badge
        cat_badge = QLabel(cmd.category.upper())
        cat_badge.setStyleSheet(f"""
            QLabel {{
                background: {COLOR_SURFACE_HIGH};
                color: {COLOR_TEXT_MUTED};
                font-size: 9px;
                font-weight: 700;
                padding: 2px 6px;
                border-radius: 4px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }}
        """)
        layout.addWidget(cat_badge)

        # Title
        title_lbl = QLabel(cmd.title)
        title_lbl.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {COLOR_TEXT_PRIMARY};")
        layout.addWidget(title_lbl, 1)

        # Shortcut Kbd Badge
        if cmd.shortcut:
            kbd = QLabel(cmd.shortcut)
            kbd.setStyleSheet(f"""
                QLabel {{
                    background: {COLOR_PANEL_CONTAINER};
                    color: {COLOR_ACCENT};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 2px 6px;
                    border-radius: 4px;
                    border: 1px solid rgba(208, 188, 255, 0.25);
                }}
            """)
            layout.addWidget(kbd)


class CommandPaletteDialog(QDialog):
    """Quick Actions & Tools Command Bar modal."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Actions & Tools")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(540, 380)

        self.commands: List[PaletteCommand] = []
        self._filtered_commands: List[PaletteCommand] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        container = QFrame(self)
        container.setObjectName("container")
        container.setStyleSheet(f"""
            QFrame#container {{
                background-color: rgba(24, 27, 37, 0.98);
                border: 1px solid rgba(208, 188, 255, 0.35);
                border-radius: 12px;
            }}
        """)
        dlg_layout = QVBoxLayout(self)
        dlg_layout.setContentsMargins(6, 6, 6, 6)
        dlg_layout.addWidget(container)

        inner = QVBoxLayout(container)
        inner.setContentsMargins(12, 12, 12, 12)
        inner.setSpacing(10)

        # Search Bar
        search_box = QFrame()
        search_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_PANEL_CONTAINER};
                border: 1px solid {COLOR_GLASS_BORDER};
                border-radius: 8px;
                padding: 2px 8px;
            }}
        """)
        search_layout = QHBoxLayout(search_box)
        search_layout.setContentsMargins(4, 4, 4, 4)
        search_layout.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 13px; color: #D0BCFF;")
        search_layout.addWidget(search_icon)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search commands, tools, frames, or actions (Esc to close)...")
        self.search_edit.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                font-size: 12px;
                color: {COLOR_TEXT_PRIMARY};
            }}
        """)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit, 1)
        inner.addWidget(search_box)

        # Command list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                border-radius: 6px;
                margin: 1px 0;
            }}
            QListWidget::item:selected {{
                background: rgba(160, 120, 255, 0.18);
                border: 1px solid rgba(208, 188, 255, 0.40);
            }}
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_activated)
        inner.addWidget(self.list_widget, 1)

        # Footer hints
        footer = QHBoxLayout()
        hint = QLabel("↑↓ Navigate  •  Enter Select  •  Esc Close")
        hint.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_MUTED};")
        footer.addWidget(hint)
        footer.addStretch()
        inner.addLayout(footer)

    def register_command(
        self,
        cmd_id: str,
        title: str,
        category: str,
        shortcut: str,
        callback: Callable[[], None],
        keywords: str = "",
    ) -> None:
        """Register an executable command into the palette registry."""
        self.commands.append(
            PaletteCommand(
                id=cmd_id,
                title=title,
                category=category,
                shortcut=shortcut,
                callback=callback,
                keywords=keywords,
            )
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.search_edit.clear()
        self.search_edit.setFocus()
        self._populate_list(self.commands)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self._execute_current_selection()
        elif event.key() == Qt.Key.Key_Down:
            cur = self.list_widget.currentRow()
            if cur < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(cur + 1)
        elif event.key() == Qt.Key.Key_Up:
            cur = self.list_widget.currentRow()
            if cur > 0:
                self.list_widget.setCurrentRow(cur - 1)
        else:
            super().keyPressEvent(event)

    def _on_search_changed(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._populate_list(self.commands)
            return

        filtered = [
            c
            for c in self.commands
            if q in c.title.lower() or q in c.category.lower() or q in c.keywords.lower() or q in c.shortcut.lower()
        ]
        self._populate_list(filtered)

    def _populate_list(self, cmds: List[PaletteCommand]) -> None:
        self.list_widget.clear()
        self._filtered_commands = cmds
        for cmd in cmds:
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 36))
            row_widget = CommandPaletteItemWidget(cmd)
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)

        if cmds:
            self.list_widget.setCurrentRow(0)

    def _execute_current_selection(self) -> None:
        cur_row = self.list_widget.currentRow()
        if 0 <= cur_row < len(self._filtered_commands):
            cmd = self._filtered_commands[cur_row]
            self.accept()
            cmd.callback()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        self._execute_current_selection()
