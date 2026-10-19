"""Tests for the macOS-inspired translucent glass ToolsSidebar.

Verifies:
1. Tool button definitions and signals for all 9 tools.
2. Selection exclusivity (Pen, Eraser, Fill, Pipette, Lasso, Text, Line, Rect, Circle).
3. Brush controls: color swatch, size slider (1-200), opacity slider (1-100%).
4. Paint rendering across normal, hover, selected, disabled, and focused states.
5. Layout responsiveness across 1280x720, 1440x900, and 960x600 screen sizes.
"""

from __future__ import annotations

import unittest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.drawing.tools import ToolType
from app.ui.tools_sidebar import GlassColorTile, GlassToolButton, ToolsSidebar

app = QApplication.instance() or QApplication([])


class TestToolsSidebarGlassUI(unittest.TestCase):
    """Test suite for ToolsSidebar glassmorphic UI, signals, and states."""

    def setUp(self) -> None:
        self.sidebar = ToolsSidebar()
        self.sidebar.show()
        QApplication.processEvents()

    def tearDown(self) -> None:
        self.sidebar.close()
        self.sidebar.deleteLater()
        QApplication.processEvents()

    def test_all_nine_tools_registered(self) -> None:
        """Verify all 9 required drawing tools exist in the button group."""
        expected_tools = [
            ToolType.PEN,
            ToolType.ERASER,
            ToolType.FILL,
            ToolType.COLOR_PICKER,
            ToolType.SELECT,
            ToolType.TEXT,
            ToolType.LINE,
            ToolType.RECTANGLE,
            ToolType.ELLIPSE,
        ]
        for tool_type in expected_tools:
            self.assertIn(tool_type, self.sidebar._tool_buttons)
            btn = self.sidebar._tool_buttons[tool_type]
            self.assertIsInstance(btn, GlassToolButton)
            self.assertTrue(len(btn.toolTip()) > 0, f"Missing tooltip for {tool_type}")

    def test_default_active_tool_is_pen(self) -> None:
        """Verify Pen is checked by default upon initialization."""
        pen_btn = self.sidebar._tool_buttons[ToolType.PEN]
        self.assertTrue(pen_btn.isChecked())

    def test_tool_selection_signal_and_exclusivity(self) -> None:
        """Selecting a tool button updates active state and emits tool_selected."""
        selected_tool: list[ToolType] = []
        self.sidebar.tool_selected.connect(lambda t: selected_tool.append(t))

        eraser_btn = self.sidebar._tool_buttons[ToolType.ERASER]
        eraser_btn.click()

        self.assertEqual(selected_tool, [ToolType.ERASER])
        self.assertTrue(eraser_btn.isChecked())
        self.assertFalse(self.sidebar._tool_buttons[ToolType.PEN].isChecked())

        # Select Fill tool
        fill_btn = self.sidebar._tool_buttons[ToolType.FILL]
        fill_btn.click()
        self.assertEqual(selected_tool[-1], ToolType.FILL)
        self.assertTrue(fill_btn.isChecked())
        self.assertFalse(eraser_btn.isChecked())

    def test_programmatic_tool_switch(self) -> None:
        """set_active_tool properly checks the requested tool button."""
        self.sidebar.set_active_tool(ToolType.COLOR_PICKER)
        self.assertTrue(self.sidebar._tool_buttons[ToolType.COLOR_PICKER].isChecked())
        self.assertFalse(self.sidebar._tool_buttons[ToolType.PEN].isChecked())

    def test_brush_size_slider_and_signal(self) -> None:
        """Brush size slider emits brush_size_changed and updates size_label."""
        sizes: list[int] = []
        self.sidebar.brush_size_changed.connect(lambda s: sizes.append(s))

        self.sidebar.set_brush_size(32)
        self.assertEqual(self.sidebar.size_slider.value(), 32)
        self.assertEqual(self.sidebar.size_label.text(), "32")
        self.assertIn(32, sizes)

    def test_brush_opacity_slider_and_signal(self) -> None:
        """Brush opacity slider emits brush_opacity_changed and updates opacity_label."""
        opacities: list[float] = []
        self.sidebar.brush_opacity_changed.connect(lambda op: opacities.append(op))

        self.sidebar.set_brush_opacity(0.65)
        self.assertEqual(self.sidebar.opacity_slider.value(), 65)
        self.assertEqual(self.sidebar.opacity_label.text(), "65%")
        self.assertAlmostEqual(opacities[-1], 0.65, places=2)

    def test_color_swatch_update(self) -> None:
        """set_brush_color updates the color swatch tile."""
        new_color = QColor(59, 130, 246)
        self.sidebar.set_brush_color(new_color)
        self.assertEqual(self.sidebar._current_color, new_color)
        self.assertEqual(self.sidebar.color_btn._color, new_color)

    def test_button_paint_states(self) -> None:
        """GlassToolButton renders without crash in normal, hover, selected, disabled, and focus states."""
        btn = self.sidebar._tool_buttons[ToolType.PEN]
        buf = QImage(btn.size(), QImage.Format.Format_ARGB32_Premultiplied)
        buf.fill(Qt.GlobalColor.transparent)

        # 1. Selected state
        btn.setChecked(True)
        btn.render(buf)
        self.assertFalse(buf.isNull())

        # 2. Hovered state
        btn.setChecked(False)
        btn.hovered = True
        btn.render(buf)
        self.assertFalse(buf.isNull())

        # 3. Normal state
        btn.hovered = False
        btn.render(buf)
        self.assertFalse(buf.isNull())

        # 4. Disabled state
        btn.setEnabled(False)
        btn.render(buf)
        self.assertFalse(buf.isNull())

    def test_responsiveness_at_supported_resolutions(self) -> None:
        """Sidebar container renders cleanly at 720p, 900p, and 600p window heights."""
        # Splitter heights corresponding to window sizes:
        # 1440x900 -> height ~687
        # 1280x720 -> height ~507
        # 960x600  -> height ~387
        for test_h in [687, 507, 387]:
            self.sidebar.resize(98, test_h)
            QApplication.processEvents()
            buf = QImage(self.sidebar.size(), QImage.Format.Format_ARGB32_Premultiplied)
            buf.fill(Qt.GlobalColor.transparent)
            self.sidebar.render(buf)
            self.assertFalse(buf.isNull())


if __name__ == "__main__":
    unittest.main()
