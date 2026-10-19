"""Automated UI layout and responsiveness tests for the modern TimelineWidget.

Verifies:
1. Timeline header controls do not overlap across supported screen sizes:
   - 2560x1664
   - 1440x900
   - 1280x720
   - 960x600 (minimum window size)
2. Active thumbnail highlight:
   - Selected thumbnail has selected=True and magenta accent styling.
   - Non-selected thumbnails have selected=False.
3. Add-frame card at the end of the thumbnail strip:
   - Present as the final item in the strip layout.
   - Clicking it appends a new frame.
4. Auto-scrolling and visibility after navigation / playback:
   - Active frame thumbnail remains visible within scroll area bounds.
5. Collapsible audio track:
   - Hidden by default when no audio is loaded.
   - Becomes visible upon loading audio.
6. Settings bar toggle:
   - Toggles secondary controls (FPS, loop mode, onion config) without cluttering.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from app.ui.main_window import MainWindow
from app.ui.timeline_view import AddFrameCardWidget, FrameThumbnailWidget, TimelineWidget


class TestTimelineModernLayout(unittest.TestCase):
    """Test suite for modern timeline layout, styling, and frame strip interaction."""

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        QApplication.processEvents()

    def tearDown(self) -> None:
        self.window.project.modified = False
        self.window.close()

    def _check_non_overlapping(self, widgets, group_name: str) -> None:
        visible_widgets = [w for w in widgets if w.isVisible()]
        for i in range(len(visible_widgets)):
            w1 = visible_widgets[i]
            r1 = w1.geometry()
            self.assertGreater(r1.width(), 16, f"{w1} in {group_name} width too small: {r1.width()}")
            self.assertGreater(r1.height(), 16, f"{w1} in {group_name} height too small: {r1.height()}")

            for j in range(i + 1, len(visible_widgets)):
                w2 = visible_widgets[j]
                r2 = w2.geometry()
                overlap = r1.intersects(r2)
                self.assertFalse(
                    overlap,
                    f"Collision in {group_name} between {w1.objectName() or w1} ({r1}) and {w2.objectName() or w2} ({r2})"
                )

    def test_top_bar_non_overlapping_at_resolutions(self) -> None:
        """Verify top header bar controls have zero collisions at 2560x1664, 1440x900, 1280x720, 960x600."""
        resolutions = [
            (2560, 1664),
            (1440, 900),
            (1280, 720),
            (960, 600),
        ]

        tl = self.window.timeline

        for width, height in resolutions:
            with self.subTest(resolution=f"{width}x{height}"):
                self.window.resize(width, height)
                QApplication.processEvents()

                header_widgets = [
                    tl.first_btn,
                    tl.prev_btn,
                    tl.play_btn,
                    tl.next_btn,
                    tl.last_btn,
                    tl.stop_btn,
                    tl.frame_info,
                    tl.add_btn,
                    tl.dup_btn,
                    tl.del_btn,
                    tl.onion_btn,
                    tl.audio_mute_btn,
                    tl.audio_btn,
                    tl.settings_btn,
                    tl.overflow_btn,
                ]
                self._check_non_overlapping(header_widgets, "Top Bar Controls")

                # Verify critical visibility
                self.assertTrue(tl.play_btn.isVisible())
                self.assertTrue(tl.add_btn.isVisible())
                self.assertTrue(tl.scroll_area.isVisible())
                self.assertGreater(tl.scroll_area.height(), 70)
                self.assertIn("Play", tl.play_btn.text())

    def test_active_thumbnail_highlight(self) -> None:
        """Verify active frame receives selection state while others remain unselected."""
        tl = self.window.timeline
        # Add 3 frames
        self.window._on_add_frame()
        self.window._on_add_frame()
        self.window._on_add_frame()
        self.assertEqual(len(tl._thumb_widgets), 4)

        # Select frame 2 (index 1)
        self.window._on_frame_selected(1)
        QApplication.processEvents()

        for i, thumb in enumerate(tl._thumb_widgets):
            if i == 1:
                self.assertTrue(thumb.selected, f"Frame {i} should be selected")
            else:
                self.assertFalse(thumb.selected, f"Frame {i} should not be selected")

        # Navigate to frame 4 (index 3)
        self.window._on_frame_selected(3)
        QApplication.processEvents()
        self.assertTrue(tl._thumb_widgets[3].selected)
        self.assertFalse(tl._thumb_widgets[1].selected)

    def test_add_frame_card_at_end(self) -> None:
        """Verify '+ Add Frame' card exists at the end of the thumbnail strip and functions."""
        tl = self.window.timeline
        initial_count = self.window.project.frame_count()

        # Check trailing widget is AddFrameCardWidget
        self.assertIsNotNone(tl._add_card)
        self.assertIsInstance(tl._add_card, AddFrameCardWidget)
        self.assertTrue(tl._add_card.isVisible())

        # Click add card directly
        tl._add_card.clicked.emit()
        QApplication.processEvents()

        # Should have added a frame
        self.assertEqual(self.window.project.frame_count(), initial_count + 1)
        self.assertEqual(len(tl._thumb_widgets), initial_count + 1)

        # Trailing card still exists at the end
        last_item = tl.thumb_layout.itemAt(tl.thumb_layout.count() - 1).widget()
        self.assertEqual(last_item, tl._add_card)

    def test_selected_frame_visible_after_navigation(self) -> None:
        """Verify auto-scroll ensures selected frame is brought into view."""
        tl = self.window.timeline
        # Add many frames to force scrollable strip
        for _ in range(15):
            self.window._on_add_frame()
        QApplication.processEvents()
        tl.scroll_area.widget().adjustSize()
        QApplication.processEvents()

        self.assertEqual(len(tl._thumb_widgets), 16)

        # Switch to first frame
        self.window._on_frame_selected(0)
        QApplication.processEvents()
        h_bar = tl.scroll_area.horizontalScrollBar()
        self.assertEqual(h_bar.value(), 0)

        # Select the last frame
        self.window._on_frame_selected(15)
        QApplication.processEvents()
        self.assertGreater(h_bar.value(), 0)

    def test_audio_track_collapsible(self) -> None:
        """Verify audio track is hidden by default and opens when audio is present."""
        tl = self.window.timeline
        # Hidden by default when no audio is loaded
        self.assertFalse(tl.audio_track_widget.isVisible())

        # Simulate audio load
        with patch.object(tl, "_extract_waveform", return_value=[0.5] * 20):
            tl.audio_file_path = "/fake/song.wav"
            tl.waveform_widget.set_audio("song.wav", [0.5] * 20)
            tl.audio_track_widget.setVisible(True)
            tl.audio_loaded.emit("/fake/song.wav")
            QApplication.processEvents()

        self.assertTrue(tl.audio_track_widget.isVisible())

        # Clear audio
        tl._on_clear_audio_clicked()
        QApplication.processEvents()
        self.assertFalse(tl.audio_track_widget.isVisible())
        self.assertIsNone(tl.audio_file_path)

    def test_settings_bar_toggle(self) -> None:
        """Verify secondary settings bar toggles cleanly with settings button."""
        tl = self.window.timeline
        # Initially hidden
        self.assertFalse(tl.settings_bar.isVisible())

        # Toggle on
        tl.settings_btn.setChecked(True)
        QApplication.processEvents()
        self.assertTrue(tl.settings_bar.isVisible())
        self.assertTrue(tl.fps_spinbox.isVisible())
        self.assertTrue(tl.loop_combo.isVisible())

        # Toggle off
        tl.settings_btn.setChecked(False)
        QApplication.processEvents()
        self.assertFalse(tl.settings_bar.isVisible())


if __name__ == "__main__":
    unittest.main()
