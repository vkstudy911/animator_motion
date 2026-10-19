"""Timeline model wrapping frame sequences with PySide6 signals.

Provides structured manipulations for timeline operations including
insertions, deletions, duplicates, and order rearrangement.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from app.core.frame import Frame


class TimelineModel(QObject):
    """Data model managing the ordered list of frames for animation timeline."""

    frame_inserted = Signal(int)
    frame_removed = Signal(int)
    frames_reordered = Signal()
    frame_updated = Signal(int)
    timeline_reset = Signal()

    def __init__(self, frames: Optional[List[Frame]] = None, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._frames: List[Frame] = frames if frames is not None else []

    @property
    def frames(self) -> List[Frame]:
        """Return the underlying list of frames."""
        return self._frames

    def set_frames(self, frames: List[Frame]) -> None:
        """Replace all frames in the timeline and notify listeners."""
        self._frames = frames
        self.timeline_reset.emit()

    def frame_count(self) -> int:
        """Return total number of frames."""
        return len(self._frames)

    def get_frame_at(self, index: int) -> Optional[Frame]:
        """Return frame at 0-based index or None if out of bounds."""
        if 0 <= index < len(self._frames):
            return self._frames[index]
        return None

    def insert_frame(self, index: int, frame: Frame) -> int:
        """Insert frame at index (or append if index < 0 or > length).

        Returns:
            The actual index where the frame was inserted.
        """
        if index < 0 or index > len(self._frames):
            index = len(self._frames)
        self._frames.insert(index, frame)
        self.frame_inserted.emit(index)
        return index

    def remove_frame(self, index: int) -> Optional[Frame]:
        """Remove frame at index if index is valid and not the last remaining frame.

        Returns:
            The removed Frame or None if removal not possible.
        """
        if len(self._frames) <= 1:
            return None
        if 0 <= index < len(self._frames):
            removed = self._frames.pop(index)
            self.frame_removed.emit(index)
            return removed
        return None

    def swap_frames(self, index_a: int, index_b: int) -> bool:
        """Swap two frames by their indices."""
        count = len(self._frames)
        if 0 <= index_a < count and 0 <= index_b < count and index_a != index_b:
            self._frames[index_a], self._frames[index_b] = self._frames[index_b], self._frames[index_a]
            self.frames_reordered.emit()
            return True
        return False

    def move_frame(self, from_index: int, to_index: int) -> bool:
        """Move a frame from one position to another."""
        count = len(self._frames)
        if 0 <= from_index < count and 0 <= to_index < count and from_index != to_index:
            frame = self._frames.pop(from_index)
            self._frames.insert(to_index, frame)
            self.frames_reordered.emit()
            return True
        return False

    def duplicate_frame(self, index: int) -> int:
        """Duplicate frame at index, inserting the copy right after it.

        Returns:
            The index of the newly inserted duplicate frame, or -1 on error.
        """
        frame = self.get_frame_at(index)
        if frame is None:
            return -1
        cloned = frame.clone()
        return self.insert_frame(index + 1, cloned)

    def notify_frame_updated(self, index: int) -> None:
        """Emit notification that content of a frame at index was updated."""
        if 0 <= index < len(self._frames):
            self.frame_updated.emit(index)
