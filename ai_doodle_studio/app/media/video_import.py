"""Video frame extraction utilities for AI Doodle Studio.

Supports importing video clips as animation frames using OpenCV when available,
handling missing dependencies gracefully.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter

from app.core.frame import Frame

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def is_opencv_available() -> bool:
    """Return whether OpenCV is installed in current Python environment."""
    return OPENCV_AVAILABLE


def import_video_frames(
    video_path: str,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    max_frames: Optional[int] = 300,
    sample_every_n: int = 1,
) -> Tuple[List[Frame], Optional[str]]:
    """Extract frames from video and return as a sequence of Frame objects.

    Args:
        video_path: Path to video file.
        canvas_width: Target canvas width.
        canvas_height: Target canvas height.
        max_frames: Maximum number of frames to import (avoids memory exhaustion).
        sample_every_n: Stride to subsample video frames.

    Returns:
        Tuple of (frames_list, error_message).
    """
    if not OPENCV_AVAILABLE:
        return (
            [],
            "OpenCV is not installed in the environment. Run 'pip install opencv-python' to enable video import.",
        )

    if not os.path.exists(video_path):
        return [], f"Video file not found: {video_path}"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], f"Could not open video file: {video_path}"

    frames: List[Frame] = []
    frame_count = 0
    sampled_count = 0

    try:
        while True:
            ret, cv_frame = cap.read()
            if not ret:
                break

            if frame_count % sample_every_n == 0:
                # Convert BGR (OpenCV) to RGB
                rgb_frame = cv2.cvtColor(cv_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_frame.shape
                bytes_per_line = ch * w

                # Construct QImage from NumPy array buffer
                qimg = QImage(
                    rgb_frame.data,
                    w,
                    h,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,
                ).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)

                # Fit into canvas
                canvas_img = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
                canvas_img.fill(Qt.GlobalColor.transparent)

                p = QPainter(canvas_img)
                scaled = qimg.scaled(
                    QSize(canvas_width, canvas_height),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                ox = (canvas_width - scaled.width()) // 2
                oy = (canvas_height - scaled.height()) // 2
                p.drawImage(ox, oy, scaled)
                p.end()

                frames.append(Frame(width=canvas_width, height=canvas_height, image=canvas_img))
                sampled_count += 1
                if max_frames and sampled_count >= max_frames:
                    break

            frame_count += 1

    finally:
        cap.release()

    return frames, None
