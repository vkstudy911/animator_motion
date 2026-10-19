"""Test individual drawing tools in DrawingCanvas."""

import os
import sys
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication

app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from app.core.project import AnimationProject
from app.drawing.canvas import DrawingCanvas
from app.drawing.tools import ToolType


class TestDrawingTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.proj = AnimationProject(width=100, height=100, bg_color=QColor(0, 0, 0, 0))
        self.canvas = DrawingCanvas(project=self.proj)
        self.canvas.resize(100, 100)
        self.canvas.scale = 1.0
        self.canvas.offset_x = 0.0
        self.canvas.offset_y = 0.0

    def test_line_tool(self):
        self.canvas.set_tool(ToolType.LINE)
        self.canvas.set_brush_color(QColor(255, 0, 0, 255))
        self.canvas.set_brush_size(4)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(10, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(90, 10), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)
        self.canvas.mouseReleaseEvent(release)

        img = self.proj.frames[0].get_image()
        self.assertEqual(img.pixelColor(50, 10).red(), 255)

    def test_rect_tool(self):
        self.canvas.set_tool(ToolType.RECTANGLE)
        self.canvas.set_brush_color(QColor(0, 255, 0, 255))
        self.canvas.set_brush_size(4)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(80, 80), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)
        self.canvas.mouseReleaseEvent(release)

        img = self.proj.frames[0].get_image()
        self.assertEqual(img.pixelColor(20, 50).green(), 255)
        self.assertEqual(img.pixelColor(80, 50).green(), 255)

    def test_ellipse_tool(self):
        self.canvas.set_tool(ToolType.ELLIPSE)
        self.canvas.set_brush_color(QColor(0, 0, 255, 255))
        self.canvas.set_brush_size(4)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(20, 20), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(80, 80), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)
        self.canvas.mouseReleaseEvent(release)

        img = self.proj.frames[0].get_image()
        # Top of circle around (50, 20)
        self.assertEqual(img.pixelColor(50, 20).blue(), 255)

    def test_fill_tool(self):
        # Fill canvas with yellow
        self.canvas.set_tool(ToolType.FILL)
        self.canvas.set_brush_color(QColor(255, 255, 0, 255))

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(50, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)

        img = self.proj.frames[0].get_image()
        c = img.pixelColor(50, 50)
        self.assertEqual(c.red(), 255)
        self.assertEqual(c.green(), 255)
        self.assertEqual(c.blue(), 0)

    def test_eraser_tool(self):
        # First fill with red
        layer = self.proj.frames[0].get_active_layer()
        layer.image.fill(QColor(255, 0, 0, 255))
        self.proj.frames[0].mark_modified()

        self.canvas.set_tool(ToolType.ERASER)
        self.canvas.set_brush_size(30)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(50, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(50, 50), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)
        self.canvas.mouseReleaseEvent(release)

        img = self.proj.frames[0].get_image()
        # Pixel at (50, 50) was cleared by eraser
        self.assertEqual(img.pixelColor(50, 50).alpha(), 0)

    def test_eyedropper_tool(self):
        # Set pixel at (30, 30) to purple
        layer = self.proj.frames[0].get_active_layer()
        layer.image.setPixelColor(30, 30, QColor(128, 0, 128, 255))
        self.proj.frames[0].mark_modified()

        self.canvas.set_tool(ToolType.COLOR_PICKER)
        picked_colors = []
        self.canvas.color_picked.connect(picked_colors.append)

        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(30, 30), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.canvas.mousePressEvent(press)

        self.assertEqual(len(picked_colors), 1)
        self.assertEqual(picked_colors[0].red(), 128)
        self.assertEqual(picked_colors[0].blue(), 128)


if __name__ == "__main__":
    unittest.main()
