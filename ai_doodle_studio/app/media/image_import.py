"""Image import utilities for AI Doodle Studio.

Supports single image loading, image sequence batch loading, and scaling
to match animation canvas dimensions with alpha preservation.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from app.core.frame import Frame

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def load_image_as_frame(
    file_path: str,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    fit_mode: str = "contain",
) -> Optional[Frame]:
    """Load an image file and conform it to canvas dimensions as a Frame.

    Args:
        file_path: Path to image on filesystem.
        canvas_width: Desired canvas width.
        canvas_height: Desired canvas height.
        fit_mode: 'contain' (keeps aspect ratio with transparent borders) or 'stretch'.

    Returns:
        Frame object or None if loading failed.
    """
    if not os.path.exists(file_path):
        return None

    src_img = QImage(file_path)
    if src_img.isNull():
        return None

    dest_img = QImage(canvas_width, canvas_height, QImage.Format.Format_ARGB32_Premultiplied)
    dest_img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(dest_img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    if fit_mode == "contain":
        scaled = src_img.scaled(
            QSize(canvas_width, canvas_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (canvas_width - scaled.width()) // 2
        oy = (canvas_height - scaled.height()) // 2
        painter.drawImage(ox, oy, scaled)
    else:
        scaled = src_img.scaled(
            QSize(canvas_width, canvas_height),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawImage(0, 0, scaled)

    painter.end()
    return Frame(width=canvas_width, height=canvas_height, image=dest_img)


def load_image_sequence(
    folder_path: str,
    canvas_width: int = 1280,
    canvas_height: int = 720,
) -> List[Frame]:
    """Scan directory for ordered image files and load each as a Frame.

    Args:
        folder_path: Folder containing sequence files (e.g. frame_001.png, frame_002.png).
        canvas_width: Target canvas width.
        canvas_height: Target canvas height.

    Returns:
        List of Frame objects sorted alphabetically by filename.
    """
    if not os.path.isdir(folder_path):
        return []

    filenames = [
        f for f in os.listdir(folder_path)
        if os.path.splitext(f.lower())[1] in SUPPORTED_IMAGE_EXTENSIONS
    ]
    filenames.sort()

    frames: List[Frame] = []
    for fname in filenames:
        fpath = os.path.join(folder_path, fname)
        frame = load_image_as_frame(fpath, canvas_width, canvas_height)
        if frame is not None:
            frames.append(frame)

    return frames
