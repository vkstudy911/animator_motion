"""Keyframe representation and pose interpolation algorithms.

Provides smooth keyframe interpolation between poses while preserving
connected bone lengths and offering linear/smooth blending.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.models.skeleton import Skeleton

Point2D = Tuple[float, float]


@dataclass
class PoseKeyframe:
    """Snapshot of joint positions at a specific animation frame index."""

    frame_index: int
    joint_positions: Dict[str, Point2D]  # joint_id -> (x, y)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "joint_positions": {
                jid: [round(pos[0], 3), round(pos[1], 3)]
                for jid, pos in self.joint_positions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PoseKeyframe:
        raw_positions = data.get("joint_positions", {})
        pos_dict = {
            jid: (float(coords[0]), float(coords[1]))
            for jid, coords in raw_positions.items()
        }
        return cls(frame_index=int(data["frame_index"]), joint_positions=pos_dict)


def smooth_step(t: float) -> float:
    """Cubic smoothstep ease-in/ease-out curve: 3*t^2 - 2*t^3."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def interpolate_pose(
    pose_a: Dict[str, Point2D],
    pose_b: Dict[str, Point2D],
    t: float,
    skeleton: Optional[Skeleton] = None,
    ease: bool = True,
) -> Dict[str, Point2D]:
    """Interpolate between two joint pose dictionaries.

    If a skeleton with rest lengths is provided, enforces bone length
    preservation from parents to children to prevent limb stretching.
    """
    alpha = smooth_step(t) if ease else max(0.0, min(1.0, t))
    result: Dict[str, Point2D] = {}

    all_keys = set(pose_a.keys()).union(pose_b.keys())
    for jid in all_keys:
        pa = pose_a.get(jid)
        pb = pose_b.get(jid)
        if pa and pb:
            ix = pa[0] + (pb[0] - pa[0]) * alpha
            iy = pa[1] + (pb[1] - pa[1]) * alpha
            result[jid] = (ix, iy)
        elif pa:
            result[jid] = pa
        elif pb:
            result[jid] = pb

    # If skeleton provided, correct bone lengths from roots downwards
    if skeleton:
        roots = skeleton.get_roots()
        queue = list(roots)
        while queue:
            curr = queue.pop(0)
            if curr.id in result:
                cx, cy = result[curr.id]
                for child in skeleton.get_children(curr.id):
                    if child.id in result and child.rest_length > 0:
                        chx, chy = result[child.id]
                        dx = chx - cx
                        dy = chy - cy
                        dist = math.hypot(dx, dy)
                        if dist > 1e-4:
                            scale = child.rest_length / dist
                            result[child.id] = (cx + dx * scale, cy + dy * scale)
                    queue.append(child)

    return result


class SkeletonAnimation:
    """Manages ordered keyframes and evaluates interpolated poses across the timeline."""

    def __init__(self, fps: int = 24) -> None:
        self.fps: int = fps
        self.keyframes: Dict[int, PoseKeyframe] = {}

    def set_keyframe(self, frame_index: int, skeleton: Skeleton) -> PoseKeyframe:
        """Capture current skeleton joint positions as a keyframe at frame_index."""
        positions = {jid: (j.x, j.y) for jid, j in skeleton.joints.items()}
        kf = PoseKeyframe(frame_index=frame_index, joint_positions=positions)
        self.keyframes[frame_index] = kf
        return kf

    def remove_keyframe(self, frame_index: int) -> bool:
        """Remove keyframe at frame_index if present."""
        if frame_index in self.keyframes:
            del self.keyframes[frame_index]
            return True
        return False

    def has_keyframe(self, frame_index: int) -> bool:
        return frame_index in self.keyframes

    def get_keyframe_indices(self) -> List[int]:
        return sorted(self.keyframes.keys())

    def evaluate(self, frame_index: float, skeleton: Optional[Skeleton] = None) -> Optional[Dict[str, Point2D]]:
        """Evaluate joint positions at arbitrary float frame_index with interpolation."""
        if not self.keyframes:
            return None

        indices = self.get_keyframe_indices()
        int_frame = int(round(frame_index))

        # Exact match or before first keyframe
        if frame_index <= indices[0]:
            return self.keyframes[indices[0]].joint_positions

        # After last keyframe
        if frame_index >= indices[-1]:
            return self.keyframes[indices[-1]].joint_positions

        # Find surrounding keyframes
        prev_idx = indices[0]
        next_idx = indices[-1]
        for idx in indices:
            if idx <= frame_index:
                prev_idx = idx
            if idx >= frame_index:
                next_idx = idx
                break

        if prev_idx == next_idx:
            return self.keyframes[prev_idx].joint_positions

        t = (frame_index - prev_idx) / float(next_idx - prev_idx)
        return interpolate_pose(
            self.keyframes[prev_idx].joint_positions,
            self.keyframes[next_idx].joint_positions,
            t,
            skeleton=skeleton,
            ease=True,
        )

    def apply_to_skeleton(self, frame_index: float, skeleton: Skeleton) -> None:
        """Evaluate pose at frame_index and update skeleton joints in-place."""
        pose = self.evaluate(frame_index, skeleton=skeleton)
        if pose:
            for jid, (x, y) in pose.items():
                if jid in skeleton.joints:
                    skeleton.joints[jid].x = x
                    skeleton.joints[jid].y = y
            skeleton.rebuild_bones()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fps": self.fps,
            "keyframes": [kf.to_dict() for kf in sorted(self.keyframes.values(), key=lambda k: k.frame_index)],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkeletonAnimation:
        anim = cls(fps=int(data.get("fps", 24)))
        for k_data in data.get("keyframes", []):
            kf = PoseKeyframe.from_dict(k_data)
            anim.keyframes[kf.frame_index] = kf
        return anim
