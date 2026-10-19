"""Image analysis and foreground bounding-box estimation for assisted rigging.

Uses Qt's QImage for pure-CPU pixel bounding box analysis, with an optional
OpenCV acceleration fallback when cv2 is installed in the environment.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage

try:
    import cv2  # Optional OpenCV integration
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


Bounds = Tuple[float, float, float, float]  # (min_x, min_y, width, height)


def estimate_image_foreground_bounds(
    image: QImage,
    canvas_origin: Tuple[float, float] = (0.0, 0.0),
    scale: float = 1.0,
) -> Optional[Bounds]:
    """Estimate character foreground bounding box from a QImage.

    Inspects the alpha channel (if transparent background) or luminance
    contrast against the edge background color.

    Returns:
        (min_x, min_y, width, height) in canvas space, or None if empty.
    """
    if image.isNull() or image.width() <= 0 or image.height() <= 0:
        return None

    w = image.width()
    h = image.height()

    # Fast OpenCV contour path if available
    if OPENCV_AVAILABLE:
        try:
            converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
            ptr = converted.constBits()
            arr = np.array(ptr, dtype=np.uint8).reshape((h, w, 4))

            # Alpha channel check
            alpha = arr[:, :, 3]
            if np.any(alpha < 240):  # Has transparent areas
                mask = (alpha > 20).astype(np.uint8) * 255
            else:
                # Luminance difference from corner sample
                gray = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2GRAY)
                corner_val = float(gray[0, 0])
                diff = np.abs(gray.astype(np.float32) - corner_val)
                mask = (diff > 25.0).astype(np.uint8) * 255

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest = max(contours, key=cv2.contourArea)
                bx, by, bw, bh = cv2.boundingRect(largest)
                if bw > 10 and bh > 10:
                    ox, oy = canvas_origin
                    return (ox + bx * scale, oy + by * scale, bw * scale, bh * scale)
        except Exception:
            pass  # Fall through to pure Qt algorithm

    # Pure Qt algorithm (zero external dependencies)
    converted = image.convertToFormat(QImage.Format.Format_ARGB32)
    has_alpha = converted.hasAlphaChannel()
    corner_color = QColor(converted.pixelColor(0, 0))

    min_x, max_x = w, 0
    min_y, max_y = h, 0
    found_any = False

    # Sample rows/cols in steps of 4 for speed on high-res images
    step = max(1, min(w, h) // 256)
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = converted.pixelColor(x, y)
            is_foreground = False
            if has_alpha:
                is_foreground = (c.alpha() > 25)
            else:
                diff = abs(c.red() - corner_color.red()) + abs(c.green() - corner_color.green()) + abs(c.blue() - corner_color.blue())
                is_foreground = (diff > 45)

            if is_foreground:
                found_any = True
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y

    if not found_any or max_x <= min_x or max_y <= min_y:
        # Default fallback to center 80% of image
        ox, oy = canvas_origin
        return (ox + w * 0.1 * scale, oy + h * 0.1 * scale, w * 0.8 * scale, h * 0.8 * scale)

    bw = (max_x - min_x)
    bh = (max_y - min_y)
    ox, oy = canvas_origin
    return (ox + min_x * scale, oy + min_y * scale, bw * scale, bh * scale)
