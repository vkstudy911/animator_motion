"""Animation playback controller using high-precision QTimer.

Supports configurable FPS, multiple playback loop modes (loop, once, ping-pong),
and frame-stepping controls.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Optional, Union

from PySide6.QtCore import QObject, Qt, QTimer, Signal


class LoopMode(Enum):
    """Playback loop repetition policies."""

    LOOP = auto()
    ONCE = auto()
    PING_PONG = auto()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            clean = other.lower().replace("-", "_").strip()
            return self.name.lower() == clean
        return super().__eq__(other)


class PlaybackController(QObject):
    """Timer-driven playback coordinator for animation timeline."""

    frame_changed = Signal(int)
    playback_started = Signal()
    playback_stopped = Signal()
    fps_changed = Signal(int)

    def __init__(self, fps: int = 12, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._fps: int = max(1, min(60, fps))
        self._loop_mode: LoopMode = LoopMode.LOOP
        self._current_frame: int = 0
        self._total_frames: int = 1
        self._is_playing: bool = False
        self._ping_pong_direction: int = 1  # 1 for forward, -1 for backward

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timer_tick)
        self._update_timer_interval()

    # ---------------- Properties ----------------

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def fps(self) -> int:
        return self._fps

    @property
    def current_frame(self) -> int:
        return self._current_frame

    @property
    def loop_mode(self) -> LoopMode:
        return self._loop_mode

    # ---------------- Configuration ----------------

    def set_fps(self, fps: int) -> None:
        """Set animation playback speed (frames per second)."""
        fps_clamped = max(1, min(60, fps))
        if self._fps != fps_clamped:
            self._fps = fps_clamped
            self._update_timer_interval()
            self.fps_changed.emit(self._fps)

    def set_loop_mode(self, mode: Union[LoopMode, str]) -> None:
        """Change loop mode. Accepts LoopMode enum or string ('loop', 'once', 'ping_pong', 'ping-pong')."""
        if isinstance(mode, LoopMode):
            self._loop_mode = mode
        elif isinstance(mode, str):
            clean = mode.lower().replace("-", "_").strip()
            if clean == "loop":
                self._loop_mode = LoopMode.LOOP
            elif clean == "once":
                self._loop_mode = LoopMode.ONCE
            elif clean in ("ping_pong", "pingpong"):
                self._loop_mode = LoopMode.PING_PONG
            else:
                self._loop_mode = LoopMode.LOOP
        else:
            self._loop_mode = LoopMode.LOOP

    def set_total_frames(self, total: int) -> None:
        """Update total frame count known to playback controller."""
        self._total_frames = max(1, total)
        if self._current_frame >= self._total_frames:
            self._current_frame = self._total_frames - 1

    def set_current_frame(self, index: int) -> None:
        """Explicitly set current playback frame position."""
        if self._total_frames > 0:
            self._current_frame = max(0, min(self._total_frames - 1, index))

    # ---------------- Playback Actions ----------------

    def play(self) -> None:
        """Start animation playback."""
        if not self._is_playing and self._total_frames > 0:
            self._is_playing = True
            self._update_timer_interval()
            self._timer.start()
            self.playback_started.emit()

    def pause(self) -> None:
        """Pause animation playback at current frame."""
        if self._is_playing:
            self._is_playing = False
            self._timer.stop()
            self.playback_stopped.emit()

    def stop(self) -> None:
        """Stop animation and rewind to beginning."""
        self.pause()
        self._current_frame = 0
        self._ping_pong_direction = 1
        self.frame_changed.emit(self._current_frame)

    def toggle(self) -> None:
        """Toggle between play and pause."""
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def step_forward(self) -> int:
        """Advance one frame forward."""
        if self._total_frames <= 0:
            return 0
        self._current_frame = (self._current_frame + 1) % self._total_frames
        self.frame_changed.emit(self._current_frame)
        return self._current_frame

    def step_backward(self) -> int:
        """Step one frame backward."""
        if self._total_frames <= 0:
            return 0
        self._current_frame = (self._current_frame - 1 + self._total_frames) % self._total_frames
        self.frame_changed.emit(self._current_frame)
        return self._current_frame

    def go_to_first(self) -> int:
        """Jump to the first frame."""
        self._current_frame = 0
        self.frame_changed.emit(self._current_frame)
        return self._current_frame

    def go_to_last(self) -> int:
        """Jump to the final frame."""
        if self._total_frames > 0:
            self._current_frame = self._total_frames - 1
            self.frame_changed.emit(self._current_frame)
        return self._current_frame

    # ---------------- Internal Timer Tick ----------------

    def _update_timer_interval(self) -> None:
        """Recalculate timer millisecond interval from FPS."""
        interval_ms = max(1, int(1000.0 / self._fps))
        self._timer.setInterval(interval_ms)

    def _on_timer_tick(self) -> None:
        """Advance playback state by one frame interval."""
        if self._total_frames <= 1:
            return

        if self._loop_mode == LoopMode.LOOP:
            self._current_frame = (self._current_frame + 1) % self._total_frames
        elif self._loop_mode == LoopMode.ONCE:
            if self._current_frame + 1 >= self._total_frames:
                self.pause()
                return
            self._current_frame += 1
        elif self._loop_mode == LoopMode.PING_PONG:
            next_idx = self._current_frame + self._ping_pong_direction
            if next_idx >= self._total_frames:
                self._ping_pong_direction = -1
                next_idx = self._total_frames - 2
            elif next_idx < 0:
                self._ping_pong_direction = 1
                next_idx = 1
            self._current_frame = max(0, min(self._total_frames - 1, next_idx))

        self.frame_changed.emit(self._current_frame)
