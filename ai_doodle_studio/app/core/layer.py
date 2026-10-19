"""Layer data model for AI Doodle Studio.

Each layer owns an independent raster buffer plus visibility, lock,
opacity, and blend-mode metadata.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtCore import Qt


BLEND_MODES = ("normal", "multiply", "screen", "overlay")

_BLEND_MAP = {
    "normal": QPainter.CompositionMode.CompositionMode_SourceOver,
    "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
    "screen": QPainter.CompositionMode.CompositionMode_Screen,
    "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
}


class LayerTrack:
    """Timeline-wide layer track owning metadata shared across all frames."""

    def __init__(
        self,
        name: str = "Layer 1",
        visible: bool = True,
        opacity: float = 1.0,
        locked: bool = False,
        blend_mode: str = "normal",
        track_id: Optional[str] = None,
    ) -> None:
        self.id: str = track_id or str(uuid.uuid4())
        self.name: str = name
        self.visible: bool = visible
        self.opacity: float = max(0.0, min(1.0, opacity))
        self.locked: bool = locked
        self.blend_mode: str = blend_mode if blend_mode in BLEND_MODES else "normal"

    def composition_mode(self) -> QPainter.CompositionMode:
        return _BLEND_MAP.get(self.blend_mode, QPainter.CompositionMode.CompositionMode_SourceOver)

    def clone(self) -> LayerTrack:
        return LayerTrack(
            name=self.name,
            visible=self.visible,
            opacity=self.opacity,
            locked=self.locked,
            blend_mode=self.blend_mode,
            track_id=str(uuid.uuid4()),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "opacity": self.opacity,
            "locked": self.locked,
            "blend_mode": self.blend_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LayerTrack:
        return cls(
            name=data.get("name", "Layer 1"),
            visible=data.get("visible", True),
            opacity=data.get("opacity", 1.0),
            locked=data.get("locked", False),
            blend_mode=data.get("blend_mode", "normal"),
            track_id=data.get("id"),
        )


class Layer:
    """A frame cel / drawing layer.

    Metadata (name, visibility, opacity, lock, blend mode) is delegated to an
    associated LayerTrack, while the raster image buffer is unique to this frame cel.
    """

    def __init__(
        self,
        name: str = "Layer 1",
        width: int = 1280,
        height: int = 720,
        visible: bool = True,
        opacity: float = 1.0,
        locked: bool = False,
        blend_mode: str = "normal",
        layer_id: Optional[str] = None,
        image: Optional[QImage] = None,
        track: Optional[LayerTrack] = None,
    ) -> None:
        if track is not None:
            self.track: LayerTrack = track
        else:
            self.track = LayerTrack(
                name=name,
                visible=visible,
                opacity=opacity,
                locked=locked,
                blend_mode=blend_mode,
                track_id=layer_id,
            )

        if image is not None:
            if image.format() != QImage.Format.Format_ARGB32_Premultiplied:
                self.image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            else:
                self.image = image.copy()
        else:
            self.image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            self.image.fill(QColor(0, 0, 0, 0))

    @property
    def id(self) -> str:
        return self.track.id

    @id.setter
    def id(self, val: str) -> None:
        self.track.id = val

    @property
    def name(self) -> str:
        return self.track.name

    @name.setter
    def name(self, val: str) -> None:
        self.track.name = val

    @property
    def visible(self) -> bool:
        return self.track.visible

    @visible.setter
    def visible(self, val: bool) -> None:
        self.track.visible = val

    @property
    def opacity(self) -> float:
        return self.track.opacity

    @opacity.setter
    def opacity(self, val: float) -> None:
        self.track.opacity = max(0.0, min(1.0, val))

    @property
    def locked(self) -> bool:
        return self.track.locked

    @locked.setter
    def locked(self, val: bool) -> None:
        self.track.locked = val

    @property
    def blend_mode(self) -> str:
        return self.track.blend_mode

    @blend_mode.setter
    def blend_mode(self, val: str) -> None:
        self.track.blend_mode = val if val in BLEND_MODES else "normal"

    @property
    def width(self) -> int:
        return self.image.width()

    @property
    def height(self) -> int:
        return self.image.height()

    def composition_mode(self) -> QPainter.CompositionMode:
        return self.track.composition_mode()

    def is_empty(self) -> bool:
        """Return True if image buffer is null, zero-sized, or entirely transparent."""
        if self.image.isNull() or self.image.width() == 0 or self.image.height() == 0:
            return True
        try:
            return not any(memoryview(self.image.constBits())[: self.image.sizeInBytes()])
        except Exception:
            return False

    def clear(self) -> None:
        self.image.fill(Qt.GlobalColor.transparent)

    def set_image(self, new_image: QImage) -> None:
        if new_image.format() != QImage.Format.Format_ARGB32_Premultiplied:
            self.image = new_image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        else:
            self.image = new_image.copy()

    def clone(self, keep_track: bool = True) -> Layer:
        """Clone this cel.

        If keep_track is True (the default for duplicating frames), the clone
        references the same global LayerTrack.
        """
        track = self.track if keep_track else self.track.clone()
        return Layer(
            width=self.width,
            height=self.height,
            image=self.image.copy(),
            track=track,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = self.track.to_dict()
        d["track_id"] = self.track.id
        return d

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        width: int,
        height: int,
        image: Optional[QImage] = None,
        track: Optional[LayerTrack] = None,
    ) -> Layer:
        if track is None:
            track = LayerTrack.from_dict(data)
        return cls(
            width=width,
            height=height,
            image=image,
            track=track,
        )

