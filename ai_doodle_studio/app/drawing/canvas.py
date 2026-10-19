"""DrawingCanvas widget for AI Doodle Studio.

Core interactive widget using QPainter for anti-aliased drawing, pan/zoom,
checkerboard transparency rendering, onion skinning, and undo integration.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, Optional, Tuple

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from app.core.frame import Frame
from app.core.history import DrawCommand, UndoManager
from app.drawing.brush_engine import BrushEngine
from app.drawing.tools import (
    BaseTool,
    ColorPickerTool,
    EllipseTool,
    EraserTool,
    FillTool,
    LassoTool,
    LineTool,
    PenTool,
    RectangleTool,
    RigTool,
    TextTool,
    ToolType,
)
from app.rendering.vector_renderer import VectorSkinRenderer

if TYPE_CHECKING:
    from app.animation.onion_skin import OnionSkinRenderer
    from app.core.project import AnimationProject


class DrawingCanvas(QWidget):
    """Central drawing canvas widget rendering frame content via QPainter."""

    canvas_modified = Signal()
    zoom_changed = Signal(float)
    color_picked = Signal(QColor)
    pointer_moved = Signal(QPoint)
    space_tapped = Signal()

    def __init__(
        self,
        project: Optional[AnimationProject] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.project: Optional[AnimationProject] = project
        self.current_frame: Optional[Frame] = None
        self.onion_skin_renderer: Optional[OnionSkinRenderer] = None

        # Transform attributes
        self.scale: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.min_scale: float = 0.1
        self.max_scale: float = 32.0

        # Interaction flags
        self.is_panning: bool = False
        self.pan_start_pos: QPointF = QPointF()
        self.space_pressed: bool = False
        self.show_grid: bool = False

        # Brush & Drawing setup
        self.brush_engine = BrushEngine(size=8.0, color=QColor(230, 230, 230), opacity=1.0)
        self._before_image: Optional[QImage] = None

        # Tool instances mapping
        self.tools: Dict[ToolType, BaseTool] = {
            ToolType.PEN: PenTool(),
            ToolType.ERASER: EraserTool(),
            ToolType.COLOR_PICKER: ColorPickerTool(),
            ToolType.FILL: FillTool(),
            ToolType.LINE: LineTool(),
            ToolType.RECTANGLE: RectangleTool(),
            ToolType.ELLIPSE: EllipseTool(),
            ToolType.SELECT: LassoTool(),
            ToolType.TEXT: TextTool(),
            ToolType.RIG: RigTool(),
        }
        self.active_tool: BaseTool = self.tools[ToolType.PEN]
        self.vector_renderer = VectorSkinRenderer()
        self.playback_locked: bool = False
        self._did_pan: bool = False

        # Enable mouse tracking and keyboard focus
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        # Pre-render checkerboard tile pixmap for transparency rendering
        self._checker_tile = self._create_checker_tile(16)

        if self.project:
            self.set_frame(self.project.get_current_frame())

    # ---------------- Properties & Configuration ----------------

    @property
    def brush_size(self) -> float:
        return self.brush_engine.size

    @property
    def brush_color(self) -> QColor:
        return self.brush_engine.color

    @property
    def brush_opacity(self) -> float:
        return self.brush_engine.opacity

    def set_frame(self, frame: Optional[Frame]) -> None:
        """Set active frame for canvas display and editing."""
        self.current_frame = frame
        self.update()

    def set_onion_skin_renderer(self, renderer: OnionSkinRenderer) -> None:
        """Attach onion skin renderer."""
        self.onion_skin_renderer = renderer

    def set_tool(self, tool_type: ToolType) -> None:
        """Switch current drawing tool."""
        if tool_type in self.tools:
            previous = self.active_tool
            if previous is not self.tools[tool_type] and hasattr(previous, "commit"):
                previous.commit(self)
            self.active_tool = self.tools[tool_type]
            self.setCursor(self.active_tool.cursor())
            self.update()

    def set_playback_locked(self, locked: bool) -> None:
        """Lock or unlock canvas editing during animation playback."""
        self.playback_locked = locked
        if locked:
            if hasattr(self.active_tool, "commit"):
                self.active_tool.commit(self)
            self.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
        else:
            self.setCursor(self.active_tool.cursor())
        self.update()

    def draw_target(self) -> Optional[QImage]:
        """Return the active layer image if it can be edited."""
        if self.playback_locked or self.current_frame is None:
            return None
        layer = self.current_frame.get_active_layer()
        if layer is None or layer.locked or not layer.visible:
            return None
        return layer.image

    def active_layer_locked(self) -> bool:
        if self.current_frame is None:
            return True
        layer = self.current_frame.get_active_layer()
        return layer is None or layer.locked or not layer.visible

    def set_brush_size(self, size: float) -> None:
        """Update brush stroke diameter (clamped between 1 and 200)."""
        self.brush_engine.size = max(1.0, min(200.0, float(size)))
        self.update()

    def set_brush_color(self, color: QColor) -> None:
        """Update active brush color."""
        self.brush_engine.color = QColor(color)
        self.update()

    def set_brush_opacity(self, opacity: float) -> None:
        """Update brush opacity (clamped between 0.0 and 1.0)."""
        self.brush_engine.opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    def toggle_grid(self) -> bool:
        """Toggle grid display on canvas."""
        self.show_grid = not self.show_grid
        self.update()
        return self.show_grid

    # ---------------- Undo / Redo Stroke Tracking ----------------

    def begin_stroke(self) -> None:
        """Capture active-layer snapshot before a destructive action begins."""
        target = self.draw_target()
        if target is not None and self._before_image is None:
            self._before_image = target.copy()

    def cancel_stroke(self) -> None:
        if self.current_frame is not None and self._before_image is not None:
            self.current_frame.set_layer_image(
                self.current_frame.active_layer_index, self._before_image
            )
            self._before_image = None
            self.update()

    def finish_stroke(self) -> None:
        """Push recorded stroke to undo history and notify project."""
        target = self.current_frame.get_active_layer_image() if self.current_frame else None
        if self.current_frame is not None and self._before_image is not None and target is not None:
            after_image = target.copy()
            if self.project and self.project.undo_manager:
                cmd = DrawCommand(
                    frame=self.current_frame,
                    before_image=self._before_image,
                    after_image=after_image,
                    on_update=self.update,
                    layer_index=self.current_frame.active_layer_index,
                    project=self.project,
                )
                self.project.undo_manager.push(cmd)

            self._before_image = None
            self.current_frame.mark_modified()
            if self.project:
                self.project.mark_modified()
            self.canvas_modified.emit()
            self.update()

    # ---------------- Coordinate Transformations ----------------

    def get_canvas_origin(self) -> Tuple[float, float]:
        """Return (draw_x, draw_y) for top-left of the canvas in widget coordinates."""
        fw = self.current_frame.width if self.current_frame else 1280
        fh = self.current_frame.height if self.current_frame else 720
        draw_x = (self.width() - fw * self.scale) / 2.0 + self.offset_x
        draw_y = (self.height() - fh * self.scale) / 2.0 + self.offset_y
        return draw_x, draw_y

    def canvas_to_image(self, widget_pos: QPointF) -> QPointF:
        """Convert widget coordinate to image pixel coordinate."""
        draw_x, draw_y = self.get_canvas_origin()
        ix = (widget_pos.x() - draw_x) / self.scale
        iy = (widget_pos.y() - draw_y) / self.scale
        return QPointF(ix, iy)

    def image_to_canvas(self, image_pos: QPointF) -> QPointF:
        """Convert image pixel coordinate to widget coordinate."""
        draw_x, draw_y = self.get_canvas_origin()
        wx = image_pos.x() * self.scale + draw_x
        wy = image_pos.y() * self.scale + draw_y
        return QPointF(wx, wy)

    # ---------------- Zoom & Pan Controls ----------------

    def zoom_in(self) -> None:
        self._set_zoom(self.scale * 1.25)

    def zoom_out(self) -> None:
        self._set_zoom(self.scale / 1.25)

    def zoom_reset(self) -> None:
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom_changed.emit(self.scale)
        self.update()

    def zoom_fit(self) -> None:
        """Fit frame canvas inside current viewport with padding."""
        if not self.current_frame:
            return
        fw = self.current_frame.width
        fh = self.current_frame.height
        margin = 40.0
        avail_w = max(10.0, self.width() - margin)
        avail_h = max(10.0, self.height() - margin)
        scale_x = avail_w / fw
        scale_y = avail_h / fh
        new_scale = min(scale_x, scale_y)
        self.scale = max(self.min_scale, min(self.max_scale, new_scale))
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.zoom_changed.emit(self.scale)
        self.update()

    def _set_zoom(self, new_scale: float, anchor_pos: Optional[QPointF] = None) -> None:
        """Apply new zoom scale with optional cursor anchor."""
        clamped = max(self.min_scale, min(self.max_scale, new_scale))
        if math.isclose(clamped, self.scale, rel_tol=1e-4):
            return

        if anchor_pos is not None:
            # Zoom anchored around mouse cursor
            old_scale = self.scale
            draw_x, draw_y = self.get_canvas_origin()
            img_x = (anchor_pos.x() - draw_x) / old_scale
            img_y = (anchor_pos.y() - draw_y) / old_scale

            self.scale = clamped
            fw = self.current_frame.width if self.current_frame else 1280
            fh = self.current_frame.height if self.current_frame else 720
            new_draw_x = anchor_pos.x() - img_x * self.scale
            new_draw_y = anchor_pos.y() - img_y * self.scale
            self.offset_x = new_draw_x - (self.width() - fw * self.scale) / 2.0
            self.offset_y = new_draw_y - (self.height() - fh * self.scale) / 2.0
        else:
            self.scale = clamped

        self.zoom_changed.emit(self.scale)
        self.update()

    # ---------------- Paint Event & Rendering ----------------

    def _create_checker_tile(self, size: int) -> QPixmap:
        """Create repeating checkerboard tile pixmap for transparency."""
        tile = QPixmap(size * 2, size * 2)
        p = QPainter(tile)
        c1 = QColor(48, 48, 48)
        c2 = QColor(40, 40, 40)
        p.fillRect(0, 0, size, size, c1)
        p.fillRect(size, size, size, size, c1)
        p.fillRect(size, 0, size, size, c2)
        p.fillRect(0, size, size, size, c2)
        p.end()
        return tile

    def paintEvent(self, event: QPaintEvent) -> None:
        """Main rendering pass using pure QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # 1. Fill entire viewport background with quiet neutral gradient
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(22, 22, 25))
        grad.setColorAt(1.0, QColor(16, 16, 18))
        painter.fillRect(self.rect(), grad)

        if not self.current_frame:
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No frame active")
            painter.end()
            return

        fw = self.current_frame.width
        fh = self.current_frame.height
        draw_x, draw_y = self.get_canvas_origin()
        canvas_rect = QRectF(draw_x, draw_y, fw * self.scale, fh * self.scale)

        # 2. Canvas drop shadow & border (subtle neutral shadow, no bright glow)
        shadow_rect = canvas_rect.adjusted(2, 2, 4, 4)
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 75))

        # 3. Canvas checkerboard background (indicates transparent areas)
        painter.save()
        painter.setClipRect(canvas_rect)
        painter.drawTiledPixmap(canvas_rect, self._checker_tile)

        # 4. Render current frame background/base layer
        bg_image = self.current_frame.get_background_image()
        if not bg_image.isNull():
            painter.drawImage(canvas_rect, bg_image)

        # 5. Render Onion Skinning overlay if enabled
        if self.onion_skin_renderer and self.project:
            self.onion_skin_renderer.render_onion_skin(
                painter=painter,
                current_index=self.project.current_frame_index,
                frames=self.project.frames,
                dest_rect=canvas_rect,
            )

        # 6. Render current frame foreground / drawing layers
        fg_image = self.current_frame.get_foreground_composite()
        if not fg_image.isNull():
            painter.drawImage(canvas_rect, fg_image)

        # 7. Render reference image (if loaded and visible)
        if self.project and getattr(self.project, "reference_image", None) and getattr(self.project, "reference_image_visible", False):
            ref = self.project.reference_image
            if not ref.isNull():
                painter.save()
                painter.setOpacity(getattr(self.project, "reference_image_opacity", 0.5))
                painter.drawImage(canvas_rect, ref)
                painter.restore()

        # 8. Render procedural vector skin (if enabled)
        if self.project and getattr(self.project, "skeleton", None) and getattr(self.project, "vector_skin_visible", False):
            self.vector_renderer.render_skin(
                painter=painter,
                skeleton=self.project.skeleton,
                scale=self.scale,
                offset=(draw_x, draw_y),
            )

        # 9. Optional Grid overlay
        if self.show_grid and self.scale >= 2.0:
            grid_pen = QPen(QColor(255, 255, 255, 25), 1.0)
            painter.setPen(grid_pen)
            step = 32.0 * self.scale
            gx = canvas_rect.left()
            while gx <= canvas_rect.right():
                painter.drawLine(QPointF(gx, canvas_rect.top()), QPointF(gx, canvas_rect.bottom()))
                gx += step
            gy = canvas_rect.top()
            while gy <= canvas_rect.bottom():
                painter.drawLine(QPointF(canvas_rect.left(), gy), QPointF(canvas_rect.right(), gy))
                gy += step

        painter.restore()

        # 10. Render frame canvas border outline
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(canvas_rect)

        # 11. Render active tool temporary preview (e.g. Line, Rect preview, or Rigging overlay)
        self.active_tool.draw_overlay(painter, self)

        # Also render skeleton overlay during playback or drawing if enabled
        if self.active_tool.tool_type != ToolType.RIG and self.project and getattr(self.project, "skeleton", None) and getattr(self.project, "skeleton_visible", False):
            self.tools[ToolType.RIG].draw_overlay(painter, self)

        painter.end()

    # ---------------- Mouse & Keyboard Event Handling ----------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self.space_pressed):
            self.is_panning = True
            self._did_pan = False
            self.pan_start_pos = event.position()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.playback_locked:
                event.accept()
                return
            img_pos = self.canvas_to_image(event.position())
            mutating = self.active_tool.tool_type not in (ToolType.COLOR_PICKER, ToolType.SELECT)
            if mutating:
                self.begin_stroke()
            self.active_tool.on_press(event, self, img_pos)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        img_pos = self.canvas_to_image(event.position())
        self.pointer_moved.emit(QPoint(int(img_pos.x()), int(img_pos.y())))

        if self.is_panning:
            delta = event.position() - self.pan_start_pos
            self.pan_start_pos = event.position()
            if delta.x() or delta.y():
                self._did_pan = True
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.update()
            event.accept()
            return

        self.active_tool.on_move(event, self, img_pos)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.is_panning and (event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton)):
            self.is_panning = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor if self.space_pressed else self.active_tool.cursor()))
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            img_pos = self.canvas_to_image(event.position())
            self.active_tool.on_release(event, self, img_pos)
            event.accept()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            super().wheelEvent(event)
            return

        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        new_scale = self.scale * factor
        self._set_zoom(new_scale, anchor_pos=event.position())
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = True
            self._did_pan = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            event.accept()
            return
        if hasattr(self.active_tool, "on_key"):
            if self.active_tool.on_key(event, self):
                event.accept()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.space_pressed = False
            self.setCursor(self.active_tool.cursor())
            if not self._did_pan:
                self.space_tapped.emit()
            event.accept()
            return
        super().keyReleaseEvent(event)
