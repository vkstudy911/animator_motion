"""Project model for AI Doodle Studio.

Manages animation document data, frames, timeline operations, project metadata,
and zip-based project file (.adsproj) serialization and deserialization.
"""

from __future__ import annotations

import datetime
import json
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QImage, QPainter

from app.core.canvas_format import ResizeMode, get_orientation, get_ratio_label, resize_image
from app.core.frame import Frame
from app.core.history import (
    CanvasResizeCommand,
    FrameAddCommand,
    FrameDeleteCommand,
    FrameDuplicateCommand,
    FrameMoveCommand,
    GlobalLayerAddCommand,
    GlobalLayerDeleteCommand,
    GlobalLayerDuplicateCommand,
    GlobalLayerMergeCommand,
    GlobalLayerMoveCommand,
    GlobalLayerPropertyCommand,
    UndoManager,
)
from app.core.layer import Layer, LayerTrack
from app.core.timeline import TimelineModel
from app.media.project_io import atomic_write_zip, encode_qimage_png


from app.animation.interpolation import SkeletonAnimation
from app.models.skeleton import Skeleton


class BackgroundType(Enum):
    TRANSPARENT = "transparent"
    WHITE = "white"
    CUSTOM_COLOR = "custom_color"


def _qcolor_to_hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexArgb)


def _hex_to_qcolor(value: str, fallback: QColor) -> QColor:
    color = QColor(value)
    return color if color.isValid() else fallback


class AnimationProject(QObject):
    """Central project manager for animation data, timeline, and persistence."""

    project_changed = Signal()
    current_frame_changed = Signal(int, object)  # (index, frame)
    frames_modified = Signal()
    frame_changed = Signal(int)
    layers_changed = Signal()
    skeleton_changed = Signal()
    skeleton_pose_changed = Signal()

    def __init__(
        self,
        name: str = "Untitled Animation",
        width: int = 1280,
        height: int = 720,
        fps: int = 12,
        parent: Optional[QObject] = None,
        background_type: Optional[BackgroundType] = None,
        bg_color: Optional[QColor] = None,
        format_label: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.name: str = name
        self.canvas_width: int = width
        self.canvas_height: int = height
        self.format_label: str = format_label or get_ratio_label(width, height)
        self.orientation: str = get_orientation(width, height)
        self.fps: int = max(1, min(60, fps))
        self.save_path: Optional[str] = None
        self.modified: bool = False
        self.background_type: BackgroundType = background_type or BackgroundType.WHITE
        self.background_color: QColor = bg_color or QColor(255, 255, 255, 255)
        self.onion_settings: Dict[str, Any] = {
            "enabled": False,
            "frames_before": 1,
            "frames_after": 1,
            "opacity": 0.35,
            "tint_before": "#FF3333",
            "tint_after": "#33FF33",
        }

        self.metadata: Dict[str, Any] = {
            "name": self.name,
            "author": "AI Doodle Studio User",
            "description": "2D Animation Doodle Project",
            "created_at": datetime.datetime.now().isoformat(),
            "modified_at": datetime.datetime.now().isoformat(),
            "version": "1.0",
        }

        self.undo_manager = UndoManager(max_steps=50, parent=self)
        self.timeline = TimelineModel([], parent=self)
        self.timeline.frame_inserted.connect(self._on_timeline_frame_inserted)
        self.timeline.frame_removed.connect(self._on_timeline_frame_removed)
        self.timeline.frames_reordered.connect(self._on_timeline_reordered)
        self.timeline.frame_updated.connect(self._on_timeline_frame_updated)

        self.layer_tracks: List[LayerTrack] = []
        self._active_layer_index: int = 0
        self.current_frame_index: int = 0

        # Skeletal rigging and animation
        self.skeleton: Optional[Skeleton] = None
        self.skeleton_animation: SkeletonAnimation = SkeletonAnimation(fps=self.fps)
        self.reference_image: Optional[QImage] = None
        self.reference_image_path: Optional[str] = None
        self.reference_image_visible: bool = True
        self.reference_image_opacity: float = 0.5
        self.skeleton_visible: bool = True
        self.vector_skin_visible: bool = True

        self.new_project(
            width=width,
            height=height,
            fps=fps,
            name=name,
            background_type=background_type,
            bg_color=bg_color,
            format_label=self.format_label,
        )

    @property
    def active_layer_index(self) -> int:
        return self._active_layer_index

    @active_layer_index.setter
    def active_layer_index(self, index: int) -> None:
        if self.layer_tracks:
            self._active_layer_index = max(0, min(index, len(self.layer_tracks) - 1))
        else:
            self._active_layer_index = 0

    @property
    def frames(self) -> List[Frame]:
        return self.timeline.frames

    def _bg_fill(self) -> Optional[QColor]:
        if self.background_type == BackgroundType.TRANSPARENT:
            return QColor(0, 0, 0, 0)
        if self.background_type == BackgroundType.WHITE:
            return QColor(255, 255, 255, 255)
        return QColor(self.background_color)

    def new_project(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 12,
        name: str = "Untitled Animation",
        bg_color: Optional[QColor] = None,
        background_type: Optional[BackgroundType] = None,
        format_label: Optional[str] = None,
    ) -> None:
        self.name = name.strip() or "Untitled Animation"
        self.canvas_width = width
        self.canvas_height = height
        self.format_label = format_label or get_ratio_label(width, height)
        self.orientation = get_orientation(width, height)
        self.fps = max(1, min(60, fps))
        self.save_path = None
        self.modified = False

        if background_type is not None:
            self.background_type = background_type
        elif bg_color is not None and bg_color.alpha() == 0:
            self.background_type = BackgroundType.TRANSPARENT
        elif bg_color is not None and bg_color == QColor(255, 255, 255, 255):
            self.background_type = BackgroundType.WHITE
        elif bg_color is not None:
            self.background_type = BackgroundType.CUSTOM_COLOR
            self.background_color = QColor(bg_color)

        if self.background_type == BackgroundType.WHITE:
            self.background_color = QColor(255, 255, 255, 255)
        elif self.background_type == BackgroundType.TRANSPARENT:
            self.background_color = QColor(0, 0, 0, 0)

        self.metadata = {
            "name": self.name,
            "author": "AI Doodle Studio User",
            "description": "2D Animation Doodle Project",
            "created_at": datetime.datetime.now().isoformat(),
            "modified_at": datetime.datetime.now().isoformat(),
            "version": "1.0",
        }

        self.onion_settings = {
            "enabled": False,
            "frames_before": 2,
            "frames_after": 1,
            "opacity": 0.35,
            "tint_before": "#EB4B4B",
            "tint_after": "#4BC864",
        }

        self.undo_manager.clear()
        default_track = LayerTrack(name="Layer 1")
        self.layer_tracks = [default_track]
        self._active_layer_index = 0

        initial_layer = Layer(
            width=self.canvas_width,
            height=self.canvas_height,
            track=default_track,
        )
        initial_frame = Frame(
            width=self.canvas_width,
            height=self.canvas_height,
            background_color=self._bg_fill(),
            layers=[initial_layer],
            project=self,
        )
        self.timeline.set_frames([initial_frame])
        self.current_frame_index = 0

        self.project_changed.emit()
        self.current_frame_changed.emit(0, initial_frame)
        self.layers_changed.emit()
        self.skeleton_changed.emit()

    def frame_count(self) -> int:
        return self.timeline.frame_count()

    def get_current_frame(self) -> Optional[Frame]:
        return self.timeline.get_frame_at(self.current_frame_index)

    def set_current_frame(self, index: int) -> bool:
        if 0 <= index < self.timeline.frame_count():
            if self.current_frame_index != index:
                self.current_frame_index = index
                frame = self.timeline.get_frame_at(index)
                if self.skeleton and self.skeleton_animation:
                    self.skeleton_animation.apply_to_skeleton(index, self.skeleton)
                    self.skeleton_pose_changed.emit()
                self.current_frame_changed.emit(index, frame)
                self.layers_changed.emit()
            return True
        return False

    def add_frame(self, index: Optional[int] = None, frame: Optional[Frame] = None, record_undo: bool = True) -> int:
        insert_idx = index if index is not None else self.current_frame_index + 1
        if frame is not None:
            new_frame = frame
        else:
            new_layers = [
                Layer(width=self.canvas_width, height=self.canvas_height, track=track)
                for track in self.layer_tracks
            ]
            new_frame = Frame(
                width=self.canvas_width,
                height=self.canvas_height,
                background_color=self._bg_fill(),
                layers=new_layers,
            )
        new_frame.project = self
        actual_idx = self.timeline.insert_frame(insert_idx, new_frame)
        self.modified = True
        self.set_current_frame(actual_idx)
        if record_undo and self.undo_manager:
            self.undo_manager.push(FrameAddCommand(self, actual_idx, new_frame))
        self.frames_modified.emit()
        return actual_idx

    def _insert_layer_track(
        self,
        index: int,
        track: LayerTrack,
        cels: Optional[List[QImage]] = None,
        record_undo: bool = True,
    ) -> None:
        if index < 0 or index > len(self.layer_tracks):
            index = len(self.layer_tracks)
        self.layer_tracks.insert(index, track)
        for f_idx, frame in enumerate(self.frames):
            img = cels[f_idx].copy() if (cels and f_idx < len(cels)) else None
            layer = Layer(
                width=self.canvas_width,
                height=self.canvas_height,
                image=img,
                track=track,
            )
            frame.layers.insert(index, layer)
            frame.mark_modified()
        self._active_layer_index = index
        self.modified = True
        self.layers_changed.emit()
        self.frames_modified.emit()

    def add_layer(self, name: Optional[str] = None, record_undo: bool = True) -> LayerTrack:
        label = name or f"Layer {len(self.layer_tracks) + 1}"
        new_track = LayerTrack(name=label)
        idx = len(self.layer_tracks)
        self._insert_layer_track(idx, new_track, None, record_undo=False)
        if record_undo and self.undo_manager:
            self.undo_manager.push(GlobalLayerAddCommand(self, idx, new_track))
        return new_track

    def duplicate_layer(self, index: Optional[int] = None, record_undo: bool = True) -> Optional[LayerTrack]:
        target_idx = index if index is not None else self.active_layer_index
        if not (0 <= target_idx < len(self.layer_tracks)):
            return None
        src_track = self.layer_tracks[target_idx]
        new_track = LayerTrack(
            name=f"{src_track.name} Copy",
            visible=src_track.visible,
            opacity=src_track.opacity,
            locked=src_track.locked,
            blend_mode=src_track.blend_mode,
        )
        insert_idx = target_idx + 1
        cel_images = [frame.layers[target_idx].image.copy() for frame in self.frames]
        self._insert_layer_track(insert_idx, new_track, cel_images, record_undo=False)
        if record_undo and self.undo_manager:
            self.undo_manager.push(
                GlobalLayerDuplicateCommand(self, target_idx, insert_idx, new_track, cel_images)
            )
        return new_track

    def delete_layer(self, index: Optional[int] = None, record_undo: bool = True) -> bool:
        if len(self.layer_tracks) <= 1:
            return False
        target_idx = index if index is not None else self.active_layer_index
        if not (0 <= target_idx < len(self.layer_tracks)):
            return False
        del_track = self.layer_tracks[target_idx]
        if del_track.locked:
            return False
        cel_images = [frame.layers[target_idx].image.copy() for frame in self.frames]
        self.layer_tracks.pop(target_idx)
        for frame in self.frames:
            if target_idx < len(frame.layers):
                frame.layers.pop(target_idx)
                frame.mark_modified()
        self._active_layer_index = max(0, min(target_idx, len(self.layer_tracks) - 1))
        self.modified = True
        if record_undo and self.undo_manager:
            self.undo_manager.push(
                GlobalLayerDeleteCommand(self, target_idx, del_track, cel_images)
            )
        self.layers_changed.emit()
        self.frames_modified.emit()
        return True

    def move_layer(self, from_idx: int, to_idx: int, record_undo: bool = True) -> bool:
        if from_idx == to_idx:
            return False
        if not (0 <= from_idx < len(self.layer_tracks) and 0 <= to_idx < len(self.layer_tracks)):
            return False
        if self.layer_tracks[from_idx].locked:
            return False
        track = self.layer_tracks.pop(from_idx)
        self.layer_tracks.insert(to_idx, track)
        for frame in self.frames:
            if from_idx < len(frame.layers):
                layer = frame.layers.pop(from_idx)
                frame.layers.insert(to_idx, layer)
                frame.mark_modified()
        self._active_layer_index = to_idx
        self.modified = True
        if record_undo and self.undo_manager:
            self.undo_manager.push(GlobalLayerMoveCommand(self, from_idx, to_idx))
        self.layers_changed.emit()
        self.frames_modified.emit()
        return True

    def merge_down_layer(self, index: Optional[int] = None, record_undo: bool = True) -> bool:
        target_idx = index if index is not None else self.active_layer_index
        if target_idx <= 0 or target_idx >= len(self.layer_tracks):
            return False
        upper = self.layer_tracks[target_idx]
        lower = self.layer_tracks[target_idx - 1]
        if upper.locked or lower.locked:
            return False
        before_upper = [f.layers[target_idx].image.copy() for f in self.frames]
        before_lower = [f.layers[target_idx - 1].image.copy() for f in self.frames]
        for frame in self.frames:
            lower_layer = frame.layers[target_idx - 1]
            upper_layer = frame.layers[target_idx]
            painter = QPainter(lower_layer.image)
            painter.setOpacity(upper.opacity)
            painter.setCompositionMode(upper.composition_mode())
            painter.drawImage(0, 0, upper_layer.image)
            painter.end()
            frame.layers.pop(target_idx)
            frame.mark_modified()
        del_track = self.layer_tracks.pop(target_idx)
        self._active_layer_index = target_idx - 1
        self.modified = True
        if record_undo and self.undo_manager:
            self.undo_manager.push(
                GlobalLayerMergeCommand(self, target_idx, del_track, before_upper, before_lower)
            )
        self.layers_changed.emit()
        self.frames_modified.emit()
        return True

    def set_layer_property(
        self,
        track_index: int,
        property_name: str,
        new_value: Any,
        record_undo: bool = True,
    ) -> None:
        if not (0 <= track_index < len(self.layer_tracks)):
            return
        track = self.layer_tracks[track_index]
        old_value = getattr(track, property_name)
        if old_value == new_value:
            return
        setattr(track, property_name, new_value)
        for frame in self.frames:
            frame.mark_modified()
        self.modified = True
        if record_undo and self.undo_manager:
            self.undo_manager.push(
                GlobalLayerPropertyCommand(self, track_index, property_name, old_value, new_value)
            )
        self.layers_changed.emit()
        self.frames_modified.emit()

    def duplicate_frame(self, index: Optional[int] = None, record_undo: bool = True) -> int:
        target_idx = index if index is not None else self.current_frame_index
        new_idx = self.timeline.duplicate_frame(target_idx)
        if new_idx >= 0:
            self.modified = True
            self.set_current_frame(new_idx)
            if record_undo and self.undo_manager:
                cloned = self.frames[new_idx]
                self.undo_manager.push(FrameDuplicateCommand(self, target_idx, new_idx, cloned))
            self.frames_modified.emit()
        return new_idx

    def delete_frame(self, index: Optional[int] = None, record_undo: bool = True) -> bool:
        if self.timeline.frame_count() <= 1:
            return False
        target_idx = index if index is not None else self.current_frame_index
        if not (0 <= target_idx < self.timeline.frame_count()):
            return False
        frame_to_delete = self.frames[target_idx]
        removed = self.timeline.remove_frame(target_idx)
        if removed is not None:
            self.modified = True
            new_idx = min(target_idx, self.timeline.frame_count() - 1)
            self.current_frame_index = -1
            self.set_current_frame(new_idx)
            if record_undo and self.undo_manager:
                self.undo_manager.push(FrameDeleteCommand(self, target_idx, frame_to_delete))
            self.frames_modified.emit()
            return True
        return False

    def move_frame(self, from_idx: int, to_idx: int, record_undo: bool = True) -> bool:
        if from_idx == to_idx:
            return False
        success = self.timeline.move_frame(from_idx, to_idx)
        if success:
            self.modified = True
            self.set_current_frame(to_idx)
            if record_undo and self.undo_manager:
                self.undo_manager.push(FrameMoveCommand(self, from_idx, to_idx))
            self.frames_modified.emit()
        return success

    def mark_modified(self) -> None:
        self.modified = True
        self.metadata["modified_at"] = datetime.datetime.now().isoformat()
        current_frame = self.get_current_frame()
        if current_frame:
            current_frame.mark_modified()
        self.frame_changed.emit(self.current_frame_index)
        self.frames_modified.emit()

    def set_fps(self, fps: int) -> None:
        self.fps = max(1, min(60, fps))
        self.modified = True
        self.project_changed.emit()

    def set_static_background_image(self, image: QImage) -> None:
        """Place a fitted image as the bottom layer of every frame."""
        if not self.layer_tracks or self.layer_tracks[0].name.lower() != "background":
            bg_track = LayerTrack(name="Background")
            self._insert_layer_track(0, bg_track, None, record_undo=False)
        for frame in self.frames:
            p = QPainter(frame.layers[0].image)
            p.drawImage(0, 0, image)
            p.end()
            frame.mark_modified()
        self.modified = True
        self.frames_modified.emit()
        self.layers_changed.emit()

    def resize_canvas(
        self,
        new_width: int,
        new_height: int,
        mode: ResizeMode = ResizeMode.SCALE,
        record_undo: bool = True,
        format_label: Optional[str] = None,
    ) -> bool:
        if new_width <= 0 or new_height <= 0:
            return False
        if self.canvas_width == new_width and self.canvas_height == new_height:
            if format_label and getattr(self, "format_label", "") != format_label:
                self.format_label = format_label
                self.project_changed.emit()
            return True

        old_w, old_h = self.canvas_width, self.canvas_height
        old_label = getattr(self, "format_label", get_ratio_label(old_w, old_h))
        new_label = format_label or get_ratio_label(new_width, new_height)

        old_cels: List[List[QImage]] = []
        new_cels: List[List[QImage]] = []

        for frame in self.frames:
            frame_old: List[QImage] = []
            frame_new: List[QImage] = []
            for layer in frame.layers:
                frame_old.append(layer.image.copy())
                resized_img = resize_image(layer.image, new_width, new_height, mode)
                frame_new.append(resized_img)
                layer.set_image(resized_img)
            old_cels.append(frame_old)
            new_cels.append(frame_new)
            frame.mark_modified()

        self.canvas_width = new_width
        self.canvas_height = new_height
        self.format_label = new_label
        self.orientation = get_orientation(new_width, new_height)
        self.modified = True

        if record_undo and self.undo_manager:
            cmd = CanvasResizeCommand(
                project=self,
                before_w=old_w,
                before_h=old_h,
                after_w=new_width,
                after_h=new_height,
                before_cels=old_cels,
                after_cels=new_cels,
                before_format=old_label,
                after_format=new_label,
            )
            self.undo_manager.push(cmd)

        self.frames_modified.emit()
        self.layers_changed.emit()
        self.project_changed.emit()
        return True

    def save_project(self, file_path: Optional[str] = None) -> bool:
        target_path = file_path or self.save_path
        if not target_path:
            return False
        if not target_path.endswith(".adsproj"):
            target_path += ".adsproj"

        self.metadata["name"] = self.name
        self.metadata["modified_at"] = datetime.datetime.now().isoformat()

        manifest: Dict[str, Any] = {
            "format": "adsproj",
            "version": 2,
            "generator": "AI Doodle Studio v2.0.0",
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "format_label": getattr(self, "format_label", get_ratio_label(self.canvas_width, self.canvas_height)),
            "orientation": getattr(self, "orientation", get_orientation(self.canvas_width, self.canvas_height)),
            "fps": self.fps,
            "background_type": self.background_type.value,
            "background_color": _qcolor_to_hex(self.background_color),
            "metadata": self.metadata,
            "onion_skin_settings": self.onion_settings,
            "frame_count": self.timeline.frame_count(),
            "layer_tracks": [t.to_dict() for t in self.layer_tracks],
            "active_layer_index": self.active_layer_index,
            "skeleton": self.skeleton.to_dict() if self.skeleton else None,
            "skeleton_animation": self.skeleton_animation.to_dict() if self.skeleton_animation else None,
            "reference_image_path": self.reference_image_path or "",
            "reference_image_visible": self.reference_image_visible,
            "skeleton_visible": self.skeleton_visible,
            "vector_skin_visible": self.vector_skin_visible,
            "frames": [],
        }

        files: Dict[str, bytes] = {}
        if self.reference_image and not self.reference_image.isNull():
            files["reference.png"] = encode_qimage_png(self.reference_image)
        try:
            for idx, frame in enumerate(self.timeline.frames):
                frame_filename = f"frames/frame_{idx:05d}.png"
                thumb_filename = f"thumbnails/thumb_{idx:05d}.png"
                layer_entries = []
                for lidx, layer in enumerate(frame.layers):
                    layer_filename = f"frames/frame_{idx:05d}_l{lidx:02d}.png"
                    layer_entries.append({
                        "track_id": layer.track.id,
                        "filename": layer_filename,
                    })
                    files[layer_filename] = encode_qimage_png(layer.image)

                manifest["frames"].append({
                    "index": idx,
                    "id": frame.id,
                    "name": frame.name,
                    "filename": frame_filename,
                    "layers": layer_entries,
                })
                files[frame_filename] = encode_qimage_png(frame.get_image())
                files[thumb_filename] = encode_qimage_png(
                    frame.get_thumbnail().toImage()
                )

            files["project.json"] = json.dumps(manifest, indent=2).encode("utf-8")
            atomic_write_zip(target_path, files)

            self.save_path = target_path
            self.modified = False
            self.project_changed.emit()
            return True
        except Exception as exc:
            print(f"Error saving project to {target_path}: {exc}")
            return False

    def load_project(self, file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False

        try:
            import zipfile

            with zipfile.ZipFile(file_path, "r") as zf:
                names = set(zf.namelist())
                if "project.json" not in names:
                    return False
                manifest = json.loads(zf.read("project.json").decode("utf-8"))

                name = manifest.get("metadata", {}).get("name", os.path.basename(file_path))
                width = manifest.get("canvas_width", 1280)
                height = manifest.get("canvas_height", 720)
                fps = manifest.get("fps", 12)
                bg_type = manifest.get("background_type", "white")
                try:
                    self.background_type = BackgroundType(bg_type)
                except ValueError:
                    self.background_type = BackgroundType.WHITE
                self.background_color = _hex_to_qcolor(
                    manifest.get("background_color", "#FFFFFFFF"),
                    QColor(255, 255, 255),
                )
                if "onion_skin_settings" in manifest:
                    self.onion_settings.update(manifest["onion_skin_settings"])

                raw_tracks = manifest.get("layer_tracks")
                if raw_tracks:
                    self.layer_tracks = [LayerTrack.from_dict(t) for t in raw_tracks]
                    self._active_layer_index = max(
                        0, min(manifest.get("active_layer_index", 0), len(self.layer_tracks) - 1)
                    )
                else:
                    # Version 1 migration: collect unique layer tracks across frames
                    seen_ids = set()
                    self.layer_tracks = []
                    for entry in manifest.get("frames", []):
                        for l_meta in entry.get("layers", []):
                            lid = l_meta.get("id") or l_meta.get("name", "Layer")
                            if lid not in seen_ids:
                                seen_ids.add(lid)
                                self.layer_tracks.append(LayerTrack.from_dict(l_meta))
                    if not self.layer_tracks:
                        self.layer_tracks = [LayerTrack(name="Layer 1")]
                    self._active_layer_index = 0

                frames: List[Frame] = []
                frame_entries = manifest.get("frames", [])
                for entry in sorted(frame_entries, key=lambda e: e.get("index", 0)):
                    layers_meta = entry.get("layers") or []
                    cel_images = {}
                    for lidx, layer_entry in enumerate(layers_meta):
                        tid = layer_entry.get("track_id") or layer_entry.get("id")
                        fname = layer_entry.get("filename")
                        if fname and fname in names:
                            img = QImage()
                            img.loadFromData(zf.read(fname), "PNG")
                            if img.format() != QImage.Format.Format_ARGB32_Premultiplied:
                                img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                            if tid:
                                cel_images[tid] = img
                            cel_images[lidx] = img

                    if not cel_images:
                        fname = entry.get("filename")
                        if fname and fname in names:
                            img = QImage()
                            img.loadFromData(zf.read(fname), "PNG")
                            if img.format() != QImage.Format.Format_ARGB32_Premultiplied:
                                img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                            cel_images[0] = img

                    frame_layers: List[Layer] = []
                    for lidx, track in enumerate(self.layer_tracks):
                        img = cel_images.get(track.id) or cel_images.get(lidx)
                        layer = Layer(
                            width=width,
                            height=height,
                            image=img,
                            track=track,
                        )
                        frame_layers.append(layer)

                    frame = Frame(
                        width=width,
                        height=height,
                        layers=frame_layers,
                        background_color=self._bg_fill(),
                        frame_id=entry.get("id"),
                        name=entry.get("name"),
                        project=self,
                    )
                    frames.append(frame)

                if not frames:
                    frame = Frame(
                        width=width,
                        height=height,
                        layers=[Layer(width=width, height=height, track=self.layer_tracks[0])],
                        background_color=self._bg_fill(),
                        project=self,
                    )
                    frames = [frame]

                for f in frames:
                    f.project = self

                self.name = name
                self.canvas_width = width
                self.canvas_height = height
                self.format_label = manifest.get("format_label", get_ratio_label(width, height))
                self.orientation = manifest.get("orientation", get_orientation(width, height))
                self.fps = fps
                self.metadata = manifest.get("metadata", {})
                self.save_path = file_path
                self.modified = False
                self.undo_manager.clear()
                self.timeline.set_frames(frames)
                self.current_frame_index = 0
                # Restore Skeletal Rigging & Animation
                skel_data = manifest.get("skeleton")
                if skel_data:
                    try:
                        self.skeleton = Skeleton.from_dict(skel_data)
                    except Exception as exc:
                        print(f"Warning: Failed to load skeleton: {exc}")
                        self.skeleton = None
                else:
                    self.skeleton = None

                anim_data = manifest.get("skeleton_animation")
                if anim_data:
                    try:
                        self.skeleton_animation = SkeletonAnimation.from_dict(anim_data)
                    except Exception as exc:
                        print(f"Warning: Failed to load skeleton animation: {exc}")
                        self.skeleton_animation = SkeletonAnimation(fps=self.fps)
                else:
                    self.skeleton_animation = SkeletonAnimation(fps=self.fps)

                if "reference.png" in names:
                    ref_img = QImage()
                    ref_img.loadFromData(zf.read("reference.png"), "PNG")
                    self.reference_image = ref_img
                elif manifest.get("reference_image_path") and os.path.exists(manifest["reference_image_path"]):
                    self.reference_image = QImage(manifest["reference_image_path"])
                else:
                    self.reference_image = None

                self.reference_image_path = manifest.get("reference_image_path")
                self.reference_image_visible = manifest.get("reference_image_visible", True)
                self.skeleton_visible = manifest.get("skeleton_visible", True)
                self.vector_skin_visible = manifest.get("vector_skin_visible", True)

                self.project_changed.emit()
                self.current_frame_changed.emit(0, frames[0])
                self.layers_changed.emit()
                self.skeleton_changed.emit()
                return True
        except Exception as exc:
            print(f"Error loading project from {file_path}: {exc}")
            return False

    def _on_timeline_frame_inserted(self, index: int) -> None:
        self.project_changed.emit()

    def _on_timeline_frame_removed(self, index: int) -> None:
        self.project_changed.emit()

    def _on_timeline_reordered(self) -> None:
        self.project_changed.emit()

    def _on_timeline_frame_updated(self, index: int) -> None:
        self.frame_changed.emit(index)
        self.frames_modified.emit()
