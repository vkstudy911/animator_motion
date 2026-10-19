"""Regression tests for runtime bug fixes in AI Doodle Studio.

Validates:
1. MainWindow Play/Pause without audio track: no crash, smooth state changes.
2. Audio track load and clear: audio_file_path set and reset properly.
3. All three loop modes (Loop, Once, Ping-Pong) advance frames correctly with timer ticks.
4. Import Image -> New Frame: creates exactly one valid frame, centers/scales, undo/redo works.
5. Import Image -> Current Layer: modifies only selected layer, undo/redo works.
6. Import Image into locked/hidden layer: shows safe warning, no mutation, no crash.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QMessageBox

app = QApplication.instance() or QApplication([])

from app.animation.playback import LoopMode, PlaybackController
from app.core.frame import Frame
from app.core.layer import Layer
from app.core.project import AnimationProject
from app.ui.dialogs import ImportImageDialog
from app.ui.main_window import MainWindow
from app.ui.timeline_view import TimelineWidget


class TestRuntimeRegressions(unittest.TestCase):
    """Test suite covering the 5 runtime bug fixes."""

    def setUp(self) -> None:
        self.window = MainWindow()

    def tearDown(self) -> None:
        self.window.project.modified = False
        self.window.close()

    def test_play_pause_without_audio_no_crash(self) -> None:
        """Play/Pause functions smoothly without an audio track without throwing AttributeError."""
        self.assertIsNone(self.window.timeline.audio_file_path)
        self.assertFalse(self.window.playback.is_playing)

        # Toggle to Play
        self.window._on_play_pause()
        self.assertTrue(self.window.playback.is_playing)

        # Toggle to Pause
        self.window._on_play_pause()
        self.assertFalse(self.window.playback.is_playing)

    def test_audio_file_path_set_and_cleared(self) -> None:
        """Loading and clearing audio tracks properly manages audio_file_path."""
        timeline = self.window.timeline
        self.assertIsNone(timeline.audio_file_path)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name

        try:
            # Simulate loading audio
            with patch.object(timeline, "_extract_waveform", return_value=[0.5] * 10):
                timeline.audio_file_path = wav_path
                timeline.audio_loaded.emit(wav_path)

            self.assertEqual(timeline.audio_file_path, wav_path)

            # Clear audio
            timeline._on_clear_audio_clicked()
            self.assertIsNone(timeline.audio_file_path)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def test_all_three_loop_modes_advance_frames(self) -> None:
        """Loop, Once, and Ping-Pong modes all correctly advance playback frames."""
        playback = PlaybackController(fps=12)
        playback.set_total_frames(3)

        # 1. Loop Mode: 0 -> 1 -> 2 -> 0
        playback.set_loop_mode("loop")
        self.assertEqual(playback.loop_mode, LoopMode.LOOP)
        playback.set_current_frame(0)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 1)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 2)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 0)

        # 2. Once Mode: 0 -> 1 -> 2 -> pause
        playback.set_loop_mode("once")
        self.assertEqual(playback.loop_mode, LoopMode.ONCE)
        playback.play()
        playback.set_current_frame(0)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 1)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 2)
        playback._on_timer_tick()
        self.assertFalse(playback.is_playing)
        self.assertEqual(playback.current_frame, 2)

        # 3. Ping-Pong Mode: 0 -> 1 -> 2 -> 1 -> 0 -> 1
        playback.set_loop_mode("ping_pong")
        self.assertEqual(playback.loop_mode, LoopMode.PING_PONG)
        playback.set_current_frame(0)
        playback._ping_pong_direction = 1
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 1)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 2)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 1)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 0)
        playback._on_timer_tick()
        self.assertEqual(playback.current_frame, 1)

        # 4. Fallback on invalid mode
        playback.set_loop_mode("unknown_mode")
        self.assertEqual(playback.loop_mode, LoopMode.LOOP)

    def test_import_image_new_frame_and_undo_redo(self) -> None:
        """Importing image as a new frame creates one frame and supports undo/redo."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_path = f.name

        try:
            # Create a 200x200 solid blue test image
            src = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
            src.fill(QColor(0, 0, 255, 255))
            src.save(img_path)

            initial_count = self.window.project.frame_count()
            self.assertEqual(initial_count, 1)

            # Mock file dialog and import dialog
            with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(img_path, "")), \
                 patch.object(ImportImageDialog, "exec", return_value=ImportImageDialog.DialogCode.Accepted), \
                 patch.object(ImportImageDialog, "get_import_mode", return_value="new_frame"):
                self.window._on_import_image()

            # Verify new frame added
            self.assertEqual(self.window.project.frame_count(), 2)
            self.assertEqual(self.window.project.current_frame_index, 1)

            new_frame = self.window.project.get_current_frame()
            self.assertIsNotNone(new_frame)
            active_img = new_frame.get_active_layer_image()
            # Center of the 1280x720 canvas should contain blue
            cx, cy = self.window.project.canvas_width // 2, self.window.project.canvas_height // 2
            self.assertEqual(active_img.pixelColor(cx, cy).blue(), 255)

            # Test Undo
            self.window.project.undo_manager.undo()
            self.assertEqual(self.window.project.frame_count(), 1)

            # Test Redo
            self.window.project.undo_manager.redo()
            self.assertEqual(self.window.project.frame_count(), 2)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_import_image_current_layer_and_undo_redo(self) -> None:
        """Importing image onto current layer modifies only selected layer with undo/redo."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_path = f.name

        try:
            # Create a green test image
            src = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
            src.fill(QColor(0, 255, 0, 255))
            src.save(img_path)

            cur_frame = self.window.project.get_current_frame()
            # Add second layer and make it active
            layer2 = cur_frame.add_layer("Layer 2")
            cur_frame.set_active_layer_index(1)

            # Set layer 1 (bottom) to red
            layer1 = cur_frame.layers[0]
            layer1.image.fill(QColor(255, 0, 0, 255))
            # Set layer 2 to transparent initially
            layer2.image.fill(QColor(0, 0, 0, 0))

            cx, cy = self.window.project.canvas_width // 2, self.window.project.canvas_height // 2
            self.assertEqual(layer2.image.pixelColor(cx, cy).alpha(), 0)

            # Import onto current layer
            with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(img_path, "")), \
                 patch.object(ImportImageDialog, "exec", return_value=ImportImageDialog.DialogCode.Accepted), \
                 patch.object(ImportImageDialog, "get_import_mode", return_value="current_layer"):
                self.window._on_import_image()

            # Layer 2 should have green pixels
            self.assertEqual(layer2.image.pixelColor(cx, cy).green(), 255)
            # Layer 1 should still be red (unmodified)
            self.assertEqual(layer1.image.pixelColor(cx, cy).red(), 255)

            # Undo
            self.window.project.undo_manager.undo()
            self.assertEqual(layer2.image.pixelColor(cx, cy).alpha(), 0)
            self.assertEqual(layer1.image.pixelColor(cx, cy).red(), 255)

            # Redo
            self.window.project.undo_manager.redo()
            self.assertEqual(layer2.image.pixelColor(cx, cy).green(), 255)
            self.assertEqual(layer1.image.pixelColor(cx, cy).red(), 255)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_import_image_locked_or_hidden_layer_guard(self) -> None:
        """Importing into locked or hidden layer triggers warning without mutations."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img_path = f.name

        try:
            src = QImage(50, 50, QImage.Format.Format_ARGB32_Premultiplied)
            src.fill(QColor(255, 255, 0, 255))
            src.save(img_path)

            cur_frame = self.window.project.get_current_frame()
            layer = cur_frame.get_active_layer()
            layer.locked = True

            with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(img_path, "")), \
                 patch.object(ImportImageDialog, "exec", return_value=ImportImageDialog.DialogCode.Accepted), \
                 patch.object(ImportImageDialog, "get_import_mode", return_value="current_layer"), \
                 patch.object(QMessageBox, "warning") as mock_warn:
                self.window._on_import_image()
                mock_warn.assert_called_once()
                self.assertFalse(self.window.project.undo_manager.can_undo())

            layer.locked = False
            layer.visible = False

            with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=(img_path, "")), \
                 patch.object(ImportImageDialog, "exec", return_value=ImportImageDialog.DialogCode.Accepted), \
                 patch.object(ImportImageDialog, "get_import_mode", return_value="current_layer"), \
                 patch.object(QMessageBox, "warning") as mock_warn2:
                self.window._on_import_image()
                mock_warn2.assert_called_once()
                self.assertFalse(self.window.project.undo_manager.can_undo())
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)


if __name__ == "__main__":
    unittest.main()
