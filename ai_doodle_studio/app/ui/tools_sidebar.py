"""Left sidebar widget containing drawing tool selection and brush attributes.

Redesigned with a minimal, professional creative-software UI:
- Neutral dark surface (#242424) with restrained borders (#383838).
- Flat/transparent default tool buttons with soft hover states.
- Active tool uses warm terracotta accent (#E76F51) background tint and left pill.
- Coherent, crisp outline vector SVG icons with clear contrast.
- Compact, aligned brush size and opacity controls.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.drawing.tools import ToolType
from app.theme.styles import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_BORDER,
    COLOR_BORDER_SUBTLE,
    COLOR_GLASS_BG,
    COLOR_GLASS_BORDER,
    COLOR_SURFACE_ELEVATED,
    COLOR_SURFACE_HOVER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    THEME_ACCENT,
    THEME_ACCENT_BG,
    THEME_ACCENT_BORDER,
    THEME_ACCENT_HOVER,
    THEME_ACCENT_PILL,
    THEME_GLASS_BG_BOTTOM,
    THEME_GLASS_BG_TOP,
    THEME_GLASS_BORDER,
    THEME_GLASS_HIGHLIGHT,
    THEME_GLASS_SHADOW,
    THEME_ITEM_BG,
    THEME_ITEM_BORDER,
    THEME_ITEM_HOVER_BG,
    THEME_ITEM_HOVER_BORDER,
    THEME_PANEL_BG,
    THEME_PANEL_BORDER,
    THEME_TEXT_DISABLED,
    THEME_TEXT_MUTED,
    THEME_TEXT_PRIMARY,
    THEME_TEXT_SECONDARY,
)

# Modern, coherent outline vector SVG icons (24x24 viewBox, 1.8 stroke, rounded caps/joins)
TOOL_SVGS: Dict[ToolType, str] = {
    ToolType.PEN: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>'
        "</svg>"
    ),
    ToolType.ERASER: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21"/>'
        '<path d="M22 21H7"/><path d="m5 11 9 9"/>'
        "</svg>"
    ),
    ToolType.FILL: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m19 11-8-8-8.6 8.6a2 2 0 0 0 0 2.8l5.2 5.2c.8.8 2 .8 2.8 0L19 11Z"/>'
        '<path d="m5 2 5 5"/><path d="M2 13h15"/>'
        '<path d="M22 20a2 2 0 1 1-4 0c0-1.6 2-3.5 2-3.5s2 1.9 2 3.5Z"/>'
        "</svg>"
    ),
    ToolType.COLOR_PICKER: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="m14 7 3-3a1.5 1.5 0 0 1 2 2l-3 3"/><path d="m11 10 3 3"/>'
        '<path d="m2 22 5-1 9-9-4-4-9 9-1 5Z"/>'
        "</svg>"
    ),
    ToolType.SELECT: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 3C7.58 3 4 6.58 4 11c0 2.8 1.45 5.27 3.67 6.71L7 20l3.5-1.5c.48.1 1 .15 1.5.15 '
        '4.42 0 8-3.58 8-8s-3.58-8-8-8z" stroke-dasharray="2.5 2"/>'
        "</svg>"
    ),
    ToolType.TEXT: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 7V4h16v3"/><path d="M12 4v16"/><path d="M8 20h8"/>'
        "</svg>"
    ),
    ToolType.LINE: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 19 19 5"/>'
        '<circle cx="5" cy="19" r="1.5" fill="currentColor"/>'
        '<circle cx="19" cy="5" r="1.5" fill="currentColor"/>'
        "</svg>"
    ),
    ToolType.RECTANGLE: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3.5" y="5.5" width="17" height="13" rx="3"/>'
        "</svg>"
    ),
    ToolType.ELLIPSE: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<ellipse cx="12" cy="12" rx="8.5" ry="7"/>'
        "</svg>"
    ),
    ToolType.RIG: (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/>'
        '<line x1="12" y1="7.5" x2="6" y2="15.5"/><line x1="12" y1="7.5" x2="18" y2="15.5"/>'
        "</svg>"
    ),
}


def _render_svg_pixmap(svg_xml: str, color_hex: str, size: int = 16) -> QPixmap:
    """Render an SVG string into a crisp, anti-aliased QPixmap with dynamic color."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    colored = svg_xml.replace("currentColor", color_hex)
    renderer = QSvgRenderer(QByteArray(colored.encode("utf-8")))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pix


class GlassToolButton(QToolButton):
    """Compact tool button styled with modern professional aesthetic."""

    BUTTON_W = 84
    BUTTON_H = 36

    def __init__(
        self,
        tool_type: ToolType,
        label: str,
        svg_xml: str,
        tooltip: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.tool_type = tool_type
        self.label_text = label
        self.svg_xml = svg_xml
        self.hovered = False
        self.setCheckable(True)
        self.setFixedSize(self.BUTTON_W, self.BUTTON_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setText(label)

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()
        r = QRectF(1.0, 1.0, w - 2.0, h - 2.0)
        radius = 6.0

        is_checked = self.isChecked()
        is_hovered = self.hovered and not is_checked
        is_enabled = self.isEnabled()

        if not is_enabled:
            # Disabled state
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(r, radius, radius)
            icon_hex = "#4D4B47"
            text_color = THEME_TEXT_DISABLED
            font_bold = False
        elif is_checked:
            # Selected: Studio Obsidian Neon Violet fill, subtle glow, pill indicator
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(160, 120, 255, 50))
            p.drawRoundedRect(r.adjusted(-1, 0, 1, 2), radius + 1, radius + 1)

            grad = QLinearGradient(0, r.top(), 0, r.bottom())
            grad.setColorAt(0.0, QColor(160, 120, 255, 170))  # Primary container violet
            grad.setColorAt(1.0, QColor(109, 59, 215, 160))   # Inverse primary
            p.setBrush(grad)
            p.setPen(QPen(QColor(208, 188, 255, 230), 1.0))   # Primary violet highlight
            p.drawRoundedRect(r, radius, radius)

            # Left accent indicator pill
            p.setBrush(QColor(208, 188, 255))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(3.0, 8.0, 2.5, 20.0), 1.25, 1.25)

            # Top inner highlight line
            p.setPen(QPen(QColor(255, 255, 255, 80), 1.0))
            p.drawLine(QPointF(r.left() + radius, r.top() + 1.0), QPointF(r.right() - radius, r.top() + 1.0))

            icon_hex = "#FFFFFF"
            text_color = QColor(255, 255, 255)
            font_bold = True
        elif is_hovered:
            # Hovered: slightly brighter glass surface and border
            p.setBrush(THEME_ITEM_HOVER_BG)
            p.setPen(QPen(THEME_ITEM_HOVER_BORDER, 1.0))
            p.drawRoundedRect(r, radius, radius)
            icon_hex = "#F2F0EC"
            text_color = THEME_TEXT_PRIMARY
            font_bold = False
        else:
            # Normal: subtle transparent glass surface
            p.setBrush(THEME_ITEM_BG)
            p.setPen(QPen(THEME_ITEM_BORDER, 1.0))
            p.drawRoundedRect(r, radius, radius)
            icon_hex = "#AAA7A1"
            text_color = THEME_TEXT_SECONDARY
            font_bold = False

        # Draw icon centered horizontally
        icon_pix = _render_svg_pixmap(self.svg_xml, icon_hex, size=16)
        p.drawPixmap(int((w - 16) / 2.0), 3, icon_pix)

        # Draw label centered below icon
        font = p.font()
        font.setPointSize(8)
        font.setBold(font_bold)
        p.setFont(font)
        p.setPen(text_color)
        p.drawText(QRectF(0, 20, w, 13), Qt.AlignmentFlag.AlignCenter, self.label_text)
        p.end()


class GlassColorTile(QPushButton):
    """Clean color swatch tile with subtle border and hover highlight."""

    TILE_W = 78
    TILE_H = 18

    def __init__(self, color: QColor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.hovered = False
        self.setFixedSize(self.TILE_W, self.TILE_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to choose drawing color")

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        r = QRectF(1.0, 1.0, w - 2.0, h - 2.0)
        radius = 6.0

        # Background color swatch
        p.setBrush(self._color)
        border_color = THEME_ACCENT if self.hovered else QColor(255, 255, 255, 45)
        p.setPen(QPen(border_color, 1.0))
        p.drawRoundedRect(r, radius, radius)

        # Subtle 1px inner border for white/light color visibility
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 40), 1.0))
        p.drawRoundedRect(r.adjusted(1, 1, -1, -1), radius - 1, radius - 1)
        p.end()


class ToolsSidebar(QWidget):
    """Vertical sidebar offering drawing tool selection, color picker, and brush sliders."""

    tool_selected = Signal(ToolType)
    brush_size_changed = Signal(int)
    brush_color_changed = Signal(QColor)
    brush_opacity_changed = Signal(float)

    PANEL_WIDTH = 96

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(self.PANEL_WIDTH)
        self._current_color = QColor(240, 240, 240)
        self._tool_buttons: Dict[ToolType, QToolButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        # Stylesheet for scroll area, thin modern scrollbar, and sliders
        self.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 4px;
                margin: 4px 1px 4px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #383838;
                border-radius: 2px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #505050;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QSlider::groove:horizontal {{
                height: 3px;
                background: #333333;
                border-radius: 1.5px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLOR_ACCENT};
                border-radius: 1.5px;
            }}
            QSlider::handle:horizontal {{
                background: #F2F0EC;
                border: 1px solid {COLOR_ACCENT};
                width: 10px;
                height: 10px;
                margin: -3.5px 0px;
                border-radius: 5px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #FFFFFF;
                border-color: {COLOR_ACCENT_HOVER};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)

        # ScrollArea to ensure responsiveness on compact displays
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 2, 0, 2)
        c_layout.setSpacing(2)
        c_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        tools_def = [
            (ToolType.PEN, "Pen", "Pen / Brush Tool (B)"),
            (ToolType.ERASER, "Eraser", "Eraser Tool (E)"),
            (ToolType.FILL, "Fill", "Paint Bucket Fill (G)"),
            (ToolType.COLOR_PICKER, "Pipette", "Eyedropper Color Picker (I)"),
            (ToolType.SELECT, "Lasso", "Lasso Selection Tool (L)"),
            (ToolType.TEXT, "Text", "Text Tool (T)"),
            (ToolType.LINE, "Line", "Straight Line Tool (Shift+L)"),
            (ToolType.RECTANGLE, "Rect", "Rectangle Tool (R)"),
            (ToolType.ELLIPSE, "Circle", "Ellipse / Circle Tool (C)"),
            (ToolType.RIG, "Rig", "Skeletal Rigging & Pose Tool (K)"),
        ]

        for tool_type, label, tooltip in tools_def:
            svg_xml = TOOL_SVGS.get(tool_type, "")
            btn = GlassToolButton(tool_type, label, svg_xml, tooltip)
            self.button_group.addButton(btn)
            self._tool_buttons[tool_type] = btn
            btn.clicked.connect(lambda checked=False, t=tool_type: self.tool_selected.emit(t))
            c_layout.addWidget(btn)

        # Default tool active
        self._tool_buttons[ToolType.PEN].setChecked(True)

        c_layout.addSpacing(3)

        # Brush controls section in a subtle elevated panel
        brush_card = QFrame()
        brush_card.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }}
        """)
        b_layout = QVBoxLayout(brush_card)
        b_layout.setContentsMargins(5, 4, 5, 4)
        b_layout.setSpacing(3)

        # Color Tile Swatch
        self.color_btn = GlassColorTile(self._current_color, self)
        self.color_btn.clicked.connect(self._open_color_dialog)
        b_layout.addWidget(self.color_btn)

        # Brush Size Slider & Typography
        size_hdr = QHBoxLayout()
        size_title = QLabel("SIZE")
        size_title.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 8px; font-weight: bold; "
            "border: none; background: transparent; letter-spacing: 0.5px;"
        )
        self.size_label = QLabel("8")
        self.size_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 8.5px; font-weight: bold; "
            "border: none; background: transparent;"
        )
        size_hdr.addWidget(size_title)
        size_hdr.addStretch()
        size_hdr.addWidget(self.size_label)
        b_layout.addLayout(size_hdr)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 200)
        self.size_slider.setValue(8)
        self.size_slider.setFixedHeight(12)
        self.size_slider.setToolTip("Brush Size (1 - 200 px)")
        self.size_slider.valueChanged.connect(self._on_size_slider_changed)
        b_layout.addWidget(self.size_slider)

        # Brush Opacity Slider & Typography
        op_hdr = QHBoxLayout()
        op_title = QLabel("ALPHA")
        op_title.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 8px; font-weight: bold; "
            "border: none; background: transparent; letter-spacing: 0.5px;"
        )
        self.opacity_label = QLabel("100%")
        self.opacity_label.setStyleSheet(
            f"color: {COLOR_TEXT_PRIMARY}; font-size: 8.5px; font-weight: bold; "
            "border: none; background: transparent;"
        )
        op_hdr.addWidget(op_title)
        op_hdr.addStretch()
        op_hdr.addWidget(self.opacity_label)
        b_layout.addLayout(op_hdr)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(1, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedHeight(12)
        self.opacity_slider.setToolTip("Brush Opacity (1% - 100%)")
        self.opacity_slider.valueChanged.connect(self._on_opacity_slider_changed)
        b_layout.addWidget(self.opacity_slider)

        # Quick Reference Swatches Grid (Studio Obsidian)
        swatches_title = QLabel("PALETTE")
        swatches_title.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-size: 8px; font-weight: bold; "
            "border: none; background: transparent; letter-spacing: 0.5px; margin-top: 2px;"
        )
        b_layout.addWidget(swatches_title)

        grid_frame = QFrame()
        grid_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 6px;
            }
        """)
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setContentsMargins(4, 3, 4, 3)
        grid_layout.setSpacing(4)

        swatch_colors = [
            ("#D0BCFF", "Neon Violet"),
            ("#4CD7F6", "Electric Cyan"),
            ("#FDE047", "Warm Yellow"),
            ("#FFB0CD", "Vivid Magenta"),
            ("#10131D", "Deep Obsidian"),
            ("#FFFFFF", "Pure White"),
        ]

        for i, (hex_code, name) in enumerate(swatch_colors):
            btn = QPushButton()
            btn.setFixedSize(16, 16)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{name} ({hex_code})")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {hex_code};
                    border: 1px solid rgba(255, 255, 255, 0.20);
                    border-radius: 8px;
                }}
                QPushButton:hover {{
                    border: 1.5px solid #D0BCFF;
                }}
            """)
            btn.clicked.connect(lambda checked=False, c=hex_code: self.set_color(QColor(c)))
            row, col = divmod(i, 3)
            grid_layout.addWidget(btn, row, col)

        b_layout.addWidget(grid_frame)

        c_layout.addWidget(brush_card)

        self.scroll_area.setWidget(content)
        main_layout.addWidget(self.scroll_area)

    def paintEvent(self, event) -> None:
        """Render floating glass panel with soft shadow, translucent gradient and top highlight."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        card_rect = QRectF(3.0, 3.0, w - 6.0, h - 6.0)
        radius = 14.0

        # Soft black shadow with layered blur simulation
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

    def _open_color_dialog(self) -> None:
        """Open system color chooser dialog."""
        col = QColorDialog.getColor(
            self._current_color,
            self,
            "Select Brush Color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if col.isValid():
            self.set_brush_color(col)
            self.brush_color_changed.emit(col)

    def _update_color_button_style(self) -> None:
        if hasattr(self, "color_btn"):
            self.color_btn.set_color(self._current_color)

    def _on_size_slider_changed(self, value: int) -> None:
        self.size_label.setText(str(value))
        self.brush_size_changed.emit(value)

    def _on_opacity_slider_changed(self, value: int) -> None:
        self.opacity_label.setText(f"{value}%")
        self.brush_opacity_changed.emit(value / 100.0)

    def set_active_tool(self, tool_type: ToolType) -> None:
        """Programmatically switch highlighted tool button."""
        if tool_type in self._tool_buttons:
            self._tool_buttons[tool_type].setChecked(True)

    def set_brush_color(self, color: QColor) -> None:
        """Update displayed color swatch."""
        self._current_color = QColor(color)
        self._update_color_button_style()

    def set_brush_size(self, size: int) -> None:
        """Update brush size slider value."""
        self.size_slider.setValue(size)

    def set_brush_opacity(self, opacity: float) -> None:
        """Update brush opacity slider value."""
        self.opacity_slider.setValue(int(opacity * 100))

    def set_color(self, color: QColor) -> None:
        """Update active drawing color and emit brush_color_changed signal."""
        self.set_brush_color(color)
        self.brush_color_changed.emit(color)
