"""Brush engine for point smoothing, interpolation, and stroke rendering.

Handles Catmull-Rom / linear point interpolation between mouse events
to deliver smooth, non-segmented freehand brush strokes.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor


class BrushEngine:
    """Manages stroke geometry interpolation and brush styling parameters."""

    def __init__(
        self,
        size: float = 8.0,
        color: QColor = QColor(240, 240, 240, 255),
        opacity: float = 1.0,
        hardness: float = 1.0,
    ) -> None:
        self.size: float = max(1.0, min(200.0, float(size)))
        self.color: QColor = QColor(color)
        self.opacity: float = max(0.0, min(1.0, float(opacity)))
        self.hardness: float = max(0.0, min(1.0, float(hardness)))
        self.default_pressure: float = 1.0

        self._points_history: List[QPointF] = []
        self._pressures: List[float] = []

    def reset_stroke(self) -> None:
        """Clear active stroke points buffer."""
        self._points_history.clear()
        self._pressures.clear()

    def add_point(self, point: QPointF, pressure: float = 1.0) -> List[Tuple[QPointF, float]]:
        """Add a point sample and return newly interpolated sub-points.

        Args:
            point: Canvas image coordinate point.
            pressure: Tablet/stylus pressure factor (0.0 to 1.0).

        Returns:
            List of (QPointF, pressure) points along the smoothed curve.
        """
        press = max(0.05, min(1.0, pressure if pressure > 0 else self.default_pressure))
        self._points_history.append(point)
        self._pressures.append(press)

        num_points = len(self._points_history)
        if num_points == 1:
            return [(point, press)]

        if num_points == 2:
            return self._interpolate_linear(
                self._points_history[0], self._pressures[0],
                self._points_history[1], self._pressures[1],
            )

        # Catmull-Rom spline interpolation using last 4 points or duplicate ends
        p0 = self._points_history[-4] if num_points >= 4 else self._points_history[-3]
        p1 = self._points_history[-3]
        p2 = self._points_history[-2]
        p3 = self._points_history[-1]

        pr1 = self._pressures[-2]
        pr2 = self._pressures[-1]

        return self._interpolate_catmull_rom(p0, p1, p2, p3, pr1, pr2)

    def _interpolate_linear(
        self,
        p1: QPointF,
        press1: float,
        p2: QPointF,
        press2: float,
    ) -> List[Tuple[QPointF, float]]:
        """Linearly interpolate between two points with spacing based on brush size."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        step = max(1.0, self.size * 0.25)
        steps = max(1, int(dist / step))

        results: List[Tuple[QPointF, float]] = []
        for i in range(1, steps + 1):
            t = i / steps
            x = p1.x() + dx * t
            y = p1.y() + dy * t
            pr = press1 + (press2 - press1) * t
            results.append((QPointF(x, y), pr))
        return results

    def _interpolate_catmull_rom(
        self,
        p0: QPointF,
        p1: QPointF,
        p2: QPointF,
        p3: QPointF,
        press1: float,
        press2: float,
    ) -> List[Tuple[QPointF, float]]:
        """Interpolate segment between p1 and p2 using Catmull-Rom cubic spline."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        dist = math.hypot(dx, dy)
        step = max(1.0, self.size * 0.25)
        steps = max(1, int(dist / step))

        results: List[Tuple[QPointF, float]] = []
        for i in range(1, steps + 1):
            t = i / steps
            t2 = t * t
            t3 = t2 * t

            # Standard Catmull-Rom basis matrix evaluation
            x = 0.5 * (
                (2 * p1.x())
                + (-p0.x() + p2.x()) * t
                + (2 * p0.x() - 5 * p1.x() + 4 * p2.x() - p3.x()) * t2
                + (-p0.x() + 3 * p1.x() - 3 * p2.x() + p3.x()) * t3
            )
            y = 0.5 * (
                (2 * p1.y())
                + (-p0.y() + p2.y()) * t
                + (2 * p0.y() - 5 * p1.y() + 4 * p2.y() - p3.y()) * t2
                + (-p0.y() + 3 * p1.y() - 3 * p2.y() + p3.y()) * t3
            )
            pr = press1 + (press2 - press1) * t
            results.append((QPointF(x, y), pr))

        return results

    def get_effective_color(self) -> QColor:
        """Return the brush color modified with current opacity."""
        col = QColor(self.color)
        col.setAlphaF(col.alphaF() * self.opacity)
        return col
