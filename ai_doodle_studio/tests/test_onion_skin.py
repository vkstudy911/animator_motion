"""Comprehensive regression tests for Onion Skin feature in AI Doodle Studio.

Validates:
1. White background project: onion skin produces a visible tinted ghost for drawings in previous frames.
2. Transparent background project: onion skin produces a visible tinted ghost.
3. Current frame drawing renders above onion ghost.
4. Preceding and succeeding frames use distinct tint colors.
5. Onion toggle and settings persist through save and load (.adsproj).
6. UI toolbar and timeline buttons stay synchronized with onion settings upon load.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from app.animation.onion_skin import OnionSkinRenderer
from app.core.frame import Frame
from app.core.project import AnimationProject, BackgroundType
from app.drawing.canvas import DrawingCanvas
from app.ui.main_window import MainWindow


class TestOnionSkinFeature(unittest.TestCase):
    """Test suite covering Onion Skin rendering order and persistence."""

    def test_white_background_onion_ghost_visibility(self) -> None:
        """With a white background and red drawing on frame 0, frame 1 renders a visible tinted ghost."""
        proj = AnimationProject(width=100, height=100, bg_color=QColor(255, 255, 255, 255))
        self.assertEqual(proj.background_type, BackgroundType.WHITE)

        # Draw red square in frame 0
        f0 = proj.frames[0]
        f0_layer = f0.get_active_layer()
        self.assertIsNotNone(f0_layer)
        p = QPainter(f0_layer.image)
        p.fillRect(40, 40, 20, 20, QColor(255, 0, 0, 255))
        p.end()
        f0.mark_modified()

        # Add blank frame 1 and select it
        proj.add_frame()
        self.assertEqual(proj.current_frame_index, 1)

        # Setup canvas and onion skin renderer
        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        renderer = OnionSkinRenderer(
            enabled=True,
            frames_before=1,
            frames_after=0,
            before_opacity=0.5,
            before_color=QColor(235, 75, 75),
        )
        canvas.set_onion_skin_renderer(renderer)
        canvas.set_frame(proj.get_current_frame())

        # Render canvas to offscreen image
        output = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)
        canvas.render(output)

        # Background area outside drawing should be pure white
        bg_col = output.pixelColor(10, 10)
        self.assertEqual((bg_col.red(), bg_col.green(), bg_col.blue()), (255, 255, 255))

        # Center area (where frame 0 has red drawing) must show tinted ghost (not pure white)
        ghost_col = output.pixelColor(50, 50)
        self.assertGreater(ghost_col.red(), 230)
        # Green and Blue must be lower than 200 due to red tinting over white
        self.assertLess(ghost_col.green(), 200)
        self.assertLess(ghost_col.blue(), 200)

    def test_transparent_background_onion_ghost(self) -> None:
        """With transparent background, onion skin ghost renders correctly."""
        proj = AnimationProject(width=100, height=100, bg_color=QColor(0, 0, 0, 0))
        self.assertEqual(proj.background_type, BackgroundType.TRANSPARENT)

        # Frame 0: draw solid green box
        f0 = proj.frames[0]
        p = QPainter(f0.get_active_layer().image)
        p.fillRect(30, 30, 40, 40, QColor(0, 255, 0, 255))
        p.end()
        f0.mark_modified()

        # Frame 1: empty
        proj.add_frame()

        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        renderer = OnionSkinRenderer(
            enabled=True,
            frames_before=1,
            before_opacity=0.5,
            before_color=QColor(235, 75, 75),
        )
        canvas.set_onion_skin_renderer(renderer)
        canvas.set_frame(proj.get_current_frame())

        output = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)
        canvas.render(output)

        ghost_col = output.pixelColor(50, 50)
        # Red component should be prominent from before_color tint
        self.assertGreater(ghost_col.red(), 100)

    def test_current_frame_drawing_above_onion_ghost(self) -> None:
        """Current frame drawing renders above onion ghost without being covered or tinted."""
        proj = AnimationProject(width=100, height=100, bg_color=QColor(255, 255, 255, 255))

        # Frame 0: draw red box at (40, 40)
        p0 = QPainter(proj.frames[0].get_active_layer().image)
        p0.fillRect(40, 40, 20, 20, QColor(255, 0, 0, 255))
        p0.end()
        proj.frames[0].mark_modified()

        # Frame 1: draw blue box at (40, 40)
        proj.add_frame()
        p1 = QPainter(proj.frames[1].get_active_layer().image)
        p1.fillRect(40, 40, 20, 20, QColor(0, 0, 255, 255))
        p1.end()
        proj.frames[1].mark_modified()

        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        renderer = OnionSkinRenderer(
            enabled=True,
            frames_before=1,
            before_opacity=0.5,
            before_color=QColor(255, 100, 100),
        )
        canvas.set_onion_skin_renderer(renderer)
        canvas.set_frame(proj.get_current_frame())

        output = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)
        canvas.render(output)

        col = output.pixelColor(50, 50)
        # Must be pure opaque blue from current frame
        self.assertEqual(col.blue(), 255)
        self.assertEqual(col.red(), 0)

    def test_previous_and_next_frames_different_tints(self) -> None:
        """Previous frames use before_color (red) and next frames use after_color (green)."""
        proj = AnimationProject(width=100, height=100, bg_color=QColor(255, 255, 255, 255))

        # Frame 0: drawing on left side (20, 50)
        p0 = QPainter(proj.frames[0].get_active_layer().image)
        p0.fillRect(15, 45, 10, 10, QColor(0, 0, 0, 255))
        p0.end()
        proj.frames[0].mark_modified()

        # Frame 1: blank active frame
        proj.add_frame()

        # Frame 2: drawing on right side (80, 50)
        proj.add_frame()
        p2 = QPainter(proj.frames[2].get_active_layer().image)
        p2.fillRect(75, 45, 10, 10, QColor(0, 0, 0, 255))
        p2.end()
        proj.frames[2].mark_modified()

        # Select frame 1 as active
        proj.set_current_frame(1)

        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        renderer = OnionSkinRenderer(
            enabled=True,
            frames_before=1,
            frames_after=1,
            before_opacity=0.5,
            after_opacity=0.5,
            before_color=QColor(255, 0, 0),
            after_color=QColor(0, 255, 0),
        )
        canvas.set_onion_skin_renderer(renderer)
        canvas.set_frame(proj.get_current_frame())

        output = QImage(100, 100, QImage.Format.Format_ARGB32_Premultiplied)
        output.fill(Qt.GlobalColor.transparent)
        canvas.render(output)

        # Left pixel (from past frame 0) must be tinted RED
        past_col = output.pixelColor(20, 50)
        self.assertEqual(past_col.red(), 255)
        self.assertLess(past_col.green(), 200)

        # Right pixel (from future frame 2) must be tinted GREEN
        future_col = output.pixelColor(80, 50)
        self.assertEqual(future_col.green(), 255)
        self.assertLess(future_col.red(), 200)

    def test_onion_settings_persistence_save_and_load(self) -> None:
        """Onion toggle, range, opacity, and tint colors persist after project save and load."""
        proj = AnimationProject(name="OnionPersistenceTest", width=100, height=100)
        proj.onion_settings.update({
            "enabled": True,
            "frames_before": 3,
            "frames_after": 2,
            "opacity": 0.65,
            "tint_before": "#FF5511",
            "tint_after": "#11EEAA",
        })
        proj.mark_modified()

        with tempfile.NamedTemporaryFile(suffix=".adsproj", delete=False) as f:
            save_path = f.name

        try:
            saved = proj.save_project(save_path)
            self.assertTrue(saved)

            # Reload into new project
            loaded_proj = AnimationProject()
            loaded = loaded_proj.load_project(save_path)
            self.assertTrue(loaded)

            self.assertTrue(loaded_proj.onion_settings["enabled"])
            self.assertEqual(loaded_proj.onion_settings["frames_before"], 3)
            self.assertEqual(loaded_proj.onion_settings["frames_after"], 2)
            self.assertAlmostEqual(loaded_proj.onion_settings["opacity"], 0.65, places=2)
            self.assertEqual(loaded_proj.onion_settings["tint_before"], "#FF5511")
            self.assertEqual(loaded_proj.onion_settings["tint_after"], "#11EEAA")
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)

    def test_main_window_onion_ui_sync_on_load(self) -> None:
        """Loading a project synchronizes the OnionSkinRenderer, toolbar action, and timeline button."""
        with tempfile.NamedTemporaryFile(suffix=".adsproj", delete=False) as f:
            save_path = f.name

        try:
            p = AnimationProject(name="SyncTest", width=100, height=100)
            p.onion_settings.update({
                "enabled": True,
                "frames_before": 4,
                "frames_after": 2,
                "opacity": 0.5,
                "tint_before": "#AA2233",
                "tint_after": "#44CC55",
            })
            p.save_project(save_path)

            window = MainWindow()
            try:
                self.assertFalse(window.onion_skin.enabled)
                self.assertFalse(window.toolbar.act_onion.isChecked())
                self.assertFalse(window.timeline.onion_btn.isChecked())

                window.project.load_project(save_path)
                window._refresh_all()

                self.assertTrue(window.onion_skin.enabled)
                self.assertEqual(window.onion_skin.frames_before, 4)
                self.assertEqual(window.onion_skin.frames_after, 2)
                self.assertAlmostEqual(window.onion_skin.before_opacity, 0.5, places=2)
                self.assertEqual(window.onion_skin.before_color.name().upper(), "#AA2233")
                self.assertEqual(window.onion_skin.after_color.name().upper(), "#44CC55")

                # UI Controls must be synchronized
                self.assertTrue(window.toolbar.act_onion.isChecked())
                self.assertTrue(window.timeline.onion_btn.isChecked())
            finally:
                window.project.modified = False
                window.close()
        finally:
            if os.path.exists(save_path):
                os.remove(save_path)


if __name__ == "__main__":
    unittest.main()
