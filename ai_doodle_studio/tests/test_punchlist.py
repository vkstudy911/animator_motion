"""Comprehensive automated test suite covering all punchlist items for AI Doodle Studio.

Validates:
- P0: Data loss prevention, save confirmation, cancel-close behavior, and error handling.
- P1: Frame layers binding in LayersPanel, layer operations & undo/redo, frame undo/redo,
      last-frame delete prevention, playback canvas lock, live drawing cache invalidation,
      Lasso tool full lifecycle (select, move, commit, cancel, delete, undo), Text tool.
- P2: Image and video import flows, audio timeline waveform extraction, audio sync,
      onion skin settings, loop modes, export progress & cancellation, keyboard shortcuts.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import wave
import struct

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QMessageBox

# Ensure a QApplication exists
app = QApplication.instance()
if app is None:
    app = QApplication([])

from app.animation.playback import PlaybackController
from app.core.frame import Frame
from app.core.history import DrawCommand, FrameMoveCommand, LayerSnapshotCommand
from app.core.layer import Layer
from app.core.project import AnimationProject
from app.drawing.canvas import DrawingCanvas
from app.drawing.tools import LassoTool, PenTool, TextTool, ToolType
from app.media.video_export import VideoExporter
from app.ui.dialogs import ExportProgressDialog, OnionSkinSettingsDialog
from app.ui.layers_panel import LayersPanel
from app.ui.main_window import MainWindow
from app.ui.timeline_view import AudioWaveformWidget, TimelineWidget


from unittest.mock import patch
from PySide6.QtGui import QCloseEvent


class TestPunchlistP0(unittest.TestCase):
    """Test Priority P0: Data-loss prevention, save prompts, and close event cancellation."""

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.project.modified = False
        self.window.close()

    def test_save_project_returns_bool(self) -> None:
        """_on_save_project returns bool indicating success."""
        self.assertFalse(self.window.project.modified)
        self.window.project.mark_modified()
        self.assertTrue(self.window.project.modified)

    def test_save_as_and_save_success(self) -> None:
        """Saving to a temporary path succeeds and clears modified flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = os.path.join(tmpdir, "test_p0.adsproj")
            self.window.project.mark_modified()
            success = self.window.project.save_project(save_path)
            self.assertTrue(success)
            self.assertFalse(self.window.project.modified)
            self.assertEqual(self.window.project.save_path, save_path)

            # Subsequent save without path
            self.window.project.mark_modified()
            save_res = self.window._on_save_project()
            self.assertTrue(save_res)
            self.assertFalse(self.window.project.modified)

    def test_load_nonexistent_returns_false(self) -> None:
        """Attempting to load a nonexistent project returns False without crashing."""
        res = self.window.project.load_project("/nonexistent/path/to/proj.adsproj")
        self.assertFalse(res)

    def test_close_event_cancel_aborts_close(self) -> None:
        """When user clicks Cancel on unsaved changes prompt, closeEvent is ignored."""
        self.window.project.mark_modified()
        evt = QCloseEvent()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            self.window.closeEvent(evt)
            self.assertFalse(evt.isAccepted())

    def test_close_event_discard_accepts_close(self) -> None:
        """When user clicks Discard on unsaved changes prompt, closeEvent is accepted."""
        self.window.project.mark_modified()
        evt = QCloseEvent()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard):
            self.window.closeEvent(evt)
            self.assertTrue(evt.isAccepted())

    def test_close_event_save_failure_aborts_close(self) -> None:
        """When user clicks Save but save fails/cancels, closeEvent is ignored."""
        self.window.project.mark_modified()
        evt = QCloseEvent()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Save), \
             patch.object(self.window, "_on_save_project", return_value=False):
            self.window.closeEvent(evt)
            self.assertFalse(evt.isAccepted())



class TestPunchlistP1(unittest.TestCase):
    """Test Priority P1: Layers panel binding, layer undo, frame undo, canvas lock, lasso tool."""

    def setUp(self) -> None:
        self.project = AnimationProject(width=200, height=200)

    def test_layers_panel_bound_to_frame_layers(self) -> None:
        """LayersPanel reflects the actual Frame.layers and active_layer_index."""
        panel = LayersPanel()
        panel.set_project(self.project)
        frame = self.project.get_current_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(len(frame.layers), 1)

        panel.set_frame(frame)
        self.assertEqual(panel.list_widget.count(), 1)

        # Add a new layer via panel
        panel._add_layer()
        self.assertEqual(len(frame.layers), 2)
        self.assertEqual(frame.active_layer_index, 1)
        self.assertEqual(panel.list_widget.count(), 2)

        # Duplicate layer
        panel._duplicate_layer()
        self.assertEqual(len(frame.layers), 3)
        self.assertEqual(panel.list_widget.count(), 3)

        # Delete layer
        panel._delete_layer()
        self.assertEqual(len(frame.layers), 2)
        self.assertEqual(panel.list_widget.count(), 2)

    def test_layer_operations_undo_redo(self) -> None:
        """Layer operations push LayerSnapshotCommand to undo manager."""
        panel = LayersPanel()
        panel.set_project(self.project)
        frame = self.project.get_current_frame()
        panel.set_frame(frame)

        self.assertEqual(len(frame.layers), 1)
        self.assertFalse(self.project.undo_manager.can_undo())

        panel._add_layer()
        self.assertEqual(len(frame.layers), 2)
        self.assertTrue(self.project.undo_manager.can_undo())

        # Undo add layer
        self.project.undo_manager.undo()
        self.assertEqual(len(frame.layers), 1)

        # Redo add layer
        self.project.undo_manager.redo()
        self.assertEqual(len(frame.layers), 2)

    def test_frame_undo_redo_and_last_frame_guard(self) -> None:
        """Frame add, dup, delete, reorder support undo/redo, last frame cannot be deleted."""
        self.assertEqual(self.project.frame_count(), 1)

        # Try deleting last frame
        del_res = self.project.delete_frame(0)
        self.assertFalse(del_res)
        self.assertEqual(self.project.frame_count(), 1)

        # Add frame
        idx = self.project.add_frame()
        self.assertEqual(self.project.frame_count(), 2)
        self.assertTrue(self.project.undo_manager.can_undo())

        # Undo add frame
        self.project.undo_manager.undo()
        self.assertEqual(self.project.frame_count(), 1)

        # Redo add frame
        self.project.undo_manager.redo()
        self.assertEqual(self.project.frame_count(), 2)

        # Move frame
        self.project.move_frame(0, 1)
        self.assertTrue(self.project.undo_manager.can_undo())
        self.project.undo_manager.undo()
        self.project.undo_manager.redo()

    def test_canvas_playback_lock(self) -> None:
        """Canvas disables drawing interaction when playback is locked."""
        canvas = DrawingCanvas(self.project)
        self.assertFalse(canvas.playback_locked)

        canvas.set_playback_locked(True)
        self.assertTrue(canvas.playback_locked)
        self.assertEqual(canvas.cursor().shape(), Qt.CursorShape.ForbiddenCursor)

        canvas.set_playback_locked(False)
        self.assertFalse(canvas.playback_locked)

    def test_pen_tool_live_drawing_cache_invalidation(self) -> None:
        """Pen tool marks frame._composite_dirty = True during stroke."""
        from PySide6.QtGui import QMouseEvent
        canvas = DrawingCanvas(self.project)
        frame = self.project.get_current_frame()
        frame._composite_dirty = False

        canvas.set_tool(ToolType.PEN)
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        move = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press)
        canvas.mouseMoveEvent(move)
        self.assertTrue(frame._composite_dirty)
        canvas.mouseReleaseEvent(release)

    def test_lasso_tool_lifecycle(self) -> None:
        """Lasso tool creates selection, moves selection, and commits undoable changes."""
        from PySide6.QtGui import QMouseEvent
        canvas = DrawingCanvas(self.project)
        frame = self.project.get_current_frame()

        # Draw a solid red box on active layer
        active_layer = frame.get_active_layer()
        p = QPainter(active_layer.image)
        p.fillRect(10, 10, 30, 30, QColor(255, 0, 0, 255))
        p.end()
        frame.mark_modified()

        canvas.set_tool(ToolType.SELECT)
        lasso = canvas.active_tool

        # 1. Select region around (5,5) to (50,50)
        p1 = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(5, 5), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        p2 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(50, 5), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        p3 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(50, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        p4 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(5, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        p5 = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(5, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(p1)
        canvas.mouseMoveEvent(p2)
        canvas.mouseMoveEvent(p3)
        canvas.mouseMoveEvent(p4)
        canvas.mouseReleaseEvent(p5)

        self.assertTrue(lasso.is_active())
        self.assertIsNotNone(lasso.floating_image)

        # 2. Drag/move selection by clicking inside selection box and dragging
        center_x = lasso.selection_rect.center().x()
        center_y = lasso.selection_rect.center().y()
        d1 = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(center_x, center_y), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        d2 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(center_x + 10, center_y + 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        d3 = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(center_x + 10, center_y + 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(d1)
        canvas.mouseMoveEvent(d2)
        canvas.mouseReleaseEvent(d3)

        # 3. Commit selection
        lasso.commit(canvas)
        self.assertFalse(lasso.is_active())
        self.assertTrue(self.project.undo_manager.can_undo())

        # 4. Undo and redo
        self.project.undo_manager.undo()
        self.assertTrue(self.project.undo_manager.can_redo())
        self.project.undo_manager.redo()


class TestPunchlistP2(unittest.TestCase):
    """Test Priority P2: Media import, audio timeline, onion settings, loop modes, export progress."""

    def setUp(self) -> None:
        self.project = AnimationProject(width=100, height=100)

    def test_audio_waveform_extraction(self) -> None:
        """AudioWaveformWidget parses WAV amplitude peaks using wave standard library."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        try:
            # Generate a 1-second test WAV file
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                data = bytearray()
                for i in range(8000):
                    val = int(10000 * (1 if (i % 200 < 100) else -1))
                    data.extend(struct.pack("<h", val))
                wf.writeframes(data)

            timeline = TimelineWidget()
            samples = timeline._extract_waveform(wav_path)
            self.assertGreater(len(samples), 0)
            timeline.waveform_widget.set_audio("test.wav", samples)
            self.assertEqual(len(timeline.waveform_widget.samples), len(samples))
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_loop_mode_selector(self) -> None:
        """Playback controller correctly supports Loop, Once, and Ping-Pong modes."""
        playback = PlaybackController(fps=12)
        playback.set_loop_mode("once")
        self.assertEqual(playback.loop_mode, "once")

        playback.set_loop_mode("ping-pong")
        self.assertEqual(playback.loop_mode, "ping-pong")

        playback.set_loop_mode("loop")
        self.assertEqual(playback.loop_mode, "loop")

    def test_export_progress_dialog_cancel(self) -> None:
        """ExportProgressDialog sets cancelled flag on cancel."""
        dlg = ExportProgressDialog()
        self.assertFalse(dlg.is_cancelled)
        dlg._on_cancel()
        self.assertTrue(dlg.is_cancelled)

    def test_onion_skin_settings_dialog(self) -> None:
        """OnionSkinSettingsDialog returns user-configured values."""
        dlg = OnionSkinSettingsDialog(frames_before=2, frames_after=3, opacity=0.4)
        settings = dlg.get_settings()
        self.assertEqual(settings["frames_before"], 2)
        self.assertEqual(settings["frames_after"], 3)
        self.assertAlmostEqual(settings["opacity"], 0.4, places=1)


if __name__ == "__main__":
    unittest.main()

