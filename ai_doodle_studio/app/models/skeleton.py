"""Skeletal rigging data models and hierarchy validation for AI Doodle Studio.

Provides Joint, Bone, Skeleton, and validation utilities with stable identifiers,
parent-child relationships, rest lengths, constraints, and hierarchy cycle detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class Joint:
    """Represents an articulated joint node in a 2D skeletal rig."""

    id: str
    name: str
    x: float  # Absolute pixel coordinate on character canvas
    y: float
    parent_id: Optional[str] = None
    rest_length: float = 0.0
    min_angle_deg: float = -180.0
    max_angle_deg: float = 180.0
    is_ik_end_effector: bool = False
    ik_bend_direction: int = 1  # +1 or -1 for elbow/knee bend orientation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "parent_id": self.parent_id,
            "rest_length": round(self.rest_length, 3),
            "min_angle_deg": round(self.min_angle_deg, 2),
            "max_angle_deg": round(self.max_angle_deg, 2),
            "is_ik_end_effector": self.is_ik_end_effector,
            "ik_bend_direction": self.ik_bend_direction,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Joint:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", data["id"])),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            parent_id=data.get("parent_id"),
            rest_length=float(data.get("rest_length", 0.0)),
            min_angle_deg=float(data.get("min_angle_deg", -180.0)),
            max_angle_deg=float(data.get("max_angle_deg", 180.0)),
            is_ik_end_effector=bool(data.get("is_ik_end_effector", False)),
            ik_bend_direction=int(data.get("ik_bend_direction", 1)),
        )


@dataclass
class Bone:
    """A structural segment connecting a parent joint to a child joint."""

    id: str
    parent_joint_id: str
    child_joint_id: str
    rest_length: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "parent_joint_id": self.parent_joint_id,
            "child_joint_id": self.child_joint_id,
            "rest_length": round(self.rest_length, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Bone:
        return cls(
            id=str(data["id"]),
            parent_joint_id=str(data["parent_joint_id"]),
            child_joint_id=str(data["child_joint_id"]),
            rest_length=float(data.get("rest_length", 0.0)),
        )


class HierarchyValidationError(ValueError):
    """Raised when skeleton joint or bone references violate hierarchy integrity."""
    pass


class Skeleton:
    """Complete 2D skeletal rig with hierarchy graph, bones, and rest-pose calculations."""

    def __init__(self, name: str = "CharacterRig") -> None:
        self.name: str = name
        self.joints: Dict[str, Joint] = {}
        self.bones: List[Bone] = []
        self._next_joint_id: int = 1

    def add_joint(
        self,
        name: str,
        x: float,
        y: float,
        parent_id: Optional[str] = None,
        joint_id: Optional[str] = None,
        is_ik_end_effector: bool = False,
        ik_bend_direction: int = 1,
    ) -> Joint:
        """Add a joint to the skeleton and automatically construct bone to parent."""
        if joint_id is None:
            joint_id = f"joint_{self._next_joint_id}"
            self._next_joint_id += 1
        elif joint_id in self.joints:
            raise HierarchyValidationError(f"Duplicate joint ID '{joint_id}'")

        if parent_id is not None and parent_id not in self.joints:
            raise HierarchyValidationError(f"Parent joint '{parent_id}' does not exist.")

        rest_len = 0.0
        if parent_id:
            parent = self.joints[parent_id]
            dx = x - parent.x
            dy = y - parent.y
            rest_len = math.hypot(dx, dy)

        joint = Joint(
            id=joint_id,
            name=name,
            x=x,
            y=y,
            parent_id=parent_id,
            rest_length=rest_len,
            is_ik_end_effector=is_ik_end_effector,
            ik_bend_direction=ik_bend_direction,
        )
        self.joints[joint_id] = joint

        if parent_id:
            bone_id = f"bone_{parent_id}_{joint_id}"
            self.bones.append(
                Bone(
                    id=bone_id,
                    parent_joint_id=parent_id,
                    child_joint_id=joint_id,
                    rest_length=rest_len,
                )
            )

        self.validate_hierarchy()
        return joint

    def remove_joint(self, joint_id: str) -> None:
        """Remove a joint and re-parent or prune its children safely."""
        if joint_id not in self.joints:
            return

        deleted_joint = self.joints.pop(joint_id)
        # Re-parent children to deleted joint's parent
        for j in self.joints.values():
            if j.parent_id == joint_id:
                j.parent_id = deleted_joint.parent_id
                if j.parent_id:
                    pj = self.joints[j.parent_id]
                    j.rest_length = math.hypot(j.x - pj.x, j.y - pj.y)
                else:
                    j.rest_length = 0.0

        # Rebuild bones
        self.rebuild_bones()
        self.validate_hierarchy()

    def rebuild_bones(self) -> None:
        """Reconstruct the bone list from current parent-child joint references."""
        self.bones.clear()
        for jid, joint in self.joints.items():
            if joint.parent_id and joint.parent_id in self.joints:
                pj = self.joints[joint.parent_id]
                length = math.hypot(joint.x - pj.x, joint.y - pj.y)
                joint.rest_length = length
                self.bones.append(
                    Bone(
                        id=f"bone_{joint.parent_id}_{jid}",
                        parent_joint_id=joint.parent_id,
                        child_joint_id=jid,
                        rest_length=length,
                    )
                )

    def set_joint_position(self, joint_id: str, x: float, y: float, update_rest_length: bool = False) -> None:
        """Update joint position and optionally recompute rest lengths."""
        if joint_id not in self.joints:
            return
        joint = self.joints[joint_id]
        joint.x = x
        joint.y = y

        if update_rest_length:
            if joint.parent_id and joint.parent_id in self.joints:
                pj = self.joints[joint.parent_id]
                joint.rest_length = math.hypot(joint.x - pj.x, joint.y - pj.y)
            for child in self.get_children(joint_id):
                child.rest_length = math.hypot(child.x - joint.x, child.y - joint.y)
            self.rebuild_bones()

    def get_roots(self) -> List[Joint]:
        """Return all root joints (joints with no parent)."""
        return [j for j in self.joints.values() if not j.parent_id]

    def get_children(self, joint_id: str) -> List[Joint]:
        """Return direct children of a given joint."""
        return [j for j in self.joints.values() if j.parent_id == joint_id]

    def get_ancestors(self, joint_id: str) -> List[str]:
        """Return ordered list of ancestor joint IDs from immediate parent up to root."""
        ancestors = []
        curr = self.joints.get(joint_id)
        while curr and curr.parent_id:
            if curr.parent_id in ancestors:
                raise HierarchyValidationError(f"Cyclic loop detected at joint '{curr.parent_id}'")
            ancestors.append(curr.parent_id)
            curr = self.joints.get(curr.parent_id)
        return ancestors

    def validate_hierarchy(self) -> None:
        """Validate skeleton hierarchy integrity, detecting cycles, orphans, and broken links."""
        for jid, joint in self.joints.items():
            if joint.parent_id:
                if joint.parent_id == jid:
                    raise HierarchyValidationError(f"Joint '{jid}' cannot be its own parent.")
                if joint.parent_id not in self.joints:
                    raise HierarchyValidationError(f"Joint '{jid}' references missing parent '{joint.parent_id}'.")

            # Check for loops
            visited: Set[str] = {jid}
            curr_pid = joint.parent_id
            while curr_pid:
                if curr_pid in visited:
                    raise HierarchyValidationError(f"Hierarchy cycle detected involving joint '{curr_pid}'.")
                visited.add(curr_pid)
                parent_joint = self.joints.get(curr_pid)
                curr_pid = parent_joint.parent_id if parent_joint else None

    def clone(self) -> Skeleton:
        """Create a deep independent copy of this skeleton."""
        skel = Skeleton(name=self.name)
        for j in self.joints.values():
            skel.joints[j.id] = Joint(**j.__dict__)
        skel.bones = [Bone(**b.__dict__) for b in self.bones]
        skel._next_joint_id = self._next_joint_id
        return skel

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skeleton to dictionary."""
        return {
            "name": self.name,
            "joints": [j.to_dict() for j in self.joints.values()],
            "bones": [b.to_dict() for b in self.bones],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Skeleton:
        """Deserialize skeleton from dictionary with validation."""
        skel = cls(name=data.get("name", "CharacterRig"))
        raw_joints = data.get("joints", [])
        for j_data in raw_joints:
            j = Joint.from_dict(j_data)
            if j.id in skel.joints:
                raise HierarchyValidationError(f"Duplicate joint ID '{j.id}' in serialized data.")
            skel.joints[j.id] = j

        # Check max numeric id
        for jid in skel.joints:
            if jid.startswith("joint_"):
                try:
                    num = int(jid.split("_")[1])
                    if num >= skel._next_joint_id:
                        skel._next_joint_id = num + 1
                except ValueError:
                    pass

        raw_bones = data.get("bones", [])
        if raw_bones:
            for b_data in raw_bones:
                skel.bones.append(Bone.from_dict(b_data))
        else:
            skel.rebuild_bones()

        skel.validate_hierarchy()
        return skel
