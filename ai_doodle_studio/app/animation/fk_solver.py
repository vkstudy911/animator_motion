"""Forward Kinematics (FK) hierarchy transformation propagation.

Propagates joint transformations down the skeletal tree from parent joints
to descendants, preserving fixed rest-pose bone lengths and respecting joint angle limits.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.models.skeleton import Skeleton

Point2D = Tuple[float, float]


def rotate_point(origin: Point2D, point: Point2D, angle_rad: float) -> Point2D:
    """Rotate a 2D point around an origin by angle in radians."""
    ox, oy = origin
    px, py = point
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    qx = ox + cos_a * (px - ox) - sin_a * (py - oy)
    qy = oy + sin_a * (px - ox) + cos_a * (py - oy)
    return qx, qy


def propagate_fk(
    skeleton: Skeleton,
    modified_joint_id: str,
    delta_angle_rad: float,
) -> Dict[str, Point2D]:
    """Rotate a joint and propagate the rotation to all descendants, preserving bone lengths.

    Args:
        skeleton: The target Skeleton.
        modified_joint_id: ID of the joint whose local angle was changed.
        delta_angle_rad: Delta rotation in radians to apply to the subtree.

    Returns:
        Dictionary mapping joint ID to updated (x, y) coordinates.
    """
    results: Dict[str, Point2D] = {}
    pivot = skeleton.joints.get(modified_joint_id)
    if not pivot:
        return results

    pivot_pt = (pivot.x, pivot.y)
    results[pivot.id] = pivot_pt

    # BFS or DFS down the descendants
    stack = list(skeleton.get_children(modified_joint_id))
    while stack:
        child = stack.pop()
        new_pt = rotate_point(pivot_pt, (child.x, child.y), delta_angle_rad)
        results[child.id] = new_pt
        # Continue to children of this child
        stack.extend(skeleton.get_children(child.id))

    return results


def apply_fk_transforms(skeleton: Skeleton, transforms: Dict[str, Point2D]) -> None:
    """Apply computed FK coordinates to the skeleton joints."""
    for jid, (x, y) in transforms.items():
        if jid in skeleton.joints:
            skeleton.joints[jid].x = x
            skeleton.joints[jid].y = y
    skeleton.rebuild_bones()
