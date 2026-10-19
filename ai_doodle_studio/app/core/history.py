"""Undo/redo history system for AI Doodle Studio.

Manages command objects with a configurable depth limit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from app.core.frame import Frame
from app.core.layer import Layer, LayerTrack


class UndoCommand(ABC):
    """Abstract base class for all undoable commands."""

    def __init__(self, description: str = "") -> None:
        self.description = description

    @abstractmethod
    def undo(self) -> None:
        pass

    @abstractmethod
    def redo(self) -> None:
        pass


class DrawCommand(UndoCommand):
    """Restores before/after raster state on a specific layer of a Frame."""

    def __init__(
        self,
        frame: Frame,
        before_image: QImage,
        after_image: QImage,
        on_update: Optional[Callable[[], None]] = None,
        description: str = "Drawing stroke",
        layer_index: Optional[int] = None,
        project: Optional[Any] = None,
    ) -> None:
        super().__init__(description)
        self.frame = frame
        self.project = project
        self.layer_index = frame.active_layer_index if layer_index is None else layer_index
        self.before_image: QImage = before_image.copy()
        self.after_image: QImage = after_image.copy()
        self.on_update = on_update

    def undo(self) -> None:
        self.frame.set_layer_image(self.layer_index, self.before_image.copy())
        if self.project:
            try:
                idx = self.project.frames.index(self.frame)
                self.project.set_current_frame(idx)
                self.project.mark_modified()
            except (ValueError, AttributeError):
                pass
        if self.on_update:
            self.on_update()

    def redo(self) -> None:
        self.frame.set_layer_image(self.layer_index, self.after_image.copy())
        if self.project:
            try:
                idx = self.project.frames.index(self.frame)
                self.project.set_current_frame(idx)
                self.project.mark_modified()
            except (ValueError, AttributeError):
                pass
        if self.on_update:
            self.on_update()


class FrameAddCommand(UndoCommand):
    def __init__(
        self,
        project: Any,
        index: int,
        frame: Frame,
        description: str = "Add Frame",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.index = index
        self.frame = frame

    def undo(self) -> None:
        self.project.delete_frame(self.index, record_undo=False)

    def redo(self) -> None:
        self.project.add_frame(index=self.index, frame=self.frame, record_undo=False)


class FrameDeleteCommand(UndoCommand):
    def __init__(
        self,
        project: Any,
        index: int,
        frame: Frame,
        description: str = "Delete Frame",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.index = index
        self.frame = frame

    def undo(self) -> None:
        self.project.add_frame(index=self.index, frame=self.frame, record_undo=False)

    def redo(self) -> None:
        self.project.delete_frame(self.index, record_undo=False)


class FrameDuplicateCommand(UndoCommand):
    def __init__(
        self,
        project: Any,
        source_index: int,
        new_index: int,
        frame: Frame,
        description: str = "Duplicate Frame",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.source_index = source_index
        self.new_index = new_index
        self.frame = frame

    def undo(self) -> None:
        self.project.delete_frame(self.new_index, record_undo=False)

    def redo(self) -> None:
        self.project.add_frame(index=self.new_index, frame=self.frame, record_undo=False)


class FrameMoveCommand(UndoCommand):
    def __init__(
        self,
        project: Any,
        from_index: int,
        to_index: int,
        description: str = "Move Frame",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.from_index = from_index
        self.to_index = to_index

    def undo(self) -> None:
        self.project.move_frame(self.to_index, self.from_index, record_undo=False)

    def redo(self) -> None:
        self.project.move_frame(self.from_index, self.to_index, record_undo=False)


class LayerSnapshotCommand(UndoCommand):
    """Generic layer-stack snapshot for add/delete/merge/reorder."""

    def __init__(
        self,
        frame: Frame,
        before_layers: List[Layer],
        after_layers: List[Layer],
        before_active: int,
        after_active: int,
        project: Optional[Any] = None,
        on_update: Optional[Callable[[], None]] = None,
        description: str = "Layer change",
    ) -> None:
        super().__init__(description)
        self.frame = frame
        self.before_layers = [layer.clone() for layer in before_layers]
        self.after_layers = [layer.clone() for layer in after_layers]
        self.before_active = before_active
        self.after_active = after_active
        self.project = project
        self.on_update = on_update

    def _apply(self, layers: List[Layer], active: int) -> None:
        self.frame.layers = [layer.clone() for layer in layers]
        self.frame.active_layer_index = active
        self.frame.mark_modified()
        if self.project is not None:
            self.project.modified = True
            if hasattr(self.project, "layers_changed"):
                self.project.layers_changed.emit()
            if hasattr(self.project, "frames_modified"):
                self.project.frames_modified.emit()
        if self.on_update:
            self.on_update()

    def undo(self) -> None:
        self._apply(self.before_layers, self.before_active)

    def redo(self) -> None:
        self._apply(self.after_layers, self.after_active)


class LayerPropertyCommand(UndoCommand):
    """Undo/redo for layer property changes: visibility, lock, opacity, name, blend_mode."""

    def __init__(
        self,
        frame: Frame,
        layer_index: int,
        property_name: str,
        old_value: Any,
        new_value: Any,
        project: Optional[Any] = None,
        on_update: Optional[Callable[[], None]] = None,
        description: str = "Change layer property",
    ) -> None:
        super().__init__(description)
        self.frame = frame
        self.layer_index = layer_index
        self.property_name = property_name
        self.old_value = old_value
        self.new_value = new_value
        self.project = project
        self.on_update = on_update

    def _apply(self, value: Any) -> None:
        if 0 <= self.layer_index < len(self.frame.layers):
            layer = self.frame.layers[self.layer_index]
            setattr(layer, self.property_name, value)
            self.frame.mark_modified()
            if self.project is not None:
                self.project.modified = True
                if hasattr(self.project, "layers_changed"):
                    self.project.layers_changed.emit()
                if hasattr(self.project, "frames_modified"):
                    self.project.frames_modified.emit()
            if self.on_update:
                self.on_update()

    def undo(self) -> None:
        self._apply(self.old_value)

    def redo(self) -> None:
        self._apply(self.new_value)


class GlobalLayerAddCommand(UndoCommand):
    """Undo/redo adding a timeline-wide layer track."""

    def __init__(
        self,
        project: Any,
        track_index: int,
        track: LayerTrack,
        description: str = "Add Layer",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.track_index = track_index
        self.track = track

    def undo(self) -> None:
        self.project.delete_layer(self.track_index, record_undo=False)

    def redo(self) -> None:
        self.project._insert_layer_track(self.track_index, self.track, None, record_undo=False)


class GlobalLayerDeleteCommand(UndoCommand):
    """Undo/redo deleting a timeline-wide layer track with all frame cels."""

    def __init__(
        self,
        project: Any,
        track_index: int,
        track: LayerTrack,
        cels: List[QImage],
        description: str = "Delete Layer",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.track_index = track_index
        self.track = track
        self.cels = [img.copy() for img in cels]

    def undo(self) -> None:
        self.project._insert_layer_track(self.track_index, self.track, self.cels, record_undo=False)

    def redo(self) -> None:
        self.project.delete_layer(self.track_index, record_undo=False)


class GlobalLayerDuplicateCommand(UndoCommand):
    """Undo/redo duplicating a timeline-wide layer track with all frame cels."""

    def __init__(
        self,
        project: Any,
        source_index: int,
        new_index: int,
        track: LayerTrack,
        cels: List[QImage],
        description: str = "Duplicate Layer",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.source_index = source_index
        self.new_index = new_index
        self.track = track
        self.cels = [img.copy() for img in cels]

    def undo(self) -> None:
        self.project.delete_layer(self.new_index, record_undo=False)

    def redo(self) -> None:
        self.project._insert_layer_track(self.new_index, self.track, self.cels, record_undo=False)


class GlobalLayerMoveCommand(UndoCommand):
    """Undo/redo reordering layer tracks timeline-wide."""

    def __init__(
        self,
        project: Any,
        from_index: int,
        to_index: int,
        description: str = "Move Layer",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.from_index = from_index
        self.to_index = to_index

    def undo(self) -> None:
        self.project.move_layer(self.to_index, self.from_index, record_undo=False)

    def redo(self) -> None:
        self.project.move_layer(self.from_index, self.to_index, record_undo=False)


class GlobalLayerMergeCommand(UndoCommand):
    """Undo/redo merging a layer track down into the one beneath it across all frames."""

    def __init__(
        self,
        project: Any,
        upper_index: int,
        upper_track: LayerTrack,
        before_upper_cels: List[QImage],
        before_lower_cels: List[QImage],
        description: str = "Merge Layer Down",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.upper_index = upper_index
        self.upper_track = upper_track
        self.before_upper_cels = [img.copy() for img in before_upper_cels]
        self.before_lower_cels = [img.copy() for img in before_lower_cels]

    def undo(self) -> None:
        lower_idx = self.upper_index - 1
        for frame, lower_img in zip(self.project.frames, self.before_lower_cels):
            if 0 <= lower_idx < len(frame.layers):
                frame.layers[lower_idx].set_image(lower_img.copy())
                frame.mark_modified()
        self.project._insert_layer_track(self.upper_index, self.upper_track, self.before_upper_cels, record_undo=False)

    def redo(self) -> None:
        self.project.merge_down_layer(self.upper_index, record_undo=False)


class GlobalLayerPropertyCommand(UndoCommand):
    """Undo/redo changing a layer property across all frames."""

    def __init__(
        self,
        project: Any,
        track_index: int,
        property_name: str,
        old_value: Any,
        new_value: Any,
        description: str = "Change Layer Property",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.track_index = track_index
        self.property_name = property_name
        self.old_value = old_value
        self.new_value = new_value

    def _apply(self, value: Any) -> None:
        self.project.set_layer_property(self.track_index, self.property_name, value, record_undo=False)

    def undo(self) -> None:
        self._apply(self.old_value)

    def redo(self) -> None:
        self._apply(self.new_value)


class CanvasResizeCommand(UndoCommand):
    """Undo/redo for resizing the project canvas dimensions and cels."""

    def __init__(
        self,
        project: Any,
        before_w: int,
        before_h: int,
        after_w: int,
        after_h: int,
        before_cels: List[List[QImage]],
        after_cels: List[List[QImage]],
        before_format: str,
        after_format: str,
        description: str = "Resize Canvas",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.before_w = before_w
        self.before_h = before_h
        self.after_w = after_w
        self.after_h = after_h
        self.before_cels = [[img.copy() for img in f_cels] for f_cels in before_cels]
        self.after_cels = [[img.copy() for img in f_cels] for f_cels in after_cels]
        self.before_format = before_format
        self.after_format = after_format

    def _apply(self, w: int, h: int, fmt: str, cels: List[List[QImage]]) -> None:
        from app.core.canvas_format import get_orientation

        self.project.canvas_width = w
        self.project.canvas_height = h
        self.project.format_label = fmt
        self.project.orientation = get_orientation(w, h)
        for f_idx, frame in enumerate(self.project.frames):
            if f_idx < len(cels):
                for l_idx, layer in enumerate(frame.layers):
                    if l_idx < len(cels[f_idx]):
                        layer.set_image(cels[f_idx][l_idx].copy())
            frame.mark_modified()
        self.project.modified = True
        self.project.project_changed.emit()
        self.project.frames_modified.emit()
        self.project.layers_changed.emit()

    def undo(self) -> None:
        self._apply(self.before_w, self.before_h, self.before_format, self.before_cels)

    def redo(self) -> None:
        self._apply(self.after_w, self.after_h, self.after_format, self.after_cels)


class RigEditCommand(UndoCommand):
    """Restores before/after skeletal rig state for undo/redo."""

    def __init__(
        self,
        project: Any,
        before_skeleton: Optional[Any],
        after_skeleton: Optional[Any],
        on_update: Optional[Callable[[], None]] = None,
        description: str = "Rig Edit",
    ) -> None:
        super().__init__(description)
        self.project = project
        self.before_skeleton = before_skeleton.clone() if before_skeleton else None
        self.after_skeleton = after_skeleton.clone() if after_skeleton else None
        self.on_update = on_update

    def undo(self) -> None:
        self.project.skeleton = self.before_skeleton.clone() if self.before_skeleton else None
        self.project.modified = True
        if hasattr(self.project, "skeleton_changed"):
            self.project.skeleton_changed.emit()
        if self.on_update:
            self.on_update()

    def redo(self) -> None:
        self.project.skeleton = self.after_skeleton.clone() if self.after_skeleton else None
        self.project.modified = True
        if hasattr(self.project, "skeleton_changed"):
            self.project.skeleton_changed.emit()
        if self.on_update:
            self.on_update()


class UndoManager(QObject):
    undo_state_changed = Signal(bool, bool)

    def __init__(self, max_steps: int = 50, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.max_steps: int = max_steps
        self._undo_stack: List[UndoCommand] = []
        self._redo_stack: List[UndoCommand] = []

    def push(self, command: UndoCommand) -> None:
        self._undo_stack.append(command)
        if len(self._undo_stack) > self.max_steps:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._notify_state()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify_state()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.redo()
        self._undo_stack.append(cmd)
        self._notify_state()
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def undo_text(self) -> str:
        return self._undo_stack[-1].description if self._undo_stack else "Undo"

    def redo_text(self) -> str:
        return self._redo_stack[-1].description if self._redo_stack else "Redo"

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify_state()

    def _notify_state(self) -> None:
        self.undo_state_changed.emit(self.can_undo(), self.can_redo())
