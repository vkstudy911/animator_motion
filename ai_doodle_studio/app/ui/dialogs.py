"""Dialog windows for project configuration, media export, and application information.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.canvas_format import (
    CANVAS_PRESETS,
    CanvasPreset,
    ResizeMode,
    get_orientation,
    get_ratio_label,
)
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_GLASS_BG,
    COLOR_GLASS_BORDER,
    COLOR_SURFACE_ELEVATED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
)


class PresetCardWidget(QFrame):
    """Clickable visual card representing a canvas format preset."""

    clicked = Signal(object)  # CanvasPreset

    def __init__(self, preset: CanvasPreset, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.preset = preset
        self.selected = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(148, 86)
        self._setup_ui()
        self._update_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.preview_box = QFrame()
        pw, ph = self._calc_preview_dims()
        self.preview_box.setFixedSize(pw, ph)
        self.preview_box.setStyleSheet(
            "border: 1px solid rgba(255, 255, 255, 0.4); "
            "background: rgba(255, 255, 255, 0.08); "
            "border-radius: 2px;"
        )
        top_row.addWidget(self.preview_box, 0, Qt.AlignmentFlag.AlignVCenter)

        self.name_label = QLabel(self.preset.name)
        self.name_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #EDE8E3;")
        self.name_label.setWordWrap(True)
        top_row.addWidget(self.name_label, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(top_row)

        self.dims_label = QLabel(f"{self.preset.width} × {self.preset.height}")
        self.dims_label.setStyleSheet("font-size: 10px; color: #A8A29E;")
        layout.addWidget(self.dims_label)

        sub_label = QLabel(f"{self.preset.ratio} • {self.preset.category}")
        sub_label.setStyleSheet("font-size: 9px; color: #78716C;")
        layout.addWidget(sub_label)

    def _calc_preview_dims(self) -> tuple[int, int]:
        max_dim = 24
        w, h = self.preset.width, self.preset.height
        if w >= h:
            pw = max_dim
            ph = max(8, int(max_dim * (h / w)))
        else:
            ph = max_dim
            pw = max(8, int(max_dim * (w / h)))
        return (pw, ph)

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._update_style()

    def _update_style(self) -> None:
        if self.selected:
            self.setStyleSheet(f"""
                PresetCardWidget {{
                    background-color: rgba(231, 111, 81, 0.18);
                    border: 1.5px solid {COLOR_ACCENT};
                    border-radius: 8px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                PresetCardWidget {{
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 8px;
                }}
                PresetCardWidget:hover {{
                    background-color: rgba(255, 255, 255, 0.08);
                    border-color: rgba(255, 255, 255, 0.25);
                }}
            """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.preset)
        super().mousePressEvent(event)


class NewProjectDialog(QDialog):
    """Dialog for creating a new animation project with dimensions and presets."""

    PRESETS = {
        "1280 x 720 (720p HD)": (1280, 720),
        "1920 x 1080 (1080p Full HD)": (1920, 1080),
        "1080 x 1080 (Square / Social)": (1080, 1080),
        "1080 x 1920 (9:16 Story / Reel)": (1080, 1920),
        "800 x 600 (Standard)": (800, 600),
        "640 x 480 (VGA)": (640, 480),
        "Custom": (1280, 720),
    }

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumSize(560, 580)
        self._custom_bg_color = QColor(255, 255, 200)
        self._updating_dims = False
        self._preset_cards: List[PresetCardWidget] = []
        self._selected_format_label: str = "16:9"
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Title & subtitle
        title_label = QLabel("New Project")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #EDE8E3;")
        layout.addWidget(title_label)

        # Project Name
        name_row = QHBoxLayout()
        name_lbl = QLabel("Project Name:")
        name_lbl.setFixedWidth(100)
        self.name_edit = QLineEdit("Untitled Animation")
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.name_edit)
        layout.addLayout(name_row)

        # Visual Preset Cards Section
        preset_header = QLabel("Canvas Format Presets:")
        preset_header.setStyleSheet("font-size: 12px; font-weight: 600; color: #D6D3D1; margin-top: 4px;")
        layout.addWidget(preset_header)

        # Category buttons
        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        self._cat_buttons: Dict[str, QPushButton] = {}
        for cat in ("All", "Landscape", "Portrait", "Square", "Social", "Other"):
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 5px;
                    padding: 3px 10px;
                    font-size: 11px;
                    color: {COLOR_TEXT_SECONDARY};
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.08);
                    color: #ffffff;
                }}
                QPushButton:checked {{
                    background: rgba(231, 111, 81, 0.20);
                    border-color: {COLOR_ACCENT};
                    color: #ffffff;
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda checked, c=cat: self._filter_presets(c))
            cat_row.addWidget(btn)
            self._cat_buttons[cat] = btn
        cat_row.addStretch()
        layout.addLayout(cat_row)
        self._cat_buttons["All"].setChecked(True)

        # Scrollable Cards Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(170)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background: rgba(20, 20, 22, 0.5);
            }
        """)
        container = QWidget()
        self.cards_layout = QGridLayout(container)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_layout.setSpacing(8)

        for idx, preset in enumerate(CANVAS_PRESETS):
            card = PresetCardWidget(preset)
            card.clicked.connect(self._on_preset_card_clicked)
            self._preset_cards.append(card)
            row = idx // 3
            col = idx % 3
            self.cards_layout.addWidget(card, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Preset combo for legacy/quick access
        self.preset_combo = QComboBox()
        for preset_name in self.PRESETS:
            self.preset_combo.addItem(preset_name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_combo_changed)

        # Dimensions & Ratio Lock Section
        dims_group = QGroupBox("Dimensions & Frame Rate")
        dims_layout = QGridLayout(dims_group)
        dims_layout.setSpacing(10)

        dims_layout.addWidget(QLabel("Width:"), 0, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 7680)
        self.width_spin.setValue(1280)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_width_changed)
        dims_layout.addWidget(self.width_spin, 0, 1)

        dims_layout.addWidget(QLabel("Height:"), 0, 2)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 4320)
        self.height_spin.setValue(720)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(self._on_height_changed)
        dims_layout.addWidget(self.height_spin, 0, 3)

        self.aspect_lock_cb = QCheckBox("Lock Aspect Ratio")
        self.aspect_lock_cb.setChecked(True)
        dims_layout.addWidget(self.aspect_lock_cb, 1, 0, 1, 2)

        self.ratio_display_label = QLabel("Ratio: 16:9 (Landscape)")
        self.ratio_display_label.setStyleSheet("font-size: 11px; color: #A8A29E;")
        dims_layout.addWidget(self.ratio_display_label, 1, 2, 1, 2)

        dims_layout.addWidget(QLabel("Frame Rate:"), 2, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(12)
        self.fps_spin.setSuffix(" fps")
        dims_layout.addWidget(self.fps_spin, 2, 1)

        layout.addWidget(dims_group)

        # Background color selection
        bg_group = QGroupBox("Canvas Background")
        bg_layout = QHBoxLayout(bg_group)
        self.bg_group_btns = QButtonGroup(self)
        self.bg_transparent_radio = QRadioButton("Transparent")
        self.bg_white_radio = QRadioButton("White")
        self.bg_white_radio.setChecked(True)
        self.bg_custom_radio = QRadioButton("Custom Color:")

        self.bg_group_btns.addButton(self.bg_transparent_radio)
        self.bg_group_btns.addButton(self.bg_white_radio)
        self.bg_group_btns.addButton(self.bg_custom_radio)

        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(28, 22)
        self.bg_color_btn.setStyleSheet(f"background-color: {self._custom_bg_color.name()}; border: 1px solid #555; border-radius: 3px;")
        self.bg_color_btn.clicked.connect(self._choose_custom_color)

        bg_layout.addWidget(self.bg_white_radio)
        bg_layout.addWidget(self.bg_transparent_radio)
        bg_layout.addWidget(self.bg_custom_radio)
        bg_layout.addWidget(self.bg_color_btn)
        bg_layout.addStretch()
        layout.addWidget(bg_group)

        # Dialog Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("Create Project")
        self.create_btn.setDefault(True)
        self.create_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: #F08064;
            }}
        """)
        self.create_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.create_btn)

        layout.addLayout(btn_layout)

        # Highlight default 1280x720 card
        self._highlight_matching_card(1280, 720)

    def _filter_presets(self, category: str) -> None:
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)

        visible_cards = []
        for card in self._preset_cards:
            is_visible = (category == "All") or (card.preset.category == category)
            card.setVisible(is_visible)
            if is_visible:
                visible_cards.append(card)

        for i in range(self.cards_layout.count()):
            self.cards_layout.takeAt(0)
        for idx, card in enumerate(visible_cards):
            self.cards_layout.addWidget(card, idx // 3, idx % 3)

    def _on_preset_card_clicked(self, preset: CanvasPreset) -> None:
        self._updating_dims = True
        self.width_spin.setValue(preset.width)
        self.height_spin.setValue(preset.height)
        self._selected_format_label = preset.ratio
        self._updating_dims = False
        self._update_ratio_display()

        for card in self._preset_cards:
            card.set_selected(card.preset == preset)

    def _highlight_matching_card(self, w: int, h: int) -> None:
        for card in self._preset_cards:
            is_match = (card.preset.width == w and card.preset.height == h)
            card.set_selected(is_match)
            if is_match:
                self._selected_format_label = card.preset.ratio

    def _choose_custom_color(self) -> None:
        col = QColorDialog.getColor(self._custom_bg_color, self, "Select Canvas Background Color")
        if col.isValid():
            self._custom_bg_color = col
            self.bg_color_btn.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #555; border-radius: 3px;")
            self.bg_custom_radio.setChecked(True)

    def _on_preset_combo_changed(self, text: str) -> None:
        if text in self.PRESETS and text != "Custom":
            w, h = self.PRESETS[text]
            self._updating_dims = True
            self.width_spin.setValue(w)
            self.height_spin.setValue(h)
            self._updating_dims = False
            self._highlight_matching_card(w, h)
            self._update_ratio_display()

    def _on_width_changed(self, w: int) -> None:
        if self._updating_dims:
            return
        if self.aspect_lock_cb.isChecked() and self.height_spin.value() > 0:
            ratio = self.width_spin.value() / max(1, self.height_spin.value())
            self._updating_dims = True
            self.height_spin.setValue(max(64, int(w / ratio)))
            self._updating_dims = False
        self._highlight_matching_card(self.width_spin.value(), self.height_spin.value())
        self._update_ratio_display()

    def _on_height_changed(self, h: int) -> None:
        if self._updating_dims:
            return
        if self.aspect_lock_cb.isChecked() and self.width_spin.value() > 0:
            ratio = self.width_spin.value() / max(1, self.height_spin.value())
            self._updating_dims = True
            self.width_spin.setValue(max(64, int(h * ratio)))
            self._updating_dims = False
        self._highlight_matching_card(self.width_spin.value(), self.height_spin.value())
        self._update_ratio_display()

    def _update_ratio_display(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        label = get_ratio_label(w, h)
        ori = get_orientation(w, h)
        self._selected_format_label = label
        self.ratio_display_label.setText(f"Ratio: {label} ({ori.title()})")

    def get_project_data(self) -> Dict[str, Any]:
        """Return project creation configuration dict."""
        if self.bg_transparent_radio.isChecked():
            bg_color = QColor(0, 0, 0, 0)
            bg_type = "transparent"
        elif self.bg_white_radio.isChecked():
            bg_color = QColor(255, 255, 255, 255)
            bg_type = "white"
        else:
            bg_color = self._custom_bg_color
            bg_type = "custom_color"

        w = self.width_spin.value()
        h = self.height_spin.value()
        return {
            "name": self.name_edit.text().strip() or "Untitled Animation",
            "width": w,
            "height": h,
            "fps": self.fps_spin.value(),
            "bg_color": bg_color,
            "background_type": bg_type,
            "format_label": self._selected_format_label or get_ratio_label(w, h),
        }


class CanvasFormatDialog(QDialog):
    """Modern dialog for switching canvas format and aspect ratio presets."""

    def __init__(
        self,
        current_width: int = 1280,
        current_height: int = 720,
        current_format_label: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Canvas Format & Aspect Ratio")
        self.setMinimumSize(580, 520)
        self.current_width = current_width
        self.current_height = current_height
        self._format_label = current_format_label or get_ratio_label(current_width, current_height)
        self._updating_dims = False
        self._preset_cards: List[PresetCardWidget] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header
        title_label = QLabel("Canvas Format & Aspect Ratio")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #EDE8E3;")
        layout.addWidget(title_label)

        sub_label = QLabel("Select an aspect ratio preset or enter custom dimensions for your project.")
        sub_label.setStyleSheet(f"font-size: 11px; color: {COLOR_TEXT_SECONDARY};")
        layout.addWidget(sub_label)

        # Categories filter bar
        cat_row = QHBoxLayout()
        cat_row.setSpacing(6)
        self._cat_buttons: Dict[str, QPushButton] = {}
        for cat in ("All", "Landscape", "Portrait", "Square", "Social", "Other"):
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.10);
                    border-radius: 5px;
                    padding: 3px 10px;
                    font-size: 11px;
                    color: {COLOR_TEXT_SECONDARY};
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.08);
                    color: #ffffff;
                }}
                QPushButton:checked {{
                    background: rgba(231, 111, 81, 0.20);
                    border-color: {COLOR_ACCENT};
                    color: #ffffff;
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda checked, c=cat: self._filter_presets(c))
            cat_row.addWidget(btn)
            self._cat_buttons[cat] = btn
        cat_row.addStretch()
        layout.addLayout(cat_row)
        self._cat_buttons["All"].setChecked(True)

        # Scrollable Cards Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(220)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background: rgba(20, 20, 22, 0.5);
            }
        """)
        container = QWidget()
        self.cards_layout = QGridLayout(container)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_layout.setSpacing(8)

        for idx, preset in enumerate(CANVAS_PRESETS):
            card = PresetCardWidget(preset)
            card.clicked.connect(self._on_preset_card_clicked)
            self._preset_cards.append(card)
            row = idx // 3
            col = idx % 3
            self.cards_layout.addWidget(card, row, col)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Custom Dimensions Box
        custom_group = QGroupBox("Custom Size & Ratio Lock")
        custom_layout = QGridLayout(custom_group)
        custom_layout.setSpacing(10)

        custom_layout.addWidget(QLabel("Width:"), 0, 0)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 7680)
        self.width_spin.setValue(self.current_width)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_width_changed)
        custom_layout.addWidget(self.width_spin, 0, 1)

        custom_layout.addWidget(QLabel("Height:"), 0, 2)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 4320)
        self.height_spin.setValue(self.current_height)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(self._on_height_changed)
        custom_layout.addWidget(self.height_spin, 0, 3)

        self.aspect_lock_cb = QCheckBox("Lock Aspect Ratio")
        self.aspect_lock_cb.setChecked(True)
        custom_layout.addWidget(self.aspect_lock_cb, 1, 0, 1, 2)

        self.ratio_display_label = QLabel(
            f"Ratio: {self._format_label} ({get_orientation(self.current_width, self.current_height).title()})"
        )
        self.ratio_display_label.setStyleSheet("font-size: 11px; color: #A8A29E;")
        custom_layout.addWidget(self.ratio_display_label, 1, 2, 1, 2)

        layout.addWidget(custom_group)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply Format")
        self.apply_btn.setDefault(True)
        self.apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: #F08064;
            }}
        """)
        self.apply_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)

        # Highlight preset card matching current project dimensions
        self._highlight_matching_card(self.current_width, self.current_height)

    def _filter_presets(self, category: str) -> None:
        for cat, btn in self._cat_buttons.items():
            btn.setChecked(cat == category)

        visible_cards = []
        for card in self._preset_cards:
            is_visible = (category == "All") or (card.preset.category == category)
            card.setVisible(is_visible)
            if is_visible:
                visible_cards.append(card)

        for i in range(self.cards_layout.count()):
            self.cards_layout.takeAt(0)
        for idx, card in enumerate(visible_cards):
            self.cards_layout.addWidget(card, idx // 3, idx % 3)

    def _on_preset_card_clicked(self, preset: CanvasPreset) -> None:
        self._updating_dims = True
        self.width_spin.setValue(preset.width)
        self.height_spin.setValue(preset.height)
        self._format_label = preset.ratio
        self._updating_dims = False
        self._update_ratio_display()

        for card in self._preset_cards:
            card.set_selected(card.preset == preset)

    def _highlight_matching_card(self, w: int, h: int) -> None:
        for card in self._preset_cards:
            is_match = (card.preset.width == w and card.preset.height == h)
            card.set_selected(is_match)
            if is_match:
                self._format_label = card.preset.ratio

    def _on_width_changed(self, w: int) -> None:
        if self._updating_dims:
            return
        if self.aspect_lock_cb.isChecked() and self.height_spin.value() > 0:
            ratio = self.current_width / max(1, self.current_height)
            self._updating_dims = True
            self.height_spin.setValue(max(64, int(w / ratio)))
            self._updating_dims = False
        self._highlight_matching_card(self.width_spin.value(), self.height_spin.value())
        self._update_ratio_display()

    def _on_height_changed(self, h: int) -> None:
        if self._updating_dims:
            return
        if self.aspect_lock_cb.isChecked() and self.width_spin.value() > 0:
            ratio = self.current_width / max(1, self.current_height)
            self._updating_dims = True
            self.width_spin.setValue(max(64, int(h * ratio)))
            self._updating_dims = False
        self._highlight_matching_card(self.width_spin.value(), self.height_spin.value())
        self._update_ratio_display()

    def _update_ratio_display(self) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        label = get_ratio_label(w, h)
        ori = get_orientation(w, h)
        self._format_label = label
        self.ratio_display_label.setText(f"Ratio: {label} ({ori.title()})")

    def get_format_data(self) -> Dict[str, Any]:
        """Return selected format dictionary."""
        w = self.width_spin.value()
        h = self.height_spin.value()
        return {
            "width": w,
            "height": h,
            "format_label": self._format_label or get_ratio_label(w, h),
            "orientation": get_orientation(w, h),
        }


class CanvasResizeConfirmDialog(QDialog):
    """Confirmation dialog prompting how existing artwork should adapt to resized canvas."""

    def __init__(
        self,
        old_width: int,
        old_height: int,
        new_width: int,
        new_height: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adapt Existing Artwork")
        self.setMinimumWidth(440)
        self.old_width = old_width
        self.old_height = old_height
        self.new_width = new_width
        self.new_height = new_height
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        title_label = QLabel("Resize Canvas Dimensions")
        title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #EDE8E3;")
        layout.addWidget(title_label)

        info_box = QFrame()
        info_box.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_box)
        info_layout.setSpacing(4)
        info_layout.addWidget(QLabel(f"Current canvas:  <b>{self.old_width} × {self.old_height}</b>"))
        info_layout.addWidget(QLabel(f"New canvas:      <b>{self.new_width} × {self.new_height}</b>"))
        layout.addWidget(info_box)

        layout.addWidget(QLabel("Choose how existing artwork across all frames should adapt:"))

        options_group = QGroupBox()
        opt_layout = QVBoxLayout(options_group)
        opt_layout.setSpacing(12)

        self.radio_scale = QRadioButton("Scale Artwork to Fit (Recommended)")
        self.radio_scale.setChecked(True)
        self.radio_scale.setStyleSheet("font-weight: 600; color: #EDE8E3;")
        opt_layout.addWidget(self.radio_scale)
        lbl_scale = QLabel("Proportionally scales existing drawings to fit the new dimensions without distortion.")
        lbl_scale.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SECONDARY}; margin-left: 20px;")
        lbl_scale.setWordWrap(True)
        opt_layout.addWidget(lbl_scale)

        self.radio_crop = QRadioButton("Crop Artwork (1:1 Center)")
        self.radio_crop.setStyleSheet("font-weight: 600; color: #EDE8E3;")
        opt_layout.addWidget(self.radio_crop)
        lbl_crop = QLabel("Preserves original 1:1 scale at center. Any drawing extending beyond new canvas boundaries is cropped.")
        lbl_crop.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SECONDARY}; margin-left: 20px;")
        lbl_crop.setWordWrap(True)
        opt_layout.addWidget(lbl_crop)

        self.radio_pad = QRadioButton("Keep Centered with Padding")
        self.radio_pad.setStyleSheet("font-weight: 600; color: #EDE8E3;")
        opt_layout.addWidget(self.radio_pad)
        lbl_pad = QLabel("Preserves original 1:1 scale at center, padding extra space with transparent borders.")
        lbl_pad.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SECONDARY}; margin-left: 20px;")
        lbl_pad.setWordWrap(True)
        opt_layout.addWidget(lbl_pad)

        layout.addWidget(options_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("Resize Canvas")
        self.confirm_btn.setDefault(True)
        self.confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                background-color: #F08064;
            }}
        """)
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.confirm_btn)

        layout.addLayout(btn_layout)

    def get_resize_mode(self) -> ResizeMode:
        if self.radio_scale.isChecked():
            return ResizeMode.SCALE
        if self.radio_crop.isChecked():
            return ResizeMode.CROP
        return ResizeMode.PAD



class ExportDialog(QDialog):
    """Dialog for configuring animation output render parameters."""

    def __init__(
        self,
        default_fps: int = 12,
        default_name: str = "animation",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Animation")
        self.setMinimumWidth(480)
        self.default_fps = default_fps
        self.default_name = default_name
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Output format
        self.format_combo = QComboBox()
        self.format_combo.addItem("MP4 Video (*.mp4)", "mp4")
        self.format_combo.addItem("Animated GIF (*.gif)", "gif")
        self.format_combo.addItem("PNG Image Sequence (*.png)", "sequence")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        form_layout.addRow("Export Format:", self.format_combo)

        # Output file path selection
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        default_dir = os.path.expanduser("~")
        self.path_edit.setText(os.path.join(default_dir, f"{self.default_name}.mp4"))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_btn)
        form_layout.addRow("Destination:", path_layout)

        # FPS
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(self.default_fps)
        self.fps_spin.setSuffix(" fps")
        form_layout.addRow("Playback FPS:", self.fps_spin)

        layout.addLayout(form_layout)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

    def _on_format_changed(self) -> None:
        fmt = self.format_combo.currentData()
        current_path = self.path_edit.text()
        base = os.path.splitext(current_path)[0]
        if fmt == "mp4":
            self.path_edit.setText(base + ".mp4")
        elif fmt == "gif":
            self.path_edit.setText(base + ".gif")
        elif fmt == "sequence":
            self.path_edit.setText(base + "_frames")

    def _on_browse(self) -> None:
        fmt = self.format_combo.currentData()
        if fmt == "mp4":
            path, _ = QFileDialog.getSaveFileName(self, "Export MP4 Video", self.path_edit.text(), "MP4 Video (*.mp4)")
        elif fmt == "gif":
            path, _ = QFileDialog.getSaveFileName(self, "Export Animated GIF", self.path_edit.text(), "GIF Animation (*.gif)")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select Export Folder", os.path.dirname(self.path_edit.text()))

        if path:
            self.path_edit.setText(path)

    def get_export_data(self) -> Dict[str, Any]:
        """Return user selected export parameters."""
        return {
            "format": self.format_combo.currentData(),
            "output_path": self.path_edit.text().strip(),
            "fps": self.fps_spin.value(),
        }


class AboutDialog(QDialog):
    """About dialog providing application description, version, and credits."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About AI Doodle Studio")
        self.setFixedSize(450, 320)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title_label = QLabel("AI Doodle Studio")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title_label.setFont(font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        ver_label = QLabel("Version 1.0.0")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver_label.setStyleSheet("color: #9ca3af;")
        layout.addWidget(ver_label)

        desc = (
            "A modern, high-performance 2D animation and doodle creation suite "
            "powered by PySide6 and Qt.\n\n"
            "Key Features:\n"
            "• Smooth anti-aliased freehand drawing & brush interpolation\n"
            "• Transparent canvas with onion skin ghosting\n"
            "• Timeline navigation, frame duplication, and reordering\n"
            "• Comprehensive multi-level undo/redo system\n"
            "• MP4, animated GIF, and PNG image sequence rendering"
        )
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("line-height: 140%; padding: 4px;")
        layout.addWidget(desc_label)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class OnionSkinSettingsDialog(QDialog):
    """Dialog for customizing onion skinning parameters."""

    def __init__(
        self,
        current_settings: Optional[Dict[str, Any]] = None,
        frames_before: int = 1,
        frames_after: int = 1,
        opacity: float = 0.35,
        tint_before: Optional[Any] = None,
        tint_after: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Onion Skin Settings")
        self.setMinimumWidth(360)
        self.settings = dict(current_settings) if current_settings else {}
        if "frames_before" not in self.settings:
            self.settings["frames_before"] = frames_before
        if "frames_after" not in self.settings:
            self.settings["frames_after"] = frames_after
        if "opacity" not in self.settings:
            self.settings["opacity"] = opacity
        if "tint_before" not in self.settings and tint_before is not None:
            self.settings["tint_before"] = tint_before
        if "tint_after" not in self.settings and tint_after is not None:
            self.settings["tint_after"] = tint_after
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self.before_spin = QSpinBox()
        self.before_spin.setRange(0, 5)
        self.before_spin.setValue(self.settings.get("frames_before", 1))
        form.addRow("Frames Before:", self.before_spin)

        self.after_spin = QSpinBox()
        self.after_spin.setRange(0, 5)
        self.after_spin.setValue(self.settings.get("frames_after", 1))
        form.addRow("Frames After:", self.after_spin)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(5, 100)
        self.opacity_slider.setValue(int(self.settings.get("opacity", 0.35) * 100))
        self.opacity_label = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))

        op_row = QHBoxLayout()
        op_row.addWidget(self.opacity_slider)
        op_row.addWidget(self.opacity_label)
        form.addRow("Overlay Opacity:", op_row)

        # Tints
        tint_b = self.settings.get("tint_before", "#FF3333")
        self.tint_before = QColor(tint_b) if not isinstance(tint_b, QColor) else tint_b
        tint_a = self.settings.get("tint_after", "#33FF33")
        self.tint_after = QColor(tint_a) if not isinstance(tint_a, QColor) else tint_a

        self.before_btn = QPushButton()
        self.before_btn.setFixedSize(40, 22)
        self.before_btn.setStyleSheet(f"background-color: {self.tint_before.name()}; border-radius: 3px;")
        self.before_btn.clicked.connect(self._pick_before_tint)
        form.addRow("Tint (Past):", self.before_btn)

        self.after_btn = QPushButton()
        self.after_btn.setFixedSize(40, 22)
        self.after_btn.setStyleSheet(f"background-color: {self.tint_after.name()}; border-radius: 3px;")
        self.after_btn.clicked.connect(self._pick_after_tint)
        form.addRow("Tint (Future):", self.after_btn)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Apply")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _pick_before_tint(self) -> None:
        c = QColorDialog.getColor(self.tint_before, self, "Past Frames Tint")
        if c.isValid():
            self.tint_before = c
            self.before_btn.setStyleSheet(f"background-color: {c.name()}; border-radius: 3px;")

    def _pick_after_tint(self) -> None:
        c = QColorDialog.getColor(self.tint_after, self, "Future Frames Tint")
        if c.isValid():
            self.tint_after = c
            self.after_btn.setStyleSheet(f"background-color: {c.name()}; border-radius: 3px;")

    def get_settings(self) -> Dict[str, Any]:
        return {
            "frames_before": self.before_spin.value(),
            "frames_after": self.after_spin.value(),
            "opacity": self.opacity_slider.value() / 100.0,
            "tint_before": self.tint_before.name(),
            "tint_after": self.tint_after.name(),
        }


class ExportProgressDialog(QDialog):
    """Progress dialog showing percentage and allowing cancellation of export."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Exporting Animation")
        self.setMinimumWidth(380)
        self.is_cancelled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.status_label = QLabel("Exporting frames, please wait...")
        self.status_label.setStyleSheet("font-size: 12px; color: #e0e0e0;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_box.addWidget(self.cancel_btn)
        layout.addLayout(btn_box)

    def set_progress(self, percent: int) -> None:
        self.progress_bar.setValue(percent)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_cancel(self) -> None:
        self.is_cancelled = True
        self.status_label.setText("Cancelling export...")
        self.cancel_btn.setEnabled(False)
        self.reject()


class ImportImageDialog(QDialog):
    """Dialog allowing user to choose target for imported image."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Image")
        self.setMinimumWidth(340)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        layout.addWidget(QLabel("How would you like to import this image?"))

        self.cur_layer_radio = QRadioButton("Place onto Current Active Layer")
        self.cur_layer_radio.setChecked(True)
        self.new_frame_radio = QRadioButton("Add as a New Frame")
        self.bg_radio = QRadioButton("Set as Static Background across all frames")

        layout.addWidget(self.cur_layer_radio)
        layout.addWidget(self.new_frame_radio)
        layout.addWidget(self.bg_radio)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Import")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(ok_btn)
        layout.addLayout(btn_box)

    def get_import_mode(self) -> str:
        if self.cur_layer_radio.isChecked():
            return "current_layer"
        elif self.new_frame_radio.isChecked():
            return "new_frame"
        return "background"

