"""Video, GIF, and sequence export engine for AI Doodle Studio.

Supports direct FFmpeg streaming pipeline for MP4, Pillow fallback for animated GIF,
and PNG frame sequence export with non-blocking QThread execution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QThread, Signal
from PySide6.QtGui import QImage

from app.core.frame import Frame

try:
    from PIL import Image as PILImage
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is available on system PATH."""
    return shutil.which("ffmpeg") is not None


def is_pillow_available() -> bool:
    """Check if Pillow library is available."""
    return PILLOW_AVAILABLE


class ExportWorker(QThread):
    """Background worker thread executing video or image sequence export."""

    progress = Signal(int)  # 0 to 100 percentage
    finished = Signal(bool, str)  # (success, message)

    def __init__(
        self,
        frames: List[Frame],
        output_path: str,
        fps: int = 12,
        width: int = 1280,
        height: int = 720,
        export_format: str = "mp4",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        # Deep clone frames to avoid threading races with user drawing
        self.frames = [f.clone() for f in frames]
        self.output_path = output_path
        self.fps = max(1, fps)
        self.width = width
        self.height = height
        self.export_format = export_format.lower()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        """Worker thread entry point."""
        if not self.frames:
            self.finished.emit(False, "No frames to export.")
            return

        try:
            if self.export_format == "mp4":
                self._export_mp4()
            elif self.export_format == "gif":
                self._export_gif()
            elif self.export_format in ("png", "sequence"):
                self._export_sequence()
            else:
                self.finished.emit(False, f"Unsupported export format: {self.export_format}")
        except Exception as exc:
            self.finished.emit(False, f"Export error: {str(exc)}")

    def _export_mp4(self) -> None:
        """Export frames to MP4 using FFmpeg rawvideo pipe."""
        if not is_ffmpeg_available():
            self.finished.emit(
                False,
                "FFmpeg is not installed or not found on PATH. Please install FFmpeg or export as GIF/PNG sequence.",
            )
            return

        # Ensure width and height are even numbers for H.264
        w = self.width if self.width % 2 == 0 else self.width + 1
        h = self.height if self.height % 2 == 0 else self.height + 1

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-pix_fmt", "rgba",
            "-r", str(self.fps),
            "-i", "-",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            self.output_path,
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        total = len(self.frames)
        for i, frame in enumerate(self.frames):
            if self._cancelled:
                proc.kill()
                self.finished.emit(False, "Export cancelled by user.")
                return
            img = frame.get_image()
            if img.width() != w or img.height() != h:
                img = img.scaled(w, h)
            rgba_img = img.convertToFormat(QImage.Format.Format_RGBA8888)
            raw_bytes = bytes(rgba_img.constBits()[: rgba_img.sizeInBytes()])
            proc.stdin.write(raw_bytes)
            self.progress.emit(int((i + 1) / total * 100))

        proc.stdin.close()
        stderr_output = proc.stderr.read()
        proc.wait()

        if proc.returncode == 0:
            self.finished.emit(True, f"Video exported successfully to {self.output_path}")
        else:
            self.finished.emit(False, f"FFmpeg error: {stderr_output.decode('utf-8', errors='ignore')}")

    def _export_gif(self) -> None:
        """Export frames to animated GIF using Pillow."""
        if not PILLOW_AVAILABLE:
            self.finished.emit(False, "Pillow is not installed. Run 'pip install Pillow' to export GIF.")
            return

        pil_frames = []
        total = len(self.frames)

        for i, frame in enumerate(self.frames):
            if self._cancelled:
                self.finished.emit(False, "Export cancelled by user.")
                return
            img = frame.get_image()
            rgba_img = img.convertToFormat(QImage.Format.Format_RGBA8888)
            raw_bytes = bytes(rgba_img.constBits()[: rgba_img.sizeInBytes()])
            pil_img = PILImage.frombytes("RGBA", (rgba_img.width(), rgba_img.height()), raw_bytes)
            pil_frames.append(pil_img)
            self.progress.emit(int((i + 1) / (total * 2) * 100))

        duration_ms = max(10, int(1000.0 / self.fps))
        first_frame = pil_frames[0]
        first_frame.save(
            self.output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration_ms,
            loop=0,
            disposal=2,
            optimize=True,
        )
        self.progress.emit(100)
        self.finished.emit(True, f"GIF animation exported successfully to {self.output_path}")

    def _export_sequence(self) -> None:
        """Export frames as individual PNG files in a folder."""
        folder = self.output_path
        os.makedirs(folder, exist_ok=True)
        total = len(self.frames)

        for i, frame in enumerate(self.frames):
            if self._cancelled:
                self.finished.emit(False, "Export cancelled by user.")
                return
            filename = os.path.join(folder, f"frame_{i:05d}.png")
            frame.get_image().save(filename, "PNG")
            self.progress.emit(int((i + 1) / total * 100))

        self.finished.emit(True, f"Exported {total} PNG frames to {folder}")


class VideoExporter(QObject):
    """Facade for exporting animation sequences with asynchronous status callbacks."""

    progress = Signal(int)
    finished = Signal(bool, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._worker: Optional[ExportWorker] = None

    def cancel(self) -> None:
        """Cancel running export worker."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()

    def export(
        self,
        frames: List[Frame],
        output_path: str,
        fps: int = 12,
        width: int = 1280,
        height: int = 720,
        export_format: str = "mp4",
    ) -> bool:
        """Initiate background export of frames."""
        if self._worker is not None and self._worker.isRunning():
            return False

        self._worker = ExportWorker(
            frames=frames,
            output_path=output_path,
            fps=fps,
            width=width,
            height=height,
            export_format=export_format,
            parent=self,
        )
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self.finished)
        self._worker.start()
        return True

    def export_sync(
        self,
        frames: List[Frame],
        output_path: str,
        fps: int = 12,
        width: int = 1280,
        height: int = 720,
        export_format: str = "mp4",
    ) -> bool:
        """Synchronously export frames without spawning a thread."""
        worker = ExportWorker(
            frames=frames,
            output_path=output_path,
            fps=fps,
            width=width,
            height=height,
            export_format=export_format,
        )
        worker.run()
        return True
