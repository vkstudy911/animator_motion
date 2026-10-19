"""Drawing tools implementation for AI Doodle Studio.

Includes base tool interface, Pen, Eraser, Flood Fill, Color Picker,
and standard geometric shape tools with full anti-aliasing and undo integration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import QInputDialog

if TYPE_CHECKING:
    from app.drawing.canvas import DrawingCanvas


class ToolType(Enum):
    """Enumeration of available drawing and manipulation tools."""

    PEN = auto()
    ERASER = auto()
    COLOR_PICKER = auto()
    FILL = auto()
    LINE = auto()
    RECTANGLE = auto()
    ELLIPSE = auto()
    SELECT = auto()
    TEXT = auto()
    RIG = auto()


class BaseTool(ABC):
    """Abstract base class for all drawing canvas tools."""

    def __init__(self, tool_type: ToolType) -> None:
        self.tool_type = tool_type

    @abstractmethod
    def cursor(self) -> QCursor:
        """Return the appropriate QCursor for this tool."""
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        """Invoked when mouse button is pressed on the canvas."""
        pass

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        """Invoked when mouse moves over the canvas."""
        pass

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        """Invoked when mouse button is released."""
        pass

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        """Render temporary previews (e.g. shape bounds) directly in canvas view."""
        pass


class PenTool(BaseTool):
    """Freehand pen tool with smooth Catmull-Rom point interpolation and uniform opacity."""

    def __init__(self) -> None:
        super().__init__(ToolType.PEN)
        self.last_point: Optional[QPointF] = None
        self.is_drawing: bool = False
        self.stroke_path: QPainterPath = QPainterPath()
        self.is_translucent: bool = False

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.is_drawing = True
        self.last_point = pos
        self.is_translucent = (canvas.brush_opacity < 0.999) or (canvas.brush_color.alpha() < 255)
        self.stroke_path = QPainterPath()
        self.stroke_path.moveTo(pos)

        canvas.brush_engine.reset_stroke()
        canvas.brush_engine.add_point(pos, getattr(event, "pressure", lambda: 1.0)())

        if self.is_translucent:
            canvas.update()
        else:
            target = canvas.draw_target()
            if target:
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(pen)
                painter.drawPoint(pos)
                painter.end()
                if canvas.current_frame is not None:
                    canvas.current_frame._composite_dirty = True
                canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if not self.is_drawing or self.last_point is None:
            return

        pressure = getattr(event, "pressure", lambda: 1.0)()
        sub_points = canvas.brush_engine.add_point(pos, pressure)

        for pt, _ in sub_points:
            self.stroke_path.lineTo(pt)

        if self.is_translucent:
            canvas.update()
        else:
            target = canvas.draw_target()
            if target is not None:
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(pen)

                prev = self.last_point
                for pt, _ in sub_points:
                    painter.drawLine(prev, pt)
                    prev = pt

                painter.end()
                self.last_point = pos
                if canvas.current_frame is not None:
                    canvas.current_frame._composite_dirty = True
                canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            if self.last_point is not None and pos != self.last_point:
                pressure = getattr(event, "pressure", lambda: 1.0)()
                sub_points = canvas.brush_engine.add_point(pos, pressure)
                for pt, _ in sub_points:
                    self.stroke_path.lineTo(pt)
            self.commit(canvas)

    def commit(self, canvas: DrawingCanvas) -> None:
        if not self.is_drawing:
            return
        if self.is_translucent:
            target = canvas.draw_target()
            if target is not None and not self.stroke_path.isEmpty():
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(pen)
                painter.drawPath(self.stroke_path)
                painter.end()
                if canvas.current_frame:
                    canvas.current_frame.mark_modified()

        self.is_drawing = False
        self.last_point = None
        self.stroke_path = QPainterPath()
        canvas.brush_engine.reset_stroke()
        canvas.finish_stroke()
        canvas.update()

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        if self.is_drawing and self.is_translucent and not self.stroke_path.isEmpty():
            painter.save()
            draw_x, draw_y = canvas.get_canvas_origin()
            painter.translate(draw_x, draw_y)
            painter.scale(canvas.scale, canvas.scale)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(
                canvas.brush_engine.get_effective_color(),
                canvas.brush_size,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            painter.drawPath(self.stroke_path)
            painter.restore()


class EraserTool(BaseTool):
    """Eraser tool utilizing CompositionMode_Clear to remove pixels completely."""

    def __init__(self) -> None:
        super().__init__(ToolType.ERASER)
        self.last_point: Optional[QPointF] = None
        self.is_erasing: bool = False

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.is_erasing = True
        self.last_point = pos
        canvas.brush_engine.reset_stroke()
        canvas.brush_engine.add_point(pos, 1.0)

        target = canvas.draw_target()
        if target:
            painter = QPainter(target)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)

            pen = QPen(
                Qt.GlobalColor.transparent,
                canvas.brush_size,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(pen)
            painter.drawPoint(pos)
            painter.end()
            if canvas.current_frame is not None:
                canvas.current_frame._composite_dirty = True
            canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if not self.is_erasing or self.last_point is None:
            return

        target = canvas.draw_target()
        if target is None:
            return

        sub_points = canvas.brush_engine.add_point(pos, 1.0)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)

        pen = QPen(
            Qt.GlobalColor.transparent,
            canvas.brush_size,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(pen)

        prev = self.last_point
        for pt, _ in sub_points:
            painter.drawLine(prev, pt)
            prev = pt

        painter.end()
        self.last_point = pos
        if canvas.current_frame is not None:
            canvas.current_frame._composite_dirty = True
        canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_erasing:
            self.is_erasing = False
            self.last_point = None
            canvas.brush_engine.reset_stroke()
            canvas.finish_stroke()


class ColorPickerTool(BaseTool):
    """Samples color from the canvas at clicked pixel."""

    def __init__(self) -> None:
        super().__init__(ToolType.COLOR_PICKER)

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.PointingHandCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        frame = canvas.current_frame
        if not frame:
            return

        x = int(pos.x())
        y = int(pos.y())
        img = frame.get_image()

        if 0 <= x < img.width() and 0 <= y < img.height():
            sampled_color = img.pixelColor(x, y)
            if sampled_color.alpha() > 0:
                canvas.set_brush_color(sampled_color)
                canvas.color_picked.emit(sampled_color)


class FillTool(BaseTool):
    """Scanline flood fill algorithm on QImage pixel buffer."""

    def __init__(self, tolerance: int = 16) -> None:
        super().__init__(ToolType.FILL)
        self.tolerance = tolerance

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        img = canvas.draw_target()
        if img is None:
            return

        x = int(pos.x())
        y = int(pos.y())
        w = img.width()
        h = img.height()

        if not (0 <= x < w and 0 <= y < h):
            return

        target_rgba = img.pixel(x, y)
        fill_color = canvas.brush_engine.get_effective_color()
        replacement_rgba = fill_color.rgba()

        if target_rgba == replacement_rgba:
            return

        # Snapshot for undo
        canvas.begin_stroke()

        # Scanline flood fill queue
        self._scanline_fill(img, x, y, target_rgba, replacement_rgba, fill_color)

        if canvas.current_frame:
            canvas.current_frame.mark_modified()
        canvas.update()
        canvas.finish_stroke()

    def _colors_match(self, c1: int, c2: int) -> bool:
        """Check color match within tolerance."""
        if c1 == c2:
            return True
        a1 = (c1 >> 24) & 0xFF
        r1 = (c1 >> 16) & 0xFF
        g1 = (c1 >> 8) & 0xFF
        b1 = c1 & 0xFF

        a2 = (c2 >> 24) & 0xFF
        r2 = (c2 >> 16) & 0xFF
        g2 = (c2 >> 8) & 0xFF
        b2 = c2 & 0xFF

        diff = abs(a1 - a2) + abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
        return diff <= (self.tolerance * 4)

    def _scanline_fill(
        self,
        img: Any,
        start_x: int,
        start_y: int,
        target_color: int,
        replace_color: int,
        fill_qcolor: QColor,
    ) -> None:
        """Scanline queue algorithm for fast continuous region filling."""
        w = img.width()
        h = img.height()

        visited = set()
        queue = deque([(start_x, start_y)])

        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) in visited:
                continue

            if not (0 <= cy < h and 0 <= cx < w):
                continue

            current_val = img.pixel(cx, cy)
            if not self._colors_match(current_val, target_color) or current_val == replace_color:
                continue

            # Scan left
            lx = cx
            while lx > 0 and self._colors_match(img.pixel(lx - 1, cy), target_color) and img.pixel(lx - 1, cy) != replace_color:
                lx -= 1

            # Scan right
            rx = cx
            while rx < w - 1 and self._colors_match(img.pixel(rx + 1, cy), target_color) and img.pixel(rx + 1, cy) != replace_color:
                rx += 1

            # Fill span from lx to rx
            for x_span in range(lx, rx + 1):
                img.setPixelColor(x_span, cy, fill_qcolor)
                visited.add((x_span, cy))

            # Scan adjacent lines (above and below)
            for ny in (cy - 1, cy + 1):
                if 0 <= ny < h:
                    x = lx
                    while x <= rx:
                        if self._colors_match(img.pixel(x, ny), target_color) and img.pixel(x, ny) != replace_color and (x, ny) not in visited:
                            queue.append((x, ny))
                            # Skip until edge of matching run
                            while x <= rx and self._colors_match(img.pixel(x, ny), target_color):
                                x += 1
                        x += 1


class LineTool(BaseTool):
    """Straight line drawing tool with interactive visual preview."""

    def __init__(self) -> None:
        super().__init__(ToolType.LINE)
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_active: bool = False

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = pos
            self.current_pos = pos
            self.is_active = True
            canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if self.is_active:
            self.current_pos = pos
            canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_active:
            self.current_pos = pos
            target = canvas.draw_target()
            if target is not None and self.start_pos is not None:
                canvas.begin_stroke()
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
                painter.setPen(pen)
                painter.drawLine(self.start_pos, self.current_pos)
                painter.end()
                if canvas.current_frame:
                    canvas.current_frame.mark_modified()
                canvas.finish_stroke()

            self.is_active = False
            self.start_pos = None
            self.current_pos = None
            canvas.update()

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        if self.is_active and self.start_pos is not None and self.current_pos is not None:
            painter.save()
            pen = QPen(
                canvas.brush_engine.get_effective_color(),
                canvas.brush_size * canvas.scale,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
            painter.setPen(pen)
            p1 = canvas.image_to_canvas(self.start_pos)
            p2 = canvas.image_to_canvas(self.current_pos)
            painter.drawLine(p1, p2)
            painter.restore()


class RectangleTool(BaseTool):
    """Rectangle shape tool with interactive visual preview."""

    def __init__(self) -> None:
        super().__init__(ToolType.RECTANGLE)
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_active: bool = False

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = pos
            self.current_pos = pos
            self.is_active = True
            canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if self.is_active:
            self.current_pos = pos
            canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_active:
            self.current_pos = pos
            target = canvas.draw_target()
            if target is not None and self.start_pos is not None:
                canvas.begin_stroke()
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.SquareCap,
                    Qt.PenJoinStyle.MiterJoin,
                )
                painter.setPen(pen)
                rect = QRectF(self.start_pos, self.current_pos).normalized()
                painter.drawRect(rect)
                painter.end()
                if canvas.current_frame:
                    canvas.current_frame.mark_modified()
                canvas.finish_stroke()

            self.is_active = False
            self.start_pos = None
            self.current_pos = None
            canvas.update()

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        if self.is_active and self.start_pos is not None and self.current_pos is not None:
            painter.save()
            pen = QPen(
                canvas.brush_engine.get_effective_color(),
                canvas.brush_size * canvas.scale,
                Qt.PenStyle.DashLine,
            )
            painter.setPen(pen)
            p1 = canvas.image_to_canvas(self.start_pos)
            p2 = canvas.image_to_canvas(self.current_pos)
            rect = QRectF(p1, p2).normalized()
            painter.drawRect(rect)
            painter.restore()


class EllipseTool(BaseTool):
    """Ellipse / circle tool with interactive visual preview."""

    def __init__(self) -> None:
        super().__init__(ToolType.ELLIPSE)
        self.start_pos: Optional[QPointF] = None
        self.current_pos: Optional[QPointF] = None
        self.is_active: bool = False

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = pos
            self.current_pos = pos
            self.is_active = True
            canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if self.is_active:
            self.current_pos = pos
            canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_active:
            self.current_pos = pos
            target = canvas.draw_target()
            if target is not None and self.start_pos is not None:
                canvas.begin_stroke()
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pen = QPen(
                    canvas.brush_engine.get_effective_color(),
                    canvas.brush_size,
                    Qt.PenStyle.SolidLine,
                )
                painter.setPen(pen)
                rect = QRectF(self.start_pos, self.current_pos).normalized()
                painter.drawEllipse(rect)
                painter.end()
                if canvas.current_frame:
                    canvas.current_frame.mark_modified()
                canvas.finish_stroke()

            self.is_active = False
            self.start_pos = None
            self.current_pos = None
            canvas.update()

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        if self.is_active and self.start_pos is not None and self.current_pos is not None:
            painter.save()
            pen = QPen(
                canvas.brush_engine.get_effective_color(),
                canvas.brush_size * canvas.scale,
                Qt.PenStyle.DashLine,
            )
            painter.setPen(pen)
            p1 = canvas.image_to_canvas(self.start_pos)
            p2 = canvas.image_to_canvas(self.current_pos)
            rect = QRectF(p1, p2).normalized()
            painter.drawEllipse(rect)
            painter.restore()


class LassoTool(BaseTool):
    """Freeform selection lasso tool with drag-move, transform preview, commit, and undo."""

    def __init__(self) -> None:
        super().__init__(ToolType.SELECT)
        self.path: Optional[QPainterPath] = None
        self.is_selecting: bool = False
        self.floating_image: Optional[QImage] = None
        self.selection_rect: Optional[QRectF] = None
        self.is_dragging: bool = False
        self.drag_start_pos: Optional[QPointF] = None
        self.has_active_selection: bool = False

    def is_active(self) -> bool:
        """Return whether there is a floating active selection."""
        return self.has_active_selection

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.CrossCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Check if clicking inside current floating selection
        if self.floating_image is not None and self.selection_rect is not None:
            if self.selection_rect.contains(pos):
                self.is_dragging = True
                self.drag_start_pos = pos
                return
            else:
                # Click outside commits existing selection
                self.commit(canvas)

        # Start new lasso selection
        self.is_selecting = True
        self.path = QPainterPath()
        self.path.moveTo(pos)
        canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if self.is_dragging and self.selection_rect is not None and self.drag_start_pos is not None:
            delta = pos - self.drag_start_pos
            self.drag_start_pos = pos
            self.selection_rect.translate(delta.x(), delta.y())
            canvas.update()
        elif self.is_selecting and self.path is not None:
            self.path.lineTo(pos)
            canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.is_dragging:
            self.is_dragging = False
            self.drag_start_pos = None
            canvas.update()
        elif self.is_selecting and self.path is not None:
            self.path.closeSubpath()
            self.is_selecting = False
            bounds = self.path.boundingRect()
            if bounds.width() >= 3 and bounds.height() >= 3:
                self._extract_selection(canvas)
            else:
                self.path = None
                self.floating_image = None
                self.selection_rect = None
            canvas.update()

    def _extract_selection(self, canvas: DrawingCanvas) -> None:
        target = canvas.draw_target()
        if target is None or self.path is None:
            self.path = None
            return

        canvas.begin_stroke()
        bounds = self.path.boundingRect()
        self.selection_rect = QRectF(bounds)

        w = max(1, int(bounds.width() + 1))
        h = max(1, int(bounds.height() + 1))
        self.floating_image = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        self.floating_image.fill(Qt.GlobalColor.transparent)

        # Clip and copy pixels from target into floating_image
        p = QPainter(self.floating_image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        local_path = QPainterPath(self.path)
        local_path.translate(-bounds.x(), -bounds.y())
        p.setClipPath(local_path)
        p.drawImage(QPointF(-bounds.x(), -bounds.y()), target)
        p.end()

        # Clear selected region from target
        p_clear = QPainter(target)
        p_clear.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        p_clear.fillPath(self.path, Qt.GlobalColor.transparent)
        p_clear.end()

        if canvas.current_frame:
            canvas.current_frame._composite_dirty = True
        self.has_active_selection = True
        canvas.update()

    def commit(self, canvas: DrawingCanvas) -> None:
        """Stamp floating selection onto layer and record undo command."""
        if self.floating_image is not None and self.selection_rect is not None:
            target = canvas.draw_target()
            if target is not None:
                p = QPainter(target)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                p.drawImage(self.selection_rect.topLeft(), self.floating_image)
                p.end()
                if canvas.current_frame:
                    canvas.current_frame.mark_modified()
                    canvas.current_frame._composite_dirty = True
                canvas.finish_stroke()

        self.floating_image = None
        self.path = None
        self.selection_rect = None
        self.is_dragging = False
        self.is_selecting = False
        self.has_active_selection = False
        canvas.update()

    def cancel(self, canvas: DrawingCanvas) -> None:
        """Cancel selection and restore original pixels."""
        if self.floating_image is not None:
            canvas.cancel_stroke()
        self.floating_image = None
        self.path = None
        self.selection_rect = None
        self.is_dragging = False
        self.is_selecting = False
        self.has_active_selection = False
        canvas.update()

    def on_key(self, event: Any, canvas: DrawingCanvas) -> bool:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.floating_image is not None or self.path is not None:
                self.commit(canvas)
                return True
        elif event.key() == Qt.Key.Key_Escape:
            if self.floating_image is not None or self.path is not None:
                self.cancel(canvas)
                return True
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if self.floating_image is not None:
                self.floating_image = None
                self.path = None
                self.selection_rect = None
                self.has_active_selection = False
                canvas.finish_stroke()
                canvas.update()
                return True
        return False

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        if self.is_selecting and self.path is not None and not self.path.isEmpty():
            painter.save()
            pen = QPen(QColor(59, 130, 246), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(59, 130, 246, 30))

            transform = QTransform()
            draw_x, draw_y = canvas.get_canvas_origin()
            transform.translate(draw_x, draw_y)
            transform.scale(canvas.scale, canvas.scale)
            canvas_path = transform.map(self.path)

            painter.drawPath(canvas_path)
            painter.restore()

        elif self.floating_image is not None and self.selection_rect is not None:
            painter.save()
            draw_x, draw_y = canvas.get_canvas_origin()
            dest_rect = QRectF(
                self.selection_rect.x() * canvas.scale + draw_x,
                self.selection_rect.y() * canvas.scale + draw_y,
                self.selection_rect.width() * canvas.scale,
                self.selection_rect.height() * canvas.scale,
            )
            # Render floating image
            painter.drawImage(dest_rect, self.floating_image)

            # Render dashed bounding box
            pen = QPen(QColor(59, 130, 246), 1.5, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(dest_rect)

            # Render corner grab handles
            painter.setPen(QPen(QColor(255, 255, 255), 1.0))
            painter.setBrush(QColor(59, 130, 246))
            corners = [
                dest_rect.topLeft(),
                dest_rect.topRight(),
                dest_rect.bottomLeft(),
                dest_rect.bottomRight(),
            ]
            for pt in corners:
                painter.drawRect(QRectF(pt.x() - 3, pt.y() - 3, 6, 6))
            painter.restore()


class TextTool(BaseTool):
    """Text placement tool using canvas dialog."""

    def __init__(self) -> None:
        super().__init__(ToolType.TEXT)

    def cursor(self) -> QCursor:
        return QCursor(Qt.CursorShape.IBeamCursor)

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        text, ok = QInputDialog.getText(canvas, "Insert Text", "Enter text to stamp on canvas:")
        if ok and text:
            target = canvas.draw_target()
            if target is not None:
                canvas.begin_stroke()
                painter = QPainter(target)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setPen(canvas.brush_engine.get_effective_color())

                font = QFont("Helvetica", int(canvas.brush_size * 2))
                painter.setFont(font)
                painter.drawText(pos, text)
                painter.end()

                if canvas.current_frame:
                    canvas.current_frame.mark_modified()
                    canvas.current_frame._composite_dirty = True
                canvas.finish_stroke()
                canvas.update()


class RigTool(BaseTool):
    """Interactive 2D Skeletal Rigging and Kinematics Tool.

    Supports selecting and dragging joints, Inverse Kinematics (IK) limb manipulation,
    Forward Kinematics (FK) rotation/translation, joint addition, and bone visualization.
    """

    def __init__(self) -> None:
        super().__init__(ToolType.RIG)
        self.selected_joint_id: Optional[str] = None
        self.selected_bone_id: Optional[str] = None
        self.hovered_joint_id: Optional[str] = None
        self.is_dragging_joint: bool = False
        self.ik_mode_enabled: bool = True
        self.ik_bend_direction: int = 1
        self.drag_start_pos: Optional[QPointF] = None
        self.before_edit_skeleton: Optional[Any] = None

    def cursor(self) -> QCursor:
        if self.hovered_joint_id or self.is_dragging_joint:
            return QCursor(Qt.CursorShape.PointingHandCursor)
        return QCursor(Qt.CursorShape.CrossCursor)

    def hit_test_joint(self, skeleton: Any, pos: QPointF, threshold: float = 14.0) -> Optional[str]:
        """Return the ID of the closest joint within threshold pixels of pos."""
        if not skeleton or not skeleton.joints:
            return None
        closest_id = None
        closest_dist = float("inf")
        for jid, joint in skeleton.joints.items():
            dist = (pos.x() - joint.x) ** 2 + (pos.y() - joint.y) ** 2
            if dist < (threshold ** 2) and dist < closest_dist:
                closest_dist = dist
                closest_id = jid
        return closest_id

    def on_press(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        project = canvas.project
        if not project:
            return

        # Ensure skeleton exists
        from app.models.skeleton import Skeleton
        if not project.skeleton:
            project.skeleton = Skeleton(name="NewRig")

        skeleton = project.skeleton
        hit_jid = self.hit_test_joint(skeleton, pos)

        # Ctrl+Click: Add new joint
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            from app.core.history import RigEditCommand
            before_skel = skeleton.clone()
            parent_id = self.selected_joint_id if self.selected_joint_id in skeleton.joints else None
            new_joint = skeleton.add_joint(
                name=f"Joint {len(skeleton.joints) + 1}",
                x=pos.x(),
                y=pos.y(),
                parent_id=parent_id,
            )
            self.selected_joint_id = new_joint.id
            if project.undo_manager:
                project.undo_manager.push(
                    RigEditCommand(project, before_skel, skeleton, canvas.update, "Add Joint")
                )
            project.modified = True
            if hasattr(project, "skeleton_changed"):
                project.skeleton_changed.emit()
            canvas.update()
            return

        if hit_jid:
            self.selected_joint_id = hit_jid
            self.selected_bone_id = None
            self.is_dragging_joint = True
            self.drag_start_pos = pos
            self.before_edit_skeleton = skeleton.clone()
            canvas.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        else:
            self.selected_joint_id = None
            self.is_dragging_joint = False

        if hasattr(project, "skeleton_changed"):
            project.skeleton_changed.emit()
        canvas.update()

    def on_move(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        project = canvas.project
        if not project or not project.skeleton:
            return

        skeleton = project.skeleton

        if self.is_dragging_joint and self.selected_joint_id:
            curr_joint = skeleton.joints.get(self.selected_joint_id)
            if not curr_joint:
                return

            # Check for Inverse Kinematics (IK)
            use_ik = self.ik_mode_enabled or curr_joint.is_ik_end_effector
            if use_ik and curr_joint.parent_id:
                parent = skeleton.joints.get(curr_joint.parent_id)
                if parent and parent.parent_id:
                    # 2-bone chain: root (grandparent) -> mid (parent) -> end (curr_joint)
                    root = skeleton.joints.get(parent.parent_id)
                    if root:
                        import math
                        from app.animation.ik_solver import solve_two_bone_ik
                        l1 = parent.rest_length or math.hypot(parent.x - root.x, parent.y - root.y)
                        l2 = curr_joint.rest_length or math.hypot(curr_joint.x - parent.x, curr_joint.y - parent.y)
                        bend = curr_joint.ik_bend_direction * self.ik_bend_direction

                        mid_pos, end_pos = solve_two_bone_ik(
                            root_position=(root.x, root.y),
                            target_position=(pos.x(), pos.y()),
                            upper_length=l1,
                            lower_length=l2,
                            bend_direction=bend,
                        )
                        parent.x, parent.y = mid_pos
                        curr_joint.x, curr_joint.y = end_pos
                        skeleton.rebuild_bones()
                    else:
                        skeleton.set_joint_position(curr_joint.id, pos.x(), pos.y())
                else:
                    skeleton.set_joint_position(curr_joint.id, pos.x(), pos.y())
            else:
                skeleton.set_joint_position(curr_joint.id, pos.x(), pos.y())

            if hasattr(project, "skeleton_changed"):
                project.skeleton_changed.emit()
            canvas.update()
        else:
            self.hovered_joint_id = self.hit_test_joint(skeleton, pos)
            canvas.setCursor(self.cursor())
            canvas.update()

    def on_release(self, event: Any, canvas: DrawingCanvas, pos: QPointF) -> None:
        project = canvas.project
        if self.is_dragging_joint:
            self.is_dragging_joint = False
            canvas.setCursor(self.cursor())
            if self.before_edit_skeleton and project and project.skeleton and project.undo_manager:
                from app.core.history import RigEditCommand
                cmd = RigEditCommand(
                    project=project,
                    before_skeleton=self.before_edit_skeleton,
                    after_skeleton=project.skeleton,
                    on_update=canvas.update,
                    description="Transform Joint",
                )
                project.undo_manager.push(cmd)
                project.modified = True
            self.before_edit_skeleton = None
            if hasattr(project, "skeleton_changed"):
                project.skeleton_changed.emit()
            canvas.update()

    def draw_overlay(self, painter: QPainter, canvas: DrawingCanvas) -> None:
        """Render bones, joints, selection halos, and name labels on canvas."""
        project = canvas.project
        if not project or not project.skeleton or not getattr(project, "skeleton_visible", True):
            return

        skeleton = project.skeleton
        if not skeleton.joints:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 1. Draw Bones
        for bone in skeleton.bones:
            pj = skeleton.joints.get(bone.parent_joint_id)
            cj = skeleton.joints.get(bone.child_joint_id)
            if not pj or not cj:
                continue

            p1 = canvas.image_to_canvas(QPointF(pj.x, pj.y))
            p2 = canvas.image_to_canvas(QPointF(cj.x, cj.y))

            # Bone shaft line
            pen = QPen(QColor(208, 188, 255, 180), 2.5)  # Neon violet
            painter.setPen(pen)
            painter.drawLine(p1, p2)

            # Tapered bone polygon
            import math
            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.hypot(dx, dy)
            if length > 12.0:
                nx = -dy / length * 4.5
                ny = dx / length * 4.5
                bone_poly = QPainterPath()
                bone_poly.moveTo(p1.x(), p1.y())
                bone_poly.lineTo(p1.x() + dx * 0.3 + nx, p1.y() + dy * 0.3 + ny)
                bone_poly.lineTo(p2.x(), p2.y())
                bone_poly.lineTo(p1.x() + dx * 0.3 - nx, p1.y() + dy * 0.3 - ny)
                bone_poly.closeSubpath()
                painter.setBrush(QColor(208, 188, 255, 45))
                painter.setPen(QPen(QColor(208, 188, 255, 120), 1.0))
                painter.drawPath(bone_poly)

        # 2. Draw Joints
        font = QFont("Helvetica", 9)
        painter.setFont(font)

        for jid, joint in skeleton.joints.items():
            pt = canvas.image_to_canvas(QPointF(joint.x, joint.y))
            is_selected = (jid == self.selected_joint_id)
            is_hovered = (jid == self.hovered_joint_id)

            radius = 6.0
            if joint.is_ik_end_effector:
                radius = 8.0
            if is_hovered:
                radius += 2.0

            # Selection halo
            if is_selected:
                painter.setPen(QPen(QColor(255, 176, 205, 220), 2.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(pt, radius + 5.0, radius + 5.0)

            # Joint fill color
            if joint.is_ik_end_effector:
                fill_color = QColor(255, 176, 205)  # Vivid magenta for IK handles
                ring_color = QColor(255, 255, 255)
            elif not joint.parent_id:
                fill_color = QColor(76, 215, 246)   # Cyan for root joints
                ring_color = QColor(208, 188, 255)
            else:
                fill_color = QColor(208, 188, 255)  # Neon violet for standard joints
                ring_color = QColor(24, 27, 37)

            painter.setPen(QPen(ring_color, 1.5))
            painter.setBrush(fill_color)
            painter.drawEllipse(pt, radius, radius)

            # Joint label pill
            label_text = joint.name
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(label_text)
            th = fm.height()
            label_rect = QRectF(pt.x() + radius + 4, pt.y() - th / 2, tw + 8, th + 2)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(16, 19, 29, 210))
            painter.drawRoundedRect(label_rect, 4.0, 4.0)

            painter.setPen(QColor(240, 240, 245))
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label_text)

        painter.restore()



