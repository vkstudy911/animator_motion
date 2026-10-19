"""Layers panel widget for AI Doodle Studio.

Manages layer hierarchy, visibility toggles, lock states, opacity, blend modes,
and layer ordering directly connected to the active Frame data model with full
undo/redo support and non-blocking validation.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.history import LayerPropertyCommand, LayerSnapshotCommand
from app.core.layer import BLEND_MODES, Layer
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_BORDER_SUBTLE,
    COLOR_DANGER,
    COLOR_GLASS_BORDER,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    THEME_GLASS_BG_BOTTOM,
    THEME_GLASS_BG_TOP,
    THEME_GLASS_BORDER,
    THEME_GLASS_HIGHLIGHT,
    THEME_GLASS_SHADOW,
)

SVG_EYE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/>'
    '<circle cx="12" cy="12" r="3"/>'
    '</svg>'
)
SVG_EYE_OFF = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/>'
    '<path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/>'
    '<path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/>'
    '<line x1="2" y1="2" x2="22" y2="22"/>'
    '</svg>'
)
SVG_LOCK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="5" y="11" width="14" height="10" rx="2"/>'
    '<path d="M8 11V7a4 4 0 0 1 8 0v4"/>'
    '</svg>'
)
SVG_UNLOCK = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="5" y="11" width="14" height="10" rx="2"/>'
    '<path d="M8 11V7a4 4 0 0 1 7.78-1.3"/>'
    '</svg>'
)


def _render_layer_icon(svg_xml: str, color_hex: str, size: int = 14) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    colored = svg_xml.replace("currentColor", color_hex)
    renderer = QSvgRenderer(QByteArray(colored.encode("utf-8")))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pix)


class LayerItemWidget(QWidget):
    """Custom widget rendered inside layer list items."""

    visibility_toggled = Signal(bool)
    lock_toggled = Signal(bool)
    rename_requested = Signal()

    def __init__(self, layer: Layer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.layer = layer
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(6)

        btn_style = """
            QToolButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 1px;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.08);
            }
            QToolButton:pressed {
                background-color: rgba(255, 255, 255, 0.15);
            }
        """

        # Visibility eye toggle button
        self.vis_btn = QToolButton()
        self.vis_btn.setCheckable(True)
        self.vis_btn.setChecked(layer.visible)
        self.vis_btn.setFixedSize(22, 22)
        self.vis_btn.setStyleSheet(btn_style)
        self.vis_btn.setToolTip("Toggle Layer Visibility")
        self._update_vis_icon(layer.visible)
        self.vis_btn.toggled.connect(self._on_vis_toggled)
        layout.addWidget(self.vis_btn)

        # Mini thumbnail preview of layer buffer
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(28, 20)
        self.thumb_label.setStyleSheet(
            f"background-color: #1A1A1A; border: 1px solid {COLOR_BORDER}; border-radius: 3px;"
        )
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_thumb()
        layout.addWidget(self.thumb_label)

        # Layer Name Label
        self.name_label = QLabel(layer.name)
        self.name_label.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 500; font-size: 11px; background: transparent;")
        layout.addWidget(self.name_label)

        layout.addStretch()

        # Lock toggle button
        self.lock_btn = QToolButton()
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(layer.locked)
        self.lock_btn.setFixedSize(22, 22)
        self.lock_btn.setStyleSheet(btn_style)
        self.lock_btn.setToolTip("Lock / Unlock Layer")
        self._update_lock_icon(layer.locked)
        self.lock_btn.toggled.connect(self._on_lock_toggled)
        layout.addWidget(self.lock_btn)

    def _update_vis_icon(self, visible: bool) -> None:
        icon = _render_layer_icon(SVG_EYE if visible else SVG_EYE_OFF, "#F2F0EC" if visible else "#6E6B66")
        self.vis_btn.setIcon(icon)

    def _update_lock_icon(self, locked: bool) -> None:
        icon = _render_layer_icon(SVG_LOCK if locked else SVG_UNLOCK, COLOR_ACCENT if locked else "#6E6B66")
        self.lock_btn.setIcon(icon)

    def _update_thumb(self) -> None:
        if self.layer and not self.layer.is_empty():
            scaled = self.layer.image.scaled(
                QSize(24, 16),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumb_label.setPixmap(QPixmap.fromImage(scaled))
            self.thumb_label.setText("")
            self.thumb_label.setToolTip("Artwork present on this frame")
            self.thumb_label.setStyleSheet(
                f"background-color: #1A1A1A; border: 1px solid {COLOR_BORDER}; border-radius: 3px;"
            )
        else:
            self.thumb_label.setPixmap(QPixmap())
            self.thumb_label.setText("·")
            self.thumb_label.setToolTip("Empty cel on this frame")
            self.thumb_label.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.02); "
                f"border: 1px dashed {COLOR_BORDER_SUBTLE}; border-radius: 3px; "
                f"color: {COLOR_TEXT_SECONDARY}; font-size: 14px; font-weight: bold;"
            )

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.rename_requested.emit()

    def _on_vis_toggled(self, checked: bool) -> None:
        self._update_vis_icon(checked)
        self.visibility_toggled.emit(checked)

    def _on_lock_toggled(self, checked: bool) -> None:
        self._update_lock_icon(checked)
        self.lock_toggled.emit(checked)


class LayersPanel(QWidget):
    """Right-side panel for inspecting and tweaking drawing layers."""

    layer_visibility_changed = Signal(int, bool)
    layer_opacity_changed = Signal(int, float)
    layer_blend_mode_changed = Signal(int, str)
    layers_changed = Signal()
    status_message = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(210)
        self.setMaximumWidth(320)
        self._frame = None
        self._layers: List[Layer] = []
        self.project = None
        self._opacity_drag_start: Optional[float] = None
        self._opacity_drag_row: int = 0
        self._setup_ui()

    def set_project(self, project) -> None:
        self.project = project
        if project and hasattr(project, "layers_changed"):
            try:
                project.layers_changed.connect(self._refresh_layers)
            except Exception:
                pass

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # Header with quick-add button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 2, 0)
        header = QLabel("Layers")
        header.setStyleSheet(
            f"font-weight: 700; font-size: 13px; color: {COLOR_TEXT_PRIMARY}; "
            "letter-spacing: 0.3px; background: transparent;"
        )
        header_layout.addWidget(header)
        header_layout.addStretch()

        self.quick_add_btn = QToolButton()
        self.quick_add_btn.setText("+")
        self.quick_add_btn.setFixedSize(22, 22)
        self.quick_add_btn.setToolTip("Add New Layer")
        self.quick_add_btn.setStyleSheet(f"""
            QToolButton {{
                background-color: rgba(231, 111, 81, 0.20);
                color: {COLOR_ACCENT};
                border: 1px solid rgba(231, 111, 81, 0.50);
                border-radius: 11px;
                font-weight: 700;
                font-size: 13px;
                padding: 0;
            }}
            QToolButton:hover {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
            }}
        """)
        self.quick_add_btn.clicked.connect(self._add_layer)
        header_layout.addWidget(self.quick_add_btn)
        layout.addLayout(header_layout)

        # Expanding Layer List
        self.list_widget = QListWidget()
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: rgba(20, 20, 24, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                outline: none;
                padding: 3px;
            }}
            QListWidget::item {{
                padding: 2px;
                border-radius: 6px;
                margin-bottom: 2px;
                border: 1px solid rgba(255, 255, 255, 0.04);
                background-color: rgba(255, 255, 255, 0.03);
            }}
            QListWidget::item:hover {{
                background-color: rgba(255, 255, 255, 0.09);
                border-color: rgba(255, 255, 255, 0.18);
            }}
            QListWidget::item:selected {{
                background-color: rgba(231, 111, 81, 0.22);
                border: 1px solid rgba(231, 111, 81, 0.70);
            }}
        """)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

        # Controls Section: Opacity & Blend Mode
        controls_frame = QFrame()
        controls_frame.setStyleSheet("""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }}
        """)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        controls_layout.setSpacing(5)

        # Opacity Row
        op_hdr = QHBoxLayout()
        op_title = QLabel("OPACITY")
        op_title.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 8.5px; font-weight: bold; "
            "border: none; background: transparent; letter-spacing: 0.5px;"
        )
        self.opacity_val_label = QLabel("100%")
        self.opacity_val_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 8.5px; font-weight: bold; "
            "border: none; background: transparent;"
        )
        op_hdr.addWidget(op_title)
        op_hdr.addStretch()
        op_hdr.addWidget(self.opacity_val_label)
        controls_layout.addLayout(op_hdr)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedHeight(14)
        self.opacity_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                background-color: rgba(255, 255, 255, 0.12);
                border-radius: 2px;
                border: none;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {COLOR_ACCENT};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
                background-color: #FFFFFF;
                border: 1px solid rgba(0, 0, 0, 0.4);
            }}
            QSlider::handle:horizontal:hover {{
                background-color: #F8F9FA;
                border: 1px solid {COLOR_ACCENT};
            }}
        """)
        self.opacity_slider.sliderPressed.connect(self._on_opacity_slider_pressed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.opacity_slider.sliderReleased.connect(self._on_opacity_slider_released)
        controls_layout.addWidget(self.opacity_slider)

        # Blend Mode Row
        blend_hdr = QHBoxLayout()
        blend_title = QLabel("BLEND")
        blend_title.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 8.5px; font-weight: bold; "
            "border: none; background: transparent; letter-spacing: 0.5px;"
        )
        self.blend_combo = QComboBox()
        self.blend_combo.addItems(["Normal", "Multiply", "Screen", "Overlay"])
        self.blend_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 11px;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QComboBox:focus {{
                border-color: {COLOR_ACCENT};
            }}
        """)
        self.blend_combo.currentTextChanged.connect(self._on_blend_mode_changed)
        blend_hdr.addWidget(blend_title)
        blend_hdr.addStretch()
        blend_hdr.addWidget(self.blend_combo)
        controls_layout.addLayout(blend_hdr)

        layout.addWidget(controls_frame)

        # Action buttons style
        action_btn_style = f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
                padding: 4px 6px;
                font-size: 11px;
                font-weight: 500;
                color: {COLOR_TEXT_PRIMARY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.14);
                border-color: rgba(255, 255, 255, 0.22);
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: rgba(255, 255, 255, 0.04);
            }}
            QPushButton:disabled {{
                background-color: rgba(255, 255, 255, 0.02);
                color: #55534E;
                border-color: rgba(255, 255, 255, 0.04);
            }}
        """

        # Action Buttons Row 1: Up, Down, Merge
        row1_box = QHBoxLayout()
        row1_box.setSpacing(4)
        self.move_up_btn = QPushButton("↑ Up")
        self.move_up_btn.setStyleSheet(action_btn_style)
        self.move_up_btn.setToolTip("Move Layer Up")
        self.move_up_btn.clicked.connect(self._move_layer_up)

        self.move_down_btn = QPushButton("↓ Down")
        self.move_down_btn.setStyleSheet(action_btn_style)
        self.move_down_btn.setToolTip("Move Layer Down")
        self.move_down_btn.clicked.connect(self._move_layer_down)

        self.merge_btn = QPushButton("⧉ Merge")
        self.merge_btn.setStyleSheet(action_btn_style)
        self.merge_btn.setToolTip("Merge Active Layer Down")
        self.merge_btn.clicked.connect(self._merge_down)

        row1_box.addWidget(self.move_up_btn)
        row1_box.addWidget(self.move_down_btn)
        row1_box.addWidget(self.merge_btn)
        layout.addLayout(row1_box)

        # Action Buttons Row 2: New, Dup, Del
        row2_box = QHBoxLayout()
        row2_box.setSpacing(4)
        self.add_layer_btn = QPushButton("+ New")
        self.add_layer_btn.setStyleSheet(action_btn_style + f"""
            QPushButton {{
                background-color: rgba(231, 111, 81, 0.20);
                border-color: rgba(231, 111, 81, 0.50);
                color: #FFFFFF;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                border-color: {COLOR_ACCENT};
            }}
        """)
        self.add_layer_btn.setToolTip("Add New Layer")
        self.add_layer_btn.clicked.connect(self._add_layer)

        self.dup_layer_btn = QPushButton("❐ Duplicate")
        self.dup_layer_btn.setStyleSheet(action_btn_style)
        self.dup_layer_btn.setToolTip("Duplicate Active Layer")
        self.dup_layer_btn.clicked.connect(self._duplicate_layer)

        self.del_layer_btn = QPushButton("🗑 Delete")
        self.del_layer_btn.setStyleSheet(action_btn_style + f"""
            QPushButton:hover {{
                background-color: rgba(217, 83, 79, 0.22);
                border-color: {COLOR_DANGER};
                color: #FFB3B0;
            }}
        """)
        self.del_layer_btn.setToolTip("Delete Selected Layer")
        self.del_layer_btn.clicked.connect(self._delete_layer)

        row2_box.addWidget(self.add_layer_btn)
        row2_box.addWidget(self.dup_layer_btn)
        row2_box.addWidget(self.del_layer_btn)
        layout.addLayout(row2_box)

    def paintEvent(self, event) -> None:
        """Render floating glass panel with soft shadow, translucent gradient and top highlight."""
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

    def set_frame(self, frame) -> None:
        """Bind panel to the given Frame instance and refresh all layers and controls."""
        self._frame = frame
        if frame is not None and hasattr(frame, "layers"):
            self._layers = frame.layers
        else:
            self._layers = []
        self._refresh_layers()

    def _refresh_layers(self) -> None:
        """Refresh layer items, active selection, slider values, blend mode, and button states."""
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for idx, layer in enumerate(self._layers):
            item = QListWidgetItem(self.list_widget)
            widget = LayerItemWidget(layer)
            widget.visibility_toggled.connect(
                lambda v, i=idx: self._handle_visibility(i, v)
            )
            widget.lock_toggled.connect(
                lambda lk, i=idx: self._handle_lock(i, lk)
            )
            widget.rename_requested.connect(
                lambda i=idx: self._rename_layer(i)
            )
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        target_row = 0
        if self._frame and hasattr(self._frame, "active_layer_index"):
            target_row = max(0, min(self._frame.active_layer_index, len(self._layers) - 1))

        if self._layers:
            self.list_widget.setCurrentRow(target_row)
            active_layer = self._layers[target_row]

            # Opacity
            self.opacity_slider.blockSignals(True)
            op_pct = int(round(active_layer.opacity * 100))
            self.opacity_slider.setValue(op_pct)
            self.opacity_val_label.setText(f"{op_pct}%")
            self.opacity_slider.blockSignals(False)

            # Blend Mode
            self.blend_combo.blockSignals(True)
            self.blend_combo.setCurrentText(active_layer.blend_mode.capitalize())
            self.blend_combo.blockSignals(False)

        self._update_button_states()
        self.list_widget.blockSignals(False)

    def _update_button_states(self) -> None:
        num_layers = len(self._layers)
        target_row = self.list_widget.currentRow()
        active_layer = self._layers[target_row] if 0 <= target_row < num_layers else None
        is_locked = active_layer.locked if active_layer else False

        # Can delete only if more than 1 layer exists and active layer is NOT locked
        self.del_layer_btn.setEnabled(num_layers > 1 and not is_locked)

        # Merge down requires active layer > 0, not locked, and destination lower layer not locked
        can_merge = (
            target_row > 0
            and num_layers > 1
            and not is_locked
            and not self._layers[target_row - 1].locked
        )
        self.merge_btn.setEnabled(can_merge)

        # Reordering disabled if active layer is locked
        self.move_up_btn.setEnabled(target_row < num_layers - 1 and not is_locked)
        self.move_down_btn.setEnabled(target_row > 0 and not is_locked)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._layers):
            if self.project and hasattr(self.project, "active_layer_index"):
                self.project.active_layer_index = row
            if self._frame and hasattr(self._frame, "set_active_layer_index"):
                self._frame.set_active_layer_index(row)
            active_layer = self._layers[row]

            self.opacity_slider.blockSignals(True)
            op_pct = int(round(active_layer.opacity * 100))
            self.opacity_slider.setValue(op_pct)
            self.opacity_val_label.setText(f"{op_pct}%")
            self.opacity_slider.blockSignals(False)

            self.blend_combo.blockSignals(True)
            self.blend_combo.setCurrentText(active_layer.blend_mode.capitalize())
            self.blend_combo.blockSignals(False)

            self._update_button_states()

    def _handle_visibility(self, layer_idx: int, visible: bool) -> None:
        if 0 <= layer_idx < len(self._layers):
            if self.project and hasattr(self.project, "set_layer_property"):
                self.project.set_layer_property(layer_idx, "visible", visible)
            else:
                old_val = not visible
                self._layers[layer_idx].visible = visible
                if self._frame:
                    self._frame.mark_modified()
                self._refresh_layers()
            self.layer_visibility_changed.emit(layer_idx, visible)
            self.layers_changed.emit()

    def _handle_lock(self, layer_idx: int, locked: bool) -> None:
        if 0 <= layer_idx < len(self._layers):
            if self.project and hasattr(self.project, "set_layer_property"):
                self.project.set_layer_property(layer_idx, "locked", locked)
            else:
                old_val = not locked
                self._layers[layer_idx].locked = locked
                if self._frame:
                    self._frame.mark_modified()
                self._refresh_layers()
            self._update_button_states()
            self.layers_changed.emit()

    def _rename_layer(self, index: int) -> None:
        if 0 <= index < len(self._layers):
            layer = self._layers[index]
            new_name, ok = QInputDialog.getText(
                self, "Rename Layer", f"Enter new name for {layer.name}:", text=layer.name
            )
            if ok and new_name.strip() and new_name.strip() != layer.name:
                if self.project and hasattr(self.project, "set_layer_property"):
                    self.project.set_layer_property(index, "name", new_name.strip())
                else:
                    layer.name = new_name.strip()
                    if self._frame:
                        self._frame.mark_modified()
                    self._refresh_layers()
                self.layers_changed.emit()

    def _on_opacity_slider_pressed(self) -> None:
        cur_row = self.list_widget.currentRow()
        if 0 <= cur_row < len(self._layers):
            self._opacity_drag_start = self._layers[cur_row].opacity
            self._opacity_drag_row = cur_row
        else:
            self._opacity_drag_start = None

    def _on_opacity_changed(self, value: int) -> None:
        self.opacity_val_label.setText(f"{value}%")
        cur_row = self.list_widget.currentRow()
        if 0 <= cur_row < len(self._layers):
            op = value / 100.0
            self._layers[cur_row].opacity = op
            if self._frame:
                self._frame.mark_modified()
            if self.project:
                self.project.modified = True
            self.layer_opacity_changed.emit(cur_row, op)
            self.layers_changed.emit()

    _on_opacity_slider_changed = _on_opacity_changed

    def _on_opacity_slider_released(self) -> None:
        if self._opacity_drag_start is not None:
            cur_val = self.opacity_slider.value() / 100.0
            if abs(cur_val - self._opacity_drag_start) > 0.001:
                if self.project and hasattr(self.project, "set_layer_property"):
                    # Reset opacity so set_layer_property can register the change and undo
                    self._layers[self._opacity_drag_row].opacity = self._opacity_drag_start
                    self.project.set_layer_property(self._opacity_drag_row, "opacity", cur_val)
                elif self._frame and self.project and getattr(self.project, "undo_manager", None):
                    cmd = LayerPropertyCommand(
                        self._frame,
                        self._opacity_drag_row,
                        "opacity",
                        self._opacity_drag_start,
                        cur_val,
                        project=self.project,
                        on_update=self._refresh_layers,
                        description="Change Layer Opacity",
                    )
                    self.project.undo_manager.push(cmd)
        self._opacity_drag_start = None

    def _on_blend_mode_changed(self, text: str) -> None:
        cur_row = self.list_widget.currentRow()
        if 0 <= cur_row < len(self._layers):
            new_mode = text.lower()
            old_mode = self._layers[cur_row].blend_mode
            if old_mode != new_mode:
                if self.project and hasattr(self.project, "set_layer_property"):
                    self.project.set_layer_property(cur_row, "blend_mode", new_mode)
                else:
                    self._layers[cur_row].blend_mode = new_mode
                    if self._frame:
                        self._frame.mark_modified()
                    self._refresh_layers()
                self.layer_blend_mode_changed.emit(cur_row, new_mode)
                self.layers_changed.emit()

    def _record_layer_snapshot(self, before_layers, before_active, desc="Layer change"):
        if self._frame and self.project and getattr(self.project, "undo_manager", None):
            after_layers = [l.clone() for l in self._frame.layers]
            after_active = self._frame.active_layer_index
            cmd = LayerSnapshotCommand(
                self._frame,
                before_layers,
                after_layers,
                before_active,
                after_active,
                project=self.project,
                on_update=self._refresh_layers,
                description=desc,
            )
            self.project.undo_manager.push(cmd)

    def _add_layer(self) -> None:
        if self.project and hasattr(self.project, "add_layer"):
            self.project.add_layer()
        elif self._frame and hasattr(self._frame, "add_layer"):
            before_layers = [l.clone() for l in self._frame.layers]
            before_active = self._frame.active_layer_index
            self._frame.add_layer()
            self._layers = self._frame.layers
            self._record_layer_snapshot(before_layers, before_active, "Add Layer")
            self._refresh_layers()
            self.layers_changed.emit()

    def _duplicate_layer(self) -> None:
        if self.project and hasattr(self.project, "duplicate_layer"):
            self.project.duplicate_layer()
        elif self._frame and hasattr(self._frame, "duplicate_active_layer"):
            before_layers = [l.clone() for l in self._frame.layers]
            before_active = self._frame.active_layer_index
            self._frame.duplicate_active_layer()
            self._layers = self._frame.layers
            self._record_layer_snapshot(before_layers, before_active, "Duplicate Layer")
            self._refresh_layers()
            self.layers_changed.emit()

    def _merge_down(self) -> None:
        target_row = self.list_widget.currentRow()
        if target_row <= 0 or target_row >= len(self._layers):
            return
        upper = self._layers[target_row]
        lower = self._layers[target_row - 1]
        if upper.locked or lower.locked:
            self.status_message.emit("Unlock this layer before merging, deleting, or reordering.")
            return

        if self.project and hasattr(self.project, "merge_down_layer"):
            self.project.merge_down_layer(target_row)
        elif self._frame and hasattr(self._frame, "merge_down"):
            before_layers = [l.clone() for l in self._frame.layers]
            before_active = self._frame.active_layer_index
            if self._frame.merge_down():
                self._layers = self._frame.layers
                self._record_layer_snapshot(before_layers, before_active, "Merge Layer Down")
                self._refresh_layers()
                self.layers_changed.emit()

    def _delete_layer(self) -> None:
        if len(self._layers) <= 1:
            return
        target_row = self.list_widget.currentRow()
        if not (0 <= target_row < len(self._layers)):
            return
        active = self._layers[target_row]
        if active and active.locked:
            self.status_message.emit("Unlock this layer before merging, deleting, or reordering.")
            return

        if self.project and hasattr(self.project, "delete_layer"):
            self.project.delete_layer(target_row)
        elif self._frame and hasattr(self._frame, "delete_active_layer"):
            before_layers = [l.clone() for l in self._frame.layers]
            before_active = self._frame.active_layer_index
            if self._frame.delete_active_layer():
                self._layers = self._frame.layers
                self._record_layer_snapshot(before_layers, before_active, "Delete Layer")
                self._refresh_layers()
                self.layers_changed.emit()

    def _move_layer_up(self) -> None:
        target_row = self.list_widget.currentRow()
        if target_row < len(self._layers) - 1:
            if self._layers[target_row].locked:
                self.status_message.emit("Unlock this layer before merging, deleting, or reordering.")
                return

            if self.project and hasattr(self.project, "move_layer"):
                self.project.move_layer(target_row, target_row + 1)
            elif self._frame and hasattr(self._frame, "move_layer"):
                before_layers = [l.clone() for l in self._frame.layers]
                before_active = target_row
                if self._frame.move_layer(target_row, target_row + 1):
                    self._layers = self._frame.layers
                    self._record_layer_snapshot(before_layers, before_active, "Move Layer Up")
                    self._refresh_layers()
                    self.layers_changed.emit()

    def _move_layer_down(self) -> None:
        target_row = self.list_widget.currentRow()
        if target_row > 0:
            if self._layers[target_row].locked:
                self.status_message.emit("Unlock this layer before merging, deleting, or reordering.")
                return

            if self.project and hasattr(self.project, "move_layer"):
                self.project.move_layer(target_row, target_row - 1)
            elif self._frame and hasattr(self._frame, "move_layer"):
                before_layers = [l.clone() for l in self._frame.layers]
                before_active = target_row
                if self._frame.move_layer(target_row, target_row - 1):
                    self._layers = self._frame.layers
                    self._record_layer_snapshot(before_layers, before_active, "Move Layer Down")
                    self._refresh_layers()
                    self.layers_changed.emit()
