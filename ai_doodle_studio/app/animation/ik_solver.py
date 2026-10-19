"""Analytic Two-Bone Inverse Kinematics (IK) solver and solver interfaces.

Provides pure-math, CPU-based 2D kinematics algorithms independent of any GUI toolkit.
"""

from __future__ import annotations

import math
from typing import Optional, Protocol, Tuple

Point2D = Tuple[float, float]


def solve_two_bone_ik(
    root_position: Point2D,
    target_position: Point2D,
    upper_length: float,
    lower_length: float,
    bend_direction: int = 1,
) -> Tuple[Point2D, Point2D]:
    """Solve analytic 2D two-bone inverse kinematics using the Law of Cosines.

    Args:
        root_position: (x, y) coordinates of the root joint (e.g. shoulder/hip).
        target_position: Desired (x, y) coordinates of the end effector (e.g. hand/foot).
        upper_length: Rest length of the first bone segment (e.g. upper arm/thigh).
        lower_length: Rest length of the second bone segment (e.g. forearm/calf).
        bend_direction: +1 for positive normal bend (e.g. human knee), -1 for opposite bend.

    Returns:
        Tuple of (mid_joint_position, end_effector_position).
        The bone lengths are strictly preserved.
    """
    rx, ry = root_position
    tx, ty = target_position

    # Handle degenerate zero bone lengths safely
    l1 = max(0.001, float(upper_length))
    l2 = max(0.001, float(lower_length))

    dx = tx - rx
    dy = ty - ry
    dist = math.hypot(dx, dy)

    # Base angle from root towards target
    if dist < 1e-6:
        base_angle = 0.0
        dx = 1e-6
        dist = 1e-6
    else:
        base_angle = math.atan2(dy, dx)

    # Clamp distance to reachable range
    max_reach = (l1 + l2) * 0.9999
    min_reach = abs(l1 - l2) * 1.0001
    clamped_dist = max(min_reach, min(max_reach, dist))

    # Law of Cosines for angle at root (alpha) and mid joint (beta)
    # clamped_dist^2 = l1^2 + l2^2 - 2*l1*l2*cos(beta)
    # l2^2 = l1^2 + clamped_dist^2 - 2*l1*clamped_dist*cos(alpha)
    cos_alpha = (l1 * l1 + clamped_dist * clamped_dist - l2 * l2) / (2.0 * l1 * clamped_dist)
    cos_alpha = max(-1.0, min(1.0, cos_alpha))
    alpha = math.acos(cos_alpha)

    # Orientation direction (+1 or -1)
    sign = 1 if bend_direction >= 0 else -1
    theta1 = base_angle + sign * alpha

    # Mid joint position (elbow / knee)
    mid_x = rx + l1 * math.cos(theta1)
    mid_y = ry + l1 * math.sin(theta1)

    # Bone 2: direction from mid joint towards actual target (or clamped end)
    # cos(beta)
    cos_beta = (l1 * l1 + l2 * l2 - clamped_dist * clamped_dist) / (2.0 * l1 * l2)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.acos(cos_beta)

    # Internal bend angle relative to bone 1
    theta2 = theta1 - sign * (math.pi - beta)
    end_x = mid_x + l2 * math.cos(theta2)
    end_y = mid_y + l2 * math.sin(theta2)

    return (mid_x, mid_y), (end_x, end_y)


class IKSolver(Protocol):
    """Protocol extension point for multi-bone solvers such as FABRIK or CCD."""

    def solve(
        self,
        joint_positions: list[Point2D],
        bone_lengths: list[float],
        target: Point2D,
    ) -> list[Point2D]:
        ...
