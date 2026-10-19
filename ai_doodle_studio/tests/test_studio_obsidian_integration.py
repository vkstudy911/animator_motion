"""Tests for Studio Obsidian redesign integration and backend wiring in AI Doodle Studio."""

import os
import unittest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication

from app.drawing.tools import ToolType
from app.ui.command_palette import CommandPaletteDialog
from app.ui.main_window import MainWindow
from app.ui.nodes_view import NodesWorkspaceWidget


class TestStudioObsidianIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.project.modified = False
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_top_toolbar_wiring(self):
        """Verify TopToolbar controls are wired to functional backend handlers."""
        tb = self.window.toolbar

        # 1. Preview button triggers play/pause (requires at least 2 frames)
        self.window._on_add_frame()
        initial_playing = self.window.playback.is_playing
        tb.btn_preview.click()
        self.assertNotEqual(self.window.playback.is_playing, initial_playing)
        tb.btn_preview.click()
        self.assertEqual(self.window.playback.is_playing, initial_playing)

        # 2. Format pill has text and updates
        self.window.toolbar.set_canvas_format_label("16:9")
        self.assertEqual(tb.format_btn.text(), "16:9")

        # 3. Onion skin pill toggle
        tb.btn_onion.click()
        self.assertTrue(self.window.onion_skin.enabled)
        tb.btn_onion.click()
        self.assertFalse(self.window.onion_skin.enabled)

    def test_workspace_switcher_nodes_and_canvas(self):
        """Verify switching to Nodes workspace and returning to Canvas works smoothly."""
        # Initial view is canvas
        self.assertEqual(self.window.center_stack.currentWidget(), self.window.canvas_container)

        # Switch to Nodes
        self.window._on_workspace_changed("nodes")
        self.assertEqual(self.window.center_stack.currentWidget(), self.window.nodes_workspace)
        self.assertTrue(isinstance(self.window.center_stack.currentWidget(), NodesWorkspaceWidget))

        # Return to Canvas via button
        self.window.nodes_workspace.return_to_canvas.emit()
        self.assertEqual(self.window.center_stack.currentWidget(), self.window.canvas_container)

    def test_tools_sidebar_palette_swatches(self):
        """Verify quick swatch buttons immediately update active brush color."""
        sidebar = self.window.tools_sidebar

        # Color before
        test_color = QColor("#4CD7F6")
        sidebar.set_color(test_color)
        self.assertEqual(self.window.canvas.brush_color, test_color)
        self.assertEqual(sidebar._current_color, test_color)

    def test_canvas_container_hud_controls(self):
        """Verify HUD zoom and fit controls call backend canvas zoom functions."""
        cc = self.window.canvas_container
        canvas = self.window.canvas

        # Zoom in
        initial_scale = canvas.scale
        cc.btn_zoom_in.click()
        self.assertGreater(canvas.scale, initial_scale)

        # Zoom out
        cc.btn_zoom_out.click()
        self.assertAlmostEqual(canvas.scale, initial_scale, places=2)

        # Fit
        cc.btn_fit.click()
        self.assertTrue(canvas.scale > 0)

        # Grid toggle
        initial_grid = canvas.show_grid
        cc.btn_grid_toggle.click()
        self.assertNotEqual(canvas.show_grid, initial_grid)
        cc.btn_grid_toggle.click()
        self.assertEqual(canvas.show_grid, initial_grid)

    def test_command_palette_registration_and_execution(self):
        """Verify CommandPaletteDialog registers and executes commands."""
        executed = []
        dlg = CommandPaletteDialog(self.window)
        dlg.register_command("test_cmd", "Execute Test Action", "Test", "Ctrl+T", lambda: executed.append(True))

        # Search and find
        dlg._on_search_changed("Test Action")
        self.assertEqual(len(dlg._filtered_commands), 1)
        self.assertEqual(dlg._filtered_commands[0].id, "test_cmd")

        # Execute
        dlg._execute_current_selection()
        self.assertEqual(len(executed), 1)

    def test_drawing_integrity_after_redesign(self):
        """Verify drawing on canvas still modifies frame pixels correctly in new layout."""
        canvas = self.window.canvas
        cur_frame = self.window.project.get_current_frame()
        self.assertIsNotNone(cur_frame)

        # Draw a stroke with Pen tool
        self.window._select_tool(ToolType.PEN)
        self.window.tools_sidebar.set_brush_color(QColor(255, 0, 0))
        self.window.tools_sidebar.set_brush_size(10)

        # Press, move, release on canvas
        p1 = QPointF(50, 50)
        p2 = QPointF(100, 100)
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press)

        move = QMouseEvent(QMouseEvent.Type.MouseMove, p2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseMoveEvent(move)

        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mouseReleaseEvent(release)

        # Verify frame was modified
        self.assertTrue(cur_frame.modified)
        self.assertTrue(self.window.project.undo_manager.can_undo())


if __name__ == "__main__":
    unittest.main()
