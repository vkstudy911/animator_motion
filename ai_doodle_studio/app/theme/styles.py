"""Theme stylesheets and styling constants for AI Doodle Studio (Studio Obsidian).

Follows the Studio Obsidian / Motion Doodle pro creative suite design system:
- Foundational dark obsidian floors (#0B0E18, #10131D).
- Tactical surface layers:
  * Surface layer 1 (#181B25): tool shelves, docks, timeline rails.
  * Surface layer 2 (#1C1F2A): cards, inspector groups, dropdowns.
  * Surface elevated (#272A34, #32343F): active headers, hover wells, pills.
- Electric Accent Choreography:
  * Neon Violet (#D0BCFF, container #A078FF, pressed #8B5CF6) acts as dominant engine signal.
  * Electric Cyan (#4CD7F6, container #03B5D3) for vector tools, coordinates, and highlights.
  * Vivid Magenta (#FFB0CD, container #F751A1) for keyframe diamonds and alert tags.
- Micro-radii: 4px, 8px, 12px, 16px.
- Subtle 1px glass perimeter highlights and micro-dividers (rgba(255, 255, 255, 0.08)).
"""

from __future__ import annotations

from PySide6.QtGui import QColor

# ── Studio Obsidian Design System Tokens ──
COLOR_APP_BG = "#0B0E18"            # Canvas floor and foundational viewport
COLOR_WORKSPACE_BG = "#10131D"      # Surface dim
COLOR_PANEL_BG = "#181B25"          # Surface layer 1: toolbars, side inspectors, timeline tracks
COLOR_PANEL_CONTAINER = "#1C1F2A"   # Surface layer 2: cards, popovers, dropdowns
COLOR_SURFACE_HIGH = "#272A34"      # Surface elevated: active headers, hover wells
COLOR_SURFACE_HIGHEST = "#32343F"   # Surface highest
COLOR_SURFACE_BRIGHT = "#363944"    # Surface bright highlight

# Glassmorphism & Translucent Panels
COLOR_GLASS_BG = "rgba(24, 27, 37, 0.90)"
COLOR_GLASS_BG_ELEVATED = "rgba(39, 42, 52, 0.85)"
COLOR_GLASS_BG_HOVER = "rgba(255, 255, 255, 0.08)"
COLOR_GLASS_BG_PRESSED = "rgba(255, 255, 255, 0.04)"
COLOR_GLASS_BORDER = "rgba(255, 255, 255, 0.08)"
COLOR_GLASS_BORDER_SUBTLE = "rgba(73, 68, 84, 0.50)"
COLOR_GLASS_BORDER_HOVER = "rgba(208, 188, 255, 0.40)"
COLOR_GLASS_INNER_HIGHLIGHT = "rgba(255, 255, 255, 0.06)"
COLOR_GLASS_SHADOW = "rgba(0, 0, 0, 0.60)"

COLOR_SURFACE_ELEVATED = "rgba(255, 255, 255, 0.05)"
COLOR_SURFACE_HOVER = "rgba(255, 255, 255, 0.10)"
COLOR_SURFACE_PRESSED = "rgba(255, 255, 255, 0.03)"
COLOR_BORDER = "rgba(255, 255, 255, 0.08)"
COLOR_BORDER_SUBTLE = "rgba(73, 68, 84, 0.40)"

# High contrast typography
COLOR_TEXT_PRIMARY = "#E0E2F0"     # High contrast neutral light
COLOR_TEXT_SECONDARY = "#CBC3D7"   # Secondary slate
COLOR_TEXT_MUTED = "#958EA0"       # Outline / muted labels
COLOR_TEXT_DISABLED = "#494454"    # Outline-variant

# Electric Accents
COLOR_ACCENT = "#D0BCFF"           # Neon violet / lilac primary signal
COLOR_ACCENT_CONTAINER = "#A078FF" # Hero glow button & selection fill
COLOR_ON_ACCENT_CONTAINER = "#340080"
COLOR_ACCENT_HOVER = "#E9DDFF"
COLOR_ACCENT_PRESSED = "#8B5CF6"
COLOR_ACCENT_SUBTLE = "rgba(160, 120, 255, 0.22)"
COLOR_ACCENT_BORDER = "rgba(208, 188, 255, 0.70)"

COLOR_SECONDARY = "#4CD7F6"        # Electric cyan (vectors, X-axis, onion before)
COLOR_SECONDARY_CONTAINER = "#03B5D3"
COLOR_TERTIARY = "#FFB0CD"         # Vivid magenta (keyframes, transforms, onion after)
COLOR_TERTIARY_CONTAINER = "#F751A1"

COLOR_DANGER = "#FFB4AB"
COLOR_DANGER_HOVER = "#FFDAD6"
COLOR_DANGER_PRESSED = "#93000A"
COLOR_DANGER_SUBTLE = "rgba(247, 81, 161, 0.20)"
COLOR_DANGER_BORDER = "rgba(247, 81, 161, 0.60)"


DARK_THEME_QSS = f"""
/* Studio Obsidian Global Application Style */
QWidget {{
    background-color: transparent;
    color: {COLOR_TEXT_PRIMARY};
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 12px;
    selection-background-color: {COLOR_ACCENT_CONTAINER};
    selection-color: #ffffff;
}}

/* Main Window & Menus */
QMainWindow {{
    background-color: {COLOR_APP_BG};
}}

QMenuBar {{
    background-color: {COLOR_APP_BG};
    border-bottom: 1px solid {COLOR_GLASS_BORDER_SUBTLE};
    padding: 2px 8px;
    color: {COLOR_TEXT_SECONDARY};
    font-size: 11px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 4px 8px;
    border-radius: 5px;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_GLASS_BG_HOVER};
    color: {COLOR_TEXT_PRIMARY};
}}

QMenu {{
    background-color: rgba(28, 31, 42, 0.96);
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 5px 22px 5px 10px;
    border-radius: 4px;
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
}}

QMenu::item:selected {{
    background-color: {COLOR_ACCENT_CONTAINER};
    color: #ffffff;
}}

QMenu::separator {{
    height: 1px;
    background-color: {COLOR_GLASS_BORDER_SUBTLE};
    margin: 4px 6px;
}}

/* Top Application Bar & ToolBar */
QToolBar {{
    background-color: {COLOR_PANEL_BG};
    border-bottom: 1px solid {COLOR_GLASS_BORDER_SUBTLE};
    spacing: 3px;
    padding: 3px 8px;
}}

QToolBar::separator {{
    width: 1px;
    background-color: {COLOR_GLASS_BORDER_SUBTLE};
    margin: 4px 6px;
}}

/* Push Buttons & Tool Buttons */
QPushButton {{
    background-color: {COLOR_SURFACE_ELEVATED};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 500;
}}

QToolButton {{
    background-color: {COLOR_SURFACE_ELEVATED};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    padding: 3px 6px;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 500;
}}

QPushButton:hover, QToolButton:hover {{
    background-color: {COLOR_SURFACE_HOVER};
    border-color: {COLOR_GLASS_BORDER_HOVER};
    color: #ffffff;
}}

QPushButton:pressed, QToolButton:pressed {{
    background-color: {COLOR_SURFACE_PRESSED};
}}

QPushButton:disabled, QToolButton:disabled {{
    background-color: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.04);
    color: {COLOR_TEXT_DISABLED};
}}

/* Sliders */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {COLOR_SURFACE_HIGH};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background-color: {COLOR_ACCENT_CONTAINER};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background-color: {COLOR_ACCENT};
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.3);
}}

QSlider::handle:horizontal:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

/* SpinBoxes */
QSpinBox {{
    background-color: {COLOR_PANEL_CONTAINER};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 11px;
    color: {COLOR_TEXT_PRIMARY};
}}

QSpinBox:focus {{
    border-color: {COLOR_ACCENT};
}}

/* ComboBoxes */
QComboBox {{
    background-color: {COLOR_PANEL_CONTAINER};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    color: {COLOR_TEXT_PRIMARY};
}}

QComboBox:focus, QComboBox:hover {{
    border-color: {COLOR_GLASS_BORDER_HOVER};
}}

QComboBox::drop-down {{
    border: none;
    width: 16px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_PANEL_CONTAINER};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    selection-background-color: {COLOR_ACCENT_CONTAINER};
    selection-color: #ffffff;
    color: {COLOR_TEXT_PRIMARY};
}}

/* ScrollBars */
QScrollBar:horizontal {{
    height: 6px;
    background-color: transparent;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-width: 20px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: rgba(208, 188, 255, 0.35);
}}

QScrollBar:vertical {{
    width: 6px;
    background-color: transparent;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: rgba(208, 188, 255, 0.35);
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

/* Splitters */
QSplitter::handle {{
    background-color: {COLOR_APP_BG};
}}

QSplitter::handle:horizontal {{
    width: 4px;
}}

QSplitter::handle:vertical {{
    height: 4px;
}}

QSplitter::handle:hover {{
    background-color: {COLOR_ACCENT_CONTAINER};
}}

/* Status Bar */
QStatusBar {{
    background-color: {COLOR_APP_BG};
    border-top: 1px solid {COLOR_GLASS_BORDER_SUBTLE};
    color: {COLOR_TEXT_MUTED};
    font-size: 11px;
    padding: 2px 8px;
}}

/* ToolTip */
QToolTip {{
    background-color: rgba(28, 31, 42, 0.95);
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* Dialogs */
QDialog {{
    background-color: {COLOR_PANEL_BG};
}}

QGroupBox {{
    background-color: rgba(255, 255, 255, 0.03);
    border: 1px solid {COLOR_GLASS_BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: {COLOR_TEXT_SECONDARY};
}}
"""

# ── QColor Palette Tokens for Custom Painting ──
THEME_APP_BG = QColor(11, 14, 24)
THEME_WORKSPACE_BG = QColor(16, 19, 29)
THEME_PANEL_BG = QColor(24, 27, 37)
THEME_PANEL_BORDER = QColor(255, 255, 255, 22)

# Layered glass surfaces (Studio Obsidian depth)
THEME_GLASS_BG = QColor(24, 27, 37, 230)
THEME_GLASS_BG_TOP = QColor(39, 42, 52, 230)
THEME_GLASS_BG_BOTTOM = QColor(20, 23, 33, 230)
THEME_GLASS_BORDER = QColor(255, 255, 255, 22)
THEME_GLASS_BORDER_HOVER = QColor(208, 188, 255, 90)
THEME_GLASS_HIGHLIGHT = QColor(255, 255, 255, 18)
THEME_GLASS_SHADOW = QColor(0, 0, 0, 150)

# Control surfaces inside panels
THEME_ITEM_BG = QColor(255, 255, 255, 10)
THEME_ITEM_HOVER_BG = QColor(255, 255, 255, 22)
THEME_ITEM_BORDER = QColor(255, 255, 255, 20)
THEME_ITEM_HOVER_BORDER = QColor(208, 188, 255, 75)

THEME_ACCENT = QColor(208, 188, 255)            # #D0BCFF Neon Violet
THEME_ACCENT_HOVER = QColor(233, 221, 255)
THEME_ACCENT_BG = QColor(160, 120, 255, 60)
THEME_ACCENT_BORDER = QColor(208, 188, 255, 180)
THEME_ACCENT_PILL = QColor(208, 188, 255)

THEME_SECONDARY = QColor(76, 215, 246)          # #4CD7F6 Electric Cyan
THEME_TERTIARY = QColor(255, 176, 205)          # #FFB0CD Vivid Magenta

THEME_TEXT_PRIMARY = QColor(224, 226, 240)
THEME_TEXT_SECONDARY = QColor(203, 195, 215)
THEME_TEXT_MUTED = QColor(149, 142, 160)
THEME_TEXT_DISABLED = QColor(73, 68, 84)

# Aliases for backward compatibility
GLASS_CONTAINER_BG_TOP = THEME_GLASS_BG_TOP
GLASS_CONTAINER_BG_BOTTOM = THEME_GLASS_BG_BOTTOM
GLASS_CONTAINER_BORDER = THEME_GLASS_BORDER
GLASS_CONTAINER_HIGHLIGHT = THEME_GLASS_HIGHLIGHT

GLASS_ITEM_BG = THEME_ITEM_BG
GLASS_ITEM_BORDER = THEME_ITEM_BORDER
GLASS_ITEM_HOVER_BG = THEME_ITEM_HOVER_BG
GLASS_ITEM_HOVER_BORDER = THEME_ITEM_HOVER_BORDER

GLASS_ACCENT_GRAD_TOP = THEME_ACCENT_BG
GLASS_ACCENT_GRAD_BOTTOM = THEME_ACCENT_BG
GLASS_ACCENT_BORDER = THEME_ACCENT_BORDER
GLASS_ACCENT_PILL = THEME_ACCENT_PILL

GLASS_TEXT_ACTIVE = THEME_TEXT_PRIMARY
GLASS_TEXT_HOVER = THEME_TEXT_PRIMARY
GLASS_TEXT_MUTED = THEME_TEXT_SECONDARY
GLASS_TEXT_DISABLED = THEME_TEXT_DISABLED


def apply_dark_theme(app) -> None:
    """Apply unified dark styling stylesheet to the QApplication."""
    app.setStyleSheet(DARK_THEME_QSS)
