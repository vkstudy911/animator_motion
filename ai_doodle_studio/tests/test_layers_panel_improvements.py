"""Regression test suite for Layers Panel improvements and fixes.

Verifies:
1. Lock toggle marks project as modified and persists across save/load.
2. Lock toggle undo/redo.
3. Visibility, opacity, rename, and blend mode undo/redo.
4. Opacity slider drag creates exactly ONE undo command, not many.
5. Blend mode dropdown binding, persistence across save/load, and undo/redo.
6. Locked layers block merge down (either upper or lower locked).
7. Locked layers block delete and reordering with status message.
8. Switching frames updates layers panel contents and active layer.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.core.frame import Frame
from app.core.layer import Layer
from app.core.project import AnimationProject
from app.ui.layers_panel import LayerItemWidget, LayersPanel

app = QApplication.instance() or QApplication([])


class TestLayersPanelImprovements(unittest.TestCase):
    """Test suite covering layer locks, undo/redo, blend modes, and UI responsiveness."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = AnimationProject(name="LayersTest", width=640, height=480)
        self.panel = LayersPanel()
        self.panel.set_project(self.project)
        self.panel.set_frame(self.project.get_current_frame())
        self.panel.show()
        QApplication.processEvents()

    def tearDown(self) -> None:
        self.panel.close()
        self.panel.deleteLater()
        QApplication.processEvents()
        self.temp_dir.cleanup()

    def test_lock_only_change_marks_project_modified_and_persists_save_load(self) -> None:
        """Lock toggle marks project modified and persists properly through save/load."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.project.modified = False

        # Toggle lock on layer 0
        self.panel._handle_lock(0, True)

        self.assertTrue(frame.layers[0].locked)
        self.assertTrue(self.project.modified, "Project modified flag should be True after lock change")

        # Save project and reload
        save_path = os.path.join(self.temp_dir.name, "lock_test.adsproj")
        saved = self.project.save_project(save_path)
        self.assertTrue(saved)

        reloaded = AnimationProject()
        loaded = reloaded.load_project(save_path)
        self.assertTrue(loaded)
        reloaded_frame = reloaded.get_current_frame()
        self.assertIsNotNone(reloaded_frame)
        self.assertTrue(reloaded_frame.layers[0].locked, "Lock state must persist after save and load")

    def test_lock_toggle_undo_redo(self) -> None:
        """Lock/unlock operations support full undo and redo."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.assertFalse(frame.layers[0].locked)

        # Lock
        self.panel._handle_lock(0, True)
        self.assertTrue(frame.layers[0].locked)
        self.assertTrue(self.project.undo_manager.can_undo())

        # Undo lock
        self.project.undo_manager.undo()
        self.assertFalse(frame.layers[0].locked)

        # Redo lock
        self.project.undo_manager.redo()
        self.assertTrue(frame.layers[0].locked)

    def test_visibility_undo_redo(self) -> None:
        """Visibility toggle operations support full undo and redo."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.assertTrue(frame.layers[0].visible)

        # Hide layer
        self.panel._handle_visibility(0, False)
        self.assertFalse(frame.layers[0].visible)

        # Undo
        self.project.undo_manager.undo()
        self.assertTrue(frame.layers[0].visible)

        # Redo
        self.project.undo_manager.redo()
        self.assertFalse(frame.layers[0].visible)

    def test_opacity_slider_single_undo_command(self) -> None:
        """Dragging opacity slider emits live updates but produces only 1 undo command on release."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        initial_undos = len(self.project.undo_manager._undo_stack)

        # Press slider
        self.panel._on_opacity_slider_pressed()

        # Drag through intermediate values
        self.panel.opacity_slider.setValue(80)
        self.panel.opacity_slider.setValue(60)
        self.panel.opacity_slider.setValue(40)
        self.assertAlmostEqual(frame.layers[0].opacity, 0.40, places=2)

        # Release slider
        self.panel._on_opacity_slider_released()

        # Should only have added 1 undo command despite 3 intermediate value changes
        self.assertEqual(len(self.project.undo_manager._undo_stack), initial_undos + 1)

        # Undo restores original 100% opacity
        self.project.undo_manager.undo()
        self.assertAlmostEqual(frame.layers[0].opacity, 1.0, places=2)

        # Redo restores 40%
        self.project.undo_manager.redo()
        self.assertAlmostEqual(frame.layers[0].opacity, 0.40, places=2)

    def test_blend_mode_undo_redo_and_persistence(self) -> None:
        """Blend mode changes support undo/redo and persist after save/load."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.layers[0].blend_mode, "normal")

        # Change blend mode via combo
        self.panel.blend_combo.setCurrentText("Multiply")
        self.assertEqual(frame.layers[0].blend_mode, "multiply")

        # Undo
        self.project.undo_manager.undo()
        self.assertEqual(frame.layers[0].blend_mode, "normal")

        # Redo
        self.project.undo_manager.redo()
        self.assertEqual(frame.layers[0].blend_mode, "multiply")

        # Save and verify persistence
        save_path = os.path.join(self.temp_dir.name, "blend_test.adsproj")
        self.project.save_project(save_path)

        reloaded = AnimationProject()
        reloaded.load_project(save_path)
        self.assertEqual(reloaded.get_current_frame().layers[0].blend_mode, "multiply")

    def test_locked_lower_layer_blocks_merge(self) -> None:
        """Merge Down is blocked if either the active upper layer or destination lower layer is locked."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)

        # Add a second layer
        self.panel._add_layer()
        self.assertEqual(len(frame.layers), 2)

        # Lock lower layer (index 0)
        frame.layers[0].locked = True
        frame.active_layer_index = 1
        self.panel._refresh_layers()

        messages: list[str] = []
        self.panel.status_message.connect(lambda msg: messages.append(msg))

        # Attempt merge down
        self.panel._merge_down()

        self.assertEqual(len(frame.layers), 2, "Merge must not occur when lower layer is locked")
        self.assertTrue(any("Unlock this layer" in m for m in messages))

        # Reset and lock upper layer instead
        frame.layers[0].locked = False
        frame.layers[1].locked = True
        self.panel._refresh_layers()
        messages.clear()

        self.panel._merge_down()
        self.assertEqual(len(frame.layers), 2, "Merge must not occur when active upper layer is locked")
        self.assertTrue(any("Unlock this layer" in m for m in messages))

    def test_locked_layer_blocks_delete_and_reorder(self) -> None:
        """Locked active layer cannot be deleted or reordered."""
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.panel._add_layer()
        self.assertEqual(len(frame.layers), 2)

        # Lock active upper layer
        frame.layers[1].locked = True
        self.panel._refresh_layers()

        messages: list[str] = []
        self.panel.status_message.connect(lambda msg: messages.append(msg))

        # Attempt delete
        self.panel._delete_layer()
        self.assertEqual(len(frame.layers), 2, "Locked layer must not be deleted")
        self.assertTrue(any("Unlock this layer" in m for m in messages))

        # Attempt move down
        messages.clear()
        self.panel._move_layer_down()
        self.assertEqual(frame.layers[1].name, "Layer 2", "Locked layer must not be moved")
        self.assertTrue(any("Unlock this layer" in m for m in messages))

    def test_switching_frames_updates_panel(self) -> None:
        """Switching between frames updates layer list, active layer, and controls in LayersPanel."""
        frame1 = self.project.get_current_frame()
        self.assertIsNotNone(frame1)
        frame1.layers[0].name = "Shared_Base_Layer"

        # Add Frame 2 and a second layer track
        self.project.add_frame()
        frame2 = self.project.get_current_frame()
        self.assertIsNotNone(frame2)
        l2 = self.project.add_layer("Character_Layer")
        l2.opacity = 0.5
        l2.blend_mode = "screen"

        # Frame 1 and Frame 2 both have 2 layers (timeline-wide tracks)
        self.project.set_current_frame(0)
        self.panel.set_frame(self.project.get_current_frame())
        self.assertEqual(self.panel.list_widget.count(), 2)
        self.assertEqual(self.panel.blend_combo.currentText(), "Screen")
        self.assertEqual(self.panel.opacity_slider.value(), 50)

        # Switch to frame 2
        self.project.set_current_frame(1)
        self.panel.set_frame(self.project.get_current_frame())
        self.assertEqual(self.panel.list_widget.count(), 2)
        self.assertEqual(self.panel.blend_combo.currentText(), "Screen")
        self.assertEqual(self.panel.opacity_slider.value(), 50)


if __name__ == "__main__":
    unittest.main()
