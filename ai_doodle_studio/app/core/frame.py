"""Frame data model for AI Doodle Studio.

A frame is a stack of layers composited into a cached ARGB32 image,
with thumbnail caching and modification tracking.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from app.core.layer import Layer


class Frame:
    """A single animation frame composed of one or more raster layers."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        image: Optional[QImage] = None,
        background_color: Optional[QColor] = None,
        frame_id: Optional[str] = None,
        layers: Optional[List[Layer]] = None,
        name: Optional[str] = None,
        project: Optional[Any] = None,
    ) -> None:
        self.id: str = frame_id or str(uuid.uuid4())
        self.name: Optional[str] = name
        self.project: Optional[Any] = project
        self.modified: bool = False
        self._thumbnail_cache: Optional[QPixmap] = None
        self._thumbnail_size: tuple[int, int] = (120, 90)
        self._composite: Optional[QImage] = None
        self._foreground_composite: Optional[QImage] = None
        self._composite_dirty: bool = True
        self._active_layer_index: int = 0
        self.background_color: Optional[QColor] = (
            QColor(background_color) if background_color is not None else None
        )

        if layers is not None and layers:
            self.layers: List[Layer] = layers
        elif image is not None:
            layer = Layer(name="Layer 1", width=image.width(), height=image.height(), image=image)
            self.layers = [layer]
        else:
            layer = Layer(name="Layer 1", width=width, height=height)
            self.layers = [layer]

    @property
    def active_layer_index(self) -> int:
        if self.project is not None and hasattr(self.project, "_active_layer_index"):
            return self.project._active_layer_index
        return self._active_layer_index

    @active_layer_index.setter
    def active_layer_index(self, index: int) -> None:
        self._active_layer_index = index
        if self.project is not None and hasattr(self.project, "_active_layer_index"):
            self.project._active_layer_index = index

    @property
    def width(self) -> int:
        return self.layers[0].width if self.layers else 0

    @property
    def height(self) -> int:
        return self.layers[0].height if self.layers else 0

    def get_layer_by_track_id(self, track_id: str) -> Optional[Layer]:
        for layer in self.layers:
            if layer.track.id == track_id:
                return layer
        return None

    def get_cel(self, track_id: str) -> Optional[QImage]:
        layer = self.get_layer_by_track_id(track_id)
        return layer.image if layer else None

    def get_active_layer(self) -> Optional[Layer]:
        idx = self.active_layer_index
        if 0 <= idx < len(self.layers):
            return self.layers[idx]
        return self.layers[0] if self.layers else None

    def get_active_layer_image(self) -> QImage:
        layer = self.get_active_layer()
        if layer is None:
            img = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
            img.fill(Qt.GlobalColor.transparent)
            return img
        return layer.image

    def set_active_layer_index(self, index: int) -> None:
        if 0 <= index < len(self.layers):
            self.active_layer_index = index

    def set_layer_image(self, layer_index: int, image: QImage) -> None:
        if 0 <= layer_index < len(self.layers):
            self.layers[layer_index].set_image(image)
            self.mark_modified()

    def get_background_image(self) -> QImage:
        """Return a QImage representing the frame's background."""
        w, h = self.width, self.height
        bg = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        if self.background_color is not None and self.background_color.alpha() > 0:
            bg.fill(self.background_color)
        else:
            bg.fill(Qt.GlobalColor.transparent)

        # If there's an explicit "Background" layer at the bottom, composite it
        if self.layers and self.layers[0].name.lower() == "background" and self.layers[0].visible:
            p = QPainter(bg)
            p.setOpacity(self.layers[0].opacity)
            p.setCompositionMode(self.layers[0].composition_mode())
            p.drawImage(0, 0, self.layers[0].image)
            p.end()

        return bg

    def get_foreground_composite(self) -> QImage:
        """Return composite of all foreground drawing layers (with transparent background)."""
        if self._foreground_composite is not None and not self._composite_dirty:
            return self._foreground_composite

        w, h = self.width, self.height
        fg = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        fg.fill(Qt.GlobalColor.transparent)
        painter = QPainter(fg)

        for layer in self.layers:
            if not layer.visible:
                continue
            if layer.name.lower() == "background":
                continue
            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.composition_mode())
            painter.drawImage(0, 0, layer.image)
        painter.end()

        self._foreground_composite = fg
        return self._foreground_composite

    def get_image(self) -> QImage:
        """Return a cached composite of visible layers (bottom to top)."""
        if self._composite is None or self._composite_dirty:
            self._rebuild_composite()
        return self._composite

    def get_composite_image(self) -> QImage:
        return self.get_image()

    def _rebuild_composite(self) -> None:
        w, h = self.width, self.height
        composite = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        composite.fill(Qt.GlobalColor.transparent)
        painter = QPainter(composite)

        # 1. Base frame background color
        if self.background_color is not None and self.background_color.alpha() > 0:
            painter.fillRect(0, 0, w, h, self.background_color)

        # 2. Layers from bottom to top
        for layer in self.layers:
            if not layer.visible:
                continue
            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.composition_mode())
            painter.drawImage(0, 0, layer.image)
        painter.end()

        self._composite = composite
        self._composite_dirty = False

    def set_image(self, new_image: QImage) -> None:
        """Replace the active layer contents (used by undo of whole-frame snapshots)."""
        layer = self.get_active_layer()
        if layer is None:
            return
        layer.set_image(new_image)
        self.mark_modified()

    def mark_modified(self) -> None:
        self.modified = True
        self._thumbnail_cache = None
        self._composite_dirty = True
        self._composite = None
        self._foreground_composite = None

    def clear(self, color: Optional[QColor] = None) -> None:
        layer = self.get_active_layer()
        if layer is None:
            return
        if color is not None:
            layer.image.fill(color)
        else:
            layer.clear()
        self.mark_modified()

    def add_layer(self, name: Optional[str] = None) -> Layer:
        if self.project is not None and hasattr(self.project, "add_layer"):
            self.project.add_layer(name=name)
            active = self.get_active_layer()
            return active if active is not None else self.layers[-1]
        label = name or f"Layer {len(self.layers) + 1}"
        layer = Layer(name=label, width=self.width, height=self.height)
        self.layers.append(layer)
        self.active_layer_index = len(self.layers) - 1
        self.mark_modified()
        return layer

    def duplicate_active_layer(self) -> Optional[Layer]:
        if self.project is not None and hasattr(self.project, "duplicate_layer"):
            self.project.duplicate_layer(self.active_layer_index)
            return self.get_active_layer()
        src = self.get_active_layer()
        if src is None:
            return None
        cloned = src.clone(keep_track=False)
        cloned.name = f"{src.name} Copy"
        cloned.id = str(uuid.uuid4())
        insert_at = self.active_layer_index + 1
        self.layers.insert(insert_at, cloned)
        self.active_layer_index = insert_at
        self.mark_modified()
        return cloned

    def delete_active_layer(self) -> bool:
        if self.project is not None and hasattr(self.project, "delete_layer"):
            return self.project.delete_layer(self.active_layer_index)
        if len(self.layers) <= 1:
            return False
        active_layer = self.get_active_layer()
        if active_layer and active_layer.locked:
            return False
        self.layers.pop(self.active_layer_index)
        self.active_layer_index = max(0, min(self.active_layer_index, len(self.layers) - 1))
        self.mark_modified()
        return True

    def merge_down(self) -> bool:
        if self.project is not None and hasattr(self.project, "merge_down_layer"):
            return self.project.merge_down_layer(self.active_layer_index)
        idx = self.active_layer_index
        if idx <= 0 or idx >= len(self.layers):
            return False
        upper = self.layers[idx]
        lower = self.layers[idx - 1]
        if upper.locked or lower.locked:
            return False
        painter = QPainter(lower.image)
        painter.setOpacity(upper.opacity)
        painter.setCompositionMode(upper.composition_mode())
        painter.drawImage(0, 0, upper.image)
        painter.end()
        self.layers.pop(idx)
        self.active_layer_index = idx - 1
        self.mark_modified()
        return True

    def move_layer(self, from_index: int, to_index: int) -> bool:
        if self.project is not None and hasattr(self.project, "move_layer"):
            return self.project.move_layer(from_index, to_index)
        if from_index == to_index:
            return False
        if not (0 <= from_index < len(self.layers) and 0 <= to_index < len(self.layers)):
            return False
        if self.layers[from_index].locked:
            return False
        layer = self.layers.pop(from_index)
        self.layers.insert(to_index, layer)
        self.active_layer_index = to_index
        self.mark_modified()
        return True

    def get_thumbnail(self, size: Optional[tuple[int, int]] = None) -> QPixmap:
        """Return a cached thumbnail pixmap scaled from the composite image.

        Preserves the canvas's exact aspect ratio without letterboxing or baking
        in unwanted checkerboard margins.
        """
        target_size = size or self._thumbnail_size
        if self._thumbnail_cache is not None and self._thumbnail_size == target_size:
            return self._thumbnail_cache

        composite = self.get_image()
        if composite.isNull() or composite.width() == 0 or composite.height() == 0:
            thumb = QPixmap(target_size[0], target_size[1])
            thumb.fill(Qt.GlobalColor.transparent)
            self._thumbnail_size = target_size
            self._thumbnail_cache = thumb
            return thumb

        tw, th = target_size
        scaled_img = composite.scaled(
            QSize(tw, th),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_size = target_size
        self._thumbnail_cache = QPixmap.fromImage(scaled_img)
        return self._thumbnail_cache

    def clone(self) -> Frame:
        cloned_layers = [layer.clone(keep_track=True) for layer in self.layers]
        cloned = Frame(
            width=self.width,
            height=self.height,
            layers=cloned_layers,
            background_color=self.background_color,
            project=self.project,
        )
        cloned.name = f"{self.name} Copy" if self.name else None
        cloned._active_layer_index = self._active_layer_index
        cloned.modified = self.modified
        return cloned
