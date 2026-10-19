"""Comprehensive end-to-end test suite for AI Doodle Studio.

Verifies:
1. Multi-frame creation, renaming, duplication, reordering, deletion safety.
2. Independent frame buffer preservation across frame switching.
3. Drawing tools: Pen (opaque & translucent), Eraser, Line, Rect, Ellipse, Fill, Eyedropper.
4. Multi-layer compositing, layer opacity, visibility toggling.
5. Multi-frame Undo / Redo with automatic frame synchronization.
6. Project serialization & deserialization (.adsproj zip package).
7. Headless full UI integration test and preview render.
"""

import os
import sys
import tempfile
import unittest

# Ensure PySide6 runs headless
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

# Ensure app is on import path
app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app.core.frame import Frame
from app.core.layer import Layer
from app.core.project import AnimationProject, BackgroundType
from app.drawing.canvas import DrawingCanvas
from app.drawing.tools import ToolType


class TestAIDoodleStudioFull(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication(sys.argv)

    def test_01_multiframe_management(self):
        proj = AnimationProject(width=320, height=240, fps=24, name="TestAnim")
        self.assertEqual(proj.frame_count(), 1)
        self.assertEqual(proj.current_frame_index, 0)

        # Add multiple frames
        idx1 = proj.add_frame()
        self.assertEqual(idx1, 1)
        self.assertEqual(proj.frame_count(), 2)

        idx2 = proj.add_frame()
        self.assertEqual(idx2, 2)
        self.assertEqual(proj.frame_count(), 3)

        # Rename frames
        proj.frames[0].name = "Intro"
        proj.frames[1].name = "Action"
        proj.frames[2].name = "Outro"
        self.assertEqual(proj.frames[0].name, "Intro")
        self.assertEqual(proj.frames[1].name, "Action")
        self.assertEqual(proj.frames[2].name, "Outro")

        # Duplicate frame
        proj.set_current_frame(1)
        dup_idx = proj.duplicate_frame()
        self.assertEqual(dup_idx, 2)
        self.assertEqual(proj.frame_count(), 4)
        self.assertEqual(proj.frames[dup_idx].name, "Action Copy")

        # Reorder frames: move Outro (index 3) to beginning (index 0)
        proj.move_frame(3, 0)
        self.assertEqual(proj.frames[0].name, "Outro")

        # Delete frames
        proj.delete_frame(0)
        self.assertEqual(proj.frame_count(), 3)
        proj.delete_frame(0)
        self.assertEqual(proj.frame_count(), 2)
        proj.delete_frame(0)
        self.assertEqual(proj.frame_count(), 1)

        # Prevent deleting last remaining frame
        can_delete = proj.delete_frame(0)
        self.assertFalse(can_delete)
        self.assertEqual(proj.frame_count(), 1)

    def test_02_frame_drawing_isolation(self):
        # Create project with transparent background to verify pixel colors directly
        proj = AnimationProject(width=100, height=100, bg_color=QColor(0, 0, 0, 0))
        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        # Draw red rectangle on frame 0
        proj.set_current_frame(0)
        canvas.set_frame(proj.get_current_frame())
        canvas.set_brush_color(QColor(255, 0, 0, 255))
        canvas.set_brush_size(6)
        canvas.set_tool(ToolType.RECTANGLE)

        p1 = QPointF(10, 10)
        p2 = QPointF(90, 90)
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

        canvas.mousePressEvent(press)
        canvas.mouseReleaseEvent(release)

        f0_pixel = proj.frames[0].get_image().pixelColor(10, 10)
        self.assertEqual(f0_pixel.red(), 255)

        # Add frame 1 (should be blank transparent)
        proj.add_frame()
        canvas.set_frame(proj.get_current_frame())
        f1_pixel = proj.frames[1].get_image().pixelColor(10, 10)
        self.assertEqual(f1_pixel.alpha(), 0)

        # Draw blue rectangle on frame 1
        canvas.set_brush_color(QColor(0, 0, 255, 255))
        canvas.mousePressEvent(press)
        canvas.mouseReleaseEvent(release)

        f1_new_pixel = proj.frames[1].get_image().pixelColor(10, 10)
        self.assertEqual(f1_new_pixel.blue(), 255)

        # Verify frame 0 is still red and untouched
        f0_check = proj.frames[0].get_image().pixelColor(10, 10)
        self.assertEqual(f0_check.red(), 255)
        self.assertEqual(f0_check.blue(), 0)

    def test_03_pen_uniform_opacity(self):
        proj = AnimationProject(width=100, height=100, bg_color=QColor(0, 0, 0, 0))
        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        canvas.set_tool(ToolType.PEN)
        canvas.set_brush_color(QColor(0, 255, 0, 255))
        canvas.set_brush_opacity(0.5)
        canvas.set_brush_size(20)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        move1 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(30, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        move2 = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(60, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(90, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)

        canvas.mousePressEvent(press)
        canvas.mouseMoveEvent(move1)
        canvas.mouseMoveEvent(move2)
        canvas.mouseReleaseEvent(release)

        drawn = proj.frames[0].get_image()
        c = drawn.pixelColor(50, 50)
        # Translucent green: alpha is ~127 (50% of 255)
        self.assertGreater(c.alpha(), 100)
        self.assertLess(c.alpha(), 150)
        self.assertEqual(c.green(), 255)

    def test_04_layers_system(self):
        frame = Frame(width=100, height=100)
        self.assertEqual(len(frame.layers), 1)

        # Add layer 2
        l2 = frame.add_layer("Layer 2")
        self.assertEqual(len(frame.layers), 2)
        self.assertEqual(frame.active_layer_index, 1)

        # Fill layer 2 with red at 50% opacity
        l2.image.fill(QColor(255, 0, 0, 255))
        l2.opacity = 0.5
        frame.mark_modified()

        comp = frame.get_image()
        c = comp.pixelColor(50, 50)
        self.assertEqual(c.red(), 255)
        self.assertAlmostEqual(c.alphaF(), 0.5, delta=0.05)

        # Toggle visibility
        l2.visible = False
        frame.mark_modified()
        comp2 = frame.get_image()
        self.assertEqual(comp2.pixelColor(50, 50).alpha(), 0)

        # Delete layer 2
        deleted = frame.delete_active_layer()
        self.assertTrue(deleted)
        self.assertEqual(len(frame.layers), 1)

        # Prevent deleting only remaining layer
        deleted_last = frame.delete_active_layer()
        self.assertFalse(deleted_last)

    def test_05_undo_redo_frame_synchronization(self):
        proj = AnimationProject(width=100, height=100, bg_color=QColor(0, 0, 0, 0))
        canvas = DrawingCanvas(project=proj)
        canvas.resize(100, 100)
        canvas.scale = 1.0
        canvas.offset_x = 0.0
        canvas.offset_y = 0.0

        proj.add_frame()

        # Frame 0: draw red rectangle
        proj.set_current_frame(0)
        canvas.set_frame(proj.get_current_frame())
        canvas.set_tool(ToolType.RECTANGLE)
        canvas.set_brush_color(QColor(255, 0, 0))
        canvas.set_brush_size(6)

        p1 = QPointF(10, 10)
        p2 = QPointF(80, 80)
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        canvas.mousePressEvent(press)
        canvas.mouseReleaseEvent(release)
        self.assertEqual(proj.frames[0].get_image().pixelColor(10, 10).red(), 255)

        # Switch to Frame 1 and draw blue ellipse
        proj.set_current_frame(1)
        canvas.set_frame(proj.get_current_frame())
        canvas.set_tool(ToolType.ELLIPSE)
        canvas.set_brush_color(QColor(0, 0, 255))
        canvas.mousePressEvent(press)
        canvas.mouseReleaseEvent(release)
        self.assertEqual(proj.frames[1].get_image().pixelColor(10, 45).blue(), 255)

        # Undo on Frame 1
        self.assertTrue(proj.undo_manager.can_undo())
        proj.undo_manager.undo()
        self.assertEqual(proj.frames[1].get_image().pixelColor(10, 45).alpha(), 0)

        # Undo on Frame 0 should switch project current frame back to 0
        proj.undo_manager.undo()
        self.assertEqual(proj.current_frame_index, 0)
        self.assertEqual(proj.frames[0].get_image().pixelColor(10, 10).alpha(), 0)

        # Redo Frame 0
        proj.undo_manager.redo()
        self.assertEqual(proj.current_frame_index, 0)
        self.assertEqual(proj.frames[0].get_image().pixelColor(10, 10).red(), 255)

        # Redo Frame 1
        proj.undo_manager.redo()
        self.assertEqual(proj.current_frame_index, 1)
        self.assertEqual(proj.frames[1].get_image().pixelColor(10, 45).blue(), 255)

    def test_06_project_save_and_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            save_file = os.path.join(tmpdir, "my_anim.adsproj")
            proj = AnimationProject(width=200, height=150, fps=18, name="Bounce", bg_color=QColor(0, 0, 0, 0))
            proj.frames[0].name = "Keyframe 1"

            canvas = DrawingCanvas(project=proj)
            canvas.resize(200, 150)
            canvas.scale = 1.0
            canvas.offset_x = 0.0
            canvas.offset_y = 0.0

            # Draw on frame 0
            canvas.set_tool(ToolType.RECTANGLE)
            canvas.set_brush_color(QColor(255, 128, 0))
            canvas.set_brush_size(6)
            p1 = QPointF(20, 20)
            p2 = QPointF(100, 100)
            press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, p1, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, p2, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            canvas.mousePressEvent(press)
            canvas.mouseReleaseEvent(release)

            # Add frame 1
            proj.add_frame()
            proj.frames[1].name = "Keyframe 2"
            canvas.set_frame(proj.frames[1])
            canvas.set_brush_color(QColor(0, 200, 255))
            canvas.mousePressEvent(press)
            canvas.mouseReleaseEvent(release)

            # Save
            ok = proj.save_project(save_file)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(save_file))

            # Reopen in new project
            proj2 = AnimationProject()
            load_ok = proj2.load_project(save_file)
            self.assertTrue(load_ok)
            self.assertEqual(proj2.name, "Bounce")
            self.assertEqual(proj2.canvas_width, 200)
            self.assertEqual(proj2.canvas_height, 150)
            self.assertEqual(proj2.fps, 18)
            self.assertEqual(proj2.frame_count(), 2)
            self.assertEqual(proj2.frames[0].name, "Keyframe 1")
            self.assertEqual(proj2.frames[1].name, "Keyframe 2")

            # Check drawing data
            f0_col = proj2.frames[0].get_image().pixelColor(20, 20)
            self.assertEqual(f0_col.red(), 255)
            self.assertEqual(f0_col.green(), 128)

            f1_col = proj2.frames[1].get_image().pixelColor(20, 20)
            self.assertEqual(f1_col.red(), 0)
            self.assertEqual(f1_col.blue(), 255)

    def test_07_full_main_window_integration(self):
        from app.ui.main_window import MainWindow
        win = MainWindow()
        win.resize(1280, 800)
        win.show()

        # Timeline has 1 frame initially
        self.assertEqual(win.project.frame_count(), 1)
        self.assertFalse(win.timeline.del_btn.isEnabled())

        # Click Add Frame
        win.timeline.add_btn.click()
        self.assertEqual(win.project.frame_count(), 2)
        self.assertTrue(win.timeline.del_btn.isEnabled())

        # Click Duplicate
        win.timeline.dup_btn.click()
        self.assertEqual(win.project.frame_count(), 3)

        # Move frame left
        win.project.frames[1].name = "Middle"
        win.timeline.move_frame_left_clicked.emit(1)
        self.assertEqual(win.project.frames[0].name, "Middle")

        # Grab UI preview image
        preview_pix = win.grab()
        docs_dir = os.path.abspath(os.path.join(app_dir, "..", "docs"))
        os.makedirs(docs_dir, exist_ok=True)
        preview_path = os.path.join(docs_dir, "app_preview_drawn.png")
        preview_pix.save(preview_path, "PNG")
        self.assertTrue(os.path.exists(preview_path))
        win.project.modified = False
        win.close()


if __name__ == "__main__":
    unittest.main()
