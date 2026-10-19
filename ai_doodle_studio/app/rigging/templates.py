"""Configurable 2D skeleton templates with normalized coordinates and anatomical hierarchies.

Normalized coordinates (0.0 to 1.0) allow skeletons to automatically scale
to fit any canvas dimension or detected foreground bounding box.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class TemplateJointDef:
    id: str
    name: str
    norm_x: float  # 0.0 to 1.0
    norm_y: float  # 0.0 to 1.0
    parent_id: Optional[str] = None
    is_ik_end_effector: bool = False
    ik_bend_direction: int = 1
    min_angle_deg: float = -180.0
    max_angle_deg: float = 180.0


@dataclass
class SkeletonTemplate:
    key: str
    name: str
    description: str
    joints: List[TemplateJointDef]


# ---------------- 1. Human / Biped Template ----------------
HUMAN_TEMPLATE = SkeletonTemplate(
    key="human",
    name="Human Biped",
    description="Standard biped rig with head, spine, 2 arms, and 2 legs",
    joints=[
        TemplateJointDef("pelvis", "Pelvis", 0.50, 0.55, parent_id=None),
        TemplateJointDef("spine", "Spine", 0.50, 0.42, parent_id="pelvis"),
        TemplateJointDef("chest", "Chest", 0.50, 0.30, parent_id="spine"),
        TemplateJointDef("neck", "Neck", 0.50, 0.22, parent_id="chest"),
        TemplateJointDef("head", "Head", 0.50, 0.12, parent_id="neck"),
        # Left Arm (viewer's left)
        TemplateJointDef("left_shoulder", "Left Shoulder", 0.42, 0.30, parent_id="chest"),
        TemplateJointDef("left_elbow", "Left Elbow", 0.35, 0.42, parent_id="left_shoulder", ik_bend_direction=-1),
        TemplateJointDef("left_hand", "Left Hand", 0.30, 0.54, parent_id="left_elbow", is_ik_end_effector=True),
        # Right Arm (viewer's right)
        TemplateJointDef("right_shoulder", "Right Shoulder", 0.58, 0.30, parent_id="chest"),
        TemplateJointDef("right_elbow", "Right Elbow", 0.65, 0.42, parent_id="right_shoulder", ik_bend_direction=1),
        TemplateJointDef("right_hand", "Right Hand", 0.70, 0.54, parent_id="right_elbow", is_ik_end_effector=True),
        # Left Leg
        TemplateJointDef("left_hip", "Left Hip", 0.45, 0.58, parent_id="pelvis"),
        TemplateJointDef("left_knee", "Left Knee", 0.44, 0.74, parent_id="left_hip", ik_bend_direction=1),
        TemplateJointDef("left_foot", "Left Foot", 0.43, 0.90, parent_id="left_knee", is_ik_end_effector=True),
        # Right Leg
        TemplateJointDef("right_hip", "Right Hip", 0.55, 0.58, parent_id="pelvis"),
        TemplateJointDef("right_knee", "Right Knee", 0.56, 0.74, parent_id="right_hip", ik_bend_direction=-1),
        TemplateJointDef("right_foot", "Right Foot", 0.57, 0.90, parent_id="right_knee", is_ik_end_effector=True),
    ],
)


# ---------------- 2. Quadruped / Cat / Dog Template ----------------
QUADRUPED_TEMPLATE = SkeletonTemplate(
    key="quadruped",
    name="Quadruped",
    description="Four-legged animal rig with spine, 4 legs, and tail",
    joints=[
        TemplateJointDef("pelvis", "Pelvis", 0.30, 0.50, parent_id=None),
        TemplateJointDef("spine_mid", "Spine Mid", 0.48, 0.48, parent_id="pelvis"),
        TemplateJointDef("chest", "Chest", 0.65, 0.46, parent_id="spine_mid"),
        TemplateJointDef("neck", "Neck", 0.76, 0.38, parent_id="chest"),
        TemplateJointDef("head", "Head", 0.85, 0.28, parent_id="neck"),
        # Front Legs
        TemplateJointDef("front_left_shoulder", "Front Left Shoulder", 0.65, 0.52, parent_id="chest"),
        TemplateJointDef("front_left_knee", "Front Left Knee", 0.66, 0.68, parent_id="front_left_shoulder", ik_bend_direction=1),
        TemplateJointDef("front_left_paw", "Front Left Paw", 0.67, 0.85, parent_id="front_left_knee", is_ik_end_effector=True),
        TemplateJointDef("front_right_shoulder", "Front Right Shoulder", 0.62, 0.50, parent_id="chest"),
        TemplateJointDef("front_right_knee", "Front Right Knee", 0.61, 0.66, parent_id="front_right_shoulder", ik_bend_direction=1),
        TemplateJointDef("front_right_paw", "Front Right Paw", 0.60, 0.83, parent_id="front_right_knee", is_ik_end_effector=True),
        # Back Legs
        TemplateJointDef("back_left_hip", "Back Left Hip", 0.32, 0.54, parent_id="pelvis"),
        TemplateJointDef("back_left_hock", "Back Left Hock", 0.28, 0.70, parent_id="back_left_hip", ik_bend_direction=-1),
        TemplateJointDef("back_left_paw", "Back Left Paw", 0.29, 0.86, parent_id="back_left_hock", is_ik_end_effector=True),
        TemplateJointDef("back_right_hip", "Back Right Hip", 0.28, 0.52, parent_id="pelvis"),
        TemplateJointDef("back_right_hock", "Back Right Hock", 0.24, 0.68, parent_id="back_right_hip", ik_bend_direction=-1),
        TemplateJointDef("back_right_paw", "Back Right Paw", 0.25, 0.84, parent_id="back_right_hock", is_ik_end_effector=True),
        # Tail
        TemplateJointDef("tail_base", "Tail Base", 0.22, 0.48, parent_id="pelvis"),
        TemplateJointDef("tail_mid", "Tail Mid", 0.14, 0.42, parent_id="tail_base"),
        TemplateJointDef("tail_tip", "Tail Tip", 0.08, 0.34, parent_id="tail_mid"),
    ],
)


# ---------------- 3. Bird Template ----------------
BIRD_TEMPLATE = SkeletonTemplate(
    key="bird",
    name="Bird",
    description="Avian rig with chest, head, 2 wings, 2 legs, and tail",
    joints=[
        TemplateJointDef("pelvis", "Pelvis", 0.45, 0.60, parent_id=None),
        TemplateJointDef("chest", "Chest", 0.50, 0.48, parent_id="pelvis"),
        TemplateJointDef("neck", "Neck", 0.54, 0.36, parent_id="chest"),
        TemplateJointDef("head", "Head", 0.58, 0.24, parent_id="neck"),
        # Left Wing
        TemplateJointDef("left_wing_base", "Left Wing Shoulder", 0.46, 0.45, parent_id="chest"),
        TemplateJointDef("left_wing_elbow", "Left Wing Elbow", 0.30, 0.32, parent_id="left_wing_base", ik_bend_direction=-1),
        TemplateJointDef("left_wing_tip", "Left Wing Tip", 0.15, 0.25, parent_id="left_wing_elbow", is_ik_end_effector=True),
        # Right Wing
        TemplateJointDef("right_wing_base", "Right Wing Shoulder", 0.54, 0.45, parent_id="chest"),
        TemplateJointDef("right_wing_elbow", "Right Wing Elbow", 0.70, 0.32, parent_id="right_wing_base", ik_bend_direction=1),
        TemplateJointDef("right_wing_tip", "Right Wing Tip", 0.85, 0.25, parent_id="right_wing_elbow", is_ik_end_effector=True),
        # Legs
        TemplateJointDef("left_leg_hip", "Left Hip", 0.46, 0.68, parent_id="pelvis"),
        TemplateJointDef("left_leg_foot", "Left Foot", 0.44, 0.88, parent_id="left_leg_hip", is_ik_end_effector=True),
        TemplateJointDef("right_leg_hip", "Right Hip", 0.54, 0.68, parent_id="pelvis"),
        TemplateJointDef("right_leg_foot", "Right Foot", 0.56, 0.88, parent_id="right_leg_hip", is_ik_end_effector=True),
        TemplateJointDef("tail", "Tail Feathers", 0.38, 0.68, parent_id="pelvis"),
    ],
)


# ---------------- 4. Fantasy Creature Template (6 legs, 2 arms) ----------------
CREATURE_TEMPLATE = SkeletonTemplate(
    key="creature",
    name="Multi-Limb Creature",
    description="Fantasy creature rig with head, torso, 2 arms, and 6 legs",
    joints=[
        TemplateJointDef("root", "Core Root", 0.50, 0.45, parent_id=None),
        TemplateJointDef("thorax", "Thorax", 0.50, 0.32, parent_id="root"),
        TemplateJointDef("head", "Head", 0.50, 0.18, parent_id="thorax"),
        TemplateJointDef("abdomen", "Abdomen", 0.50, 0.58, parent_id="root"),
        # Arms
        TemplateJointDef("arm_left_shoulder", "Left Arm Shoulder", 0.40, 0.32, parent_id="thorax"),
        TemplateJointDef("arm_left_hand", "Left Hand", 0.26, 0.40, parent_id="arm_left_shoulder", is_ik_end_effector=True),
        TemplateJointDef("arm_right_shoulder", "Right Arm Shoulder", 0.60, 0.32, parent_id="thorax"),
        TemplateJointDef("arm_right_hand", "Right Hand", 0.74, 0.40, parent_id="arm_right_shoulder", is_ik_end_effector=True),
        # 6 Legs (3 pairs)
        TemplateJointDef("leg1_left_hip", "Front Left Hip", 0.42, 0.42, parent_id="root"),
        TemplateJointDef("leg1_left_foot", "Front Left Foot", 0.28, 0.55, parent_id="leg1_left_hip", is_ik_end_effector=True),
        TemplateJointDef("leg1_right_hip", "Front Right Hip", 0.58, 0.42, parent_id="root"),
        TemplateJointDef("leg1_right_foot", "Front Right Foot", 0.72, 0.55, parent_id="leg1_right_hip", is_ik_end_effector=True),
        TemplateJointDef("leg2_left_hip", "Mid Left Hip", 0.42, 0.50, parent_id="root"),
        TemplateJointDef("leg2_left_foot", "Mid Left Foot", 0.24, 0.68, parent_id="leg2_left_hip", is_ik_end_effector=True),
        TemplateJointDef("leg2_right_hip", "Mid Right Hip", 0.58, 0.50, parent_id="root"),
        TemplateJointDef("leg2_right_foot", "Mid Right Foot", 0.76, 0.68, parent_id="leg2_right_hip", is_ik_end_effector=True),
        TemplateJointDef("leg3_left_hip", "Rear Left Hip", 0.44, 0.60, parent_id="abdomen"),
        TemplateJointDef("leg3_left_foot", "Rear Left Foot", 0.32, 0.85, parent_id="leg3_left_hip", is_ik_end_effector=True),
        TemplateJointDef("leg3_right_hip", "Rear Right Hip", 0.56, 0.60, parent_id="abdomen"),
        TemplateJointDef("leg3_right_foot", "Rear Right Foot", 0.68, 0.85, parent_id="leg3_right_hip", is_ik_end_effector=True),
    ],
)


# ---------------- 5. Generic Fallback Template ----------------
GENERIC_TEMPLATE = SkeletonTemplate(
    key="generic",
    name="Generic Rig",
    description="General-purpose starter skeleton for custom characters",
    joints=[
        TemplateJointDef("root", "Root", 0.50, 0.50, parent_id=None),
        TemplateJointDef("spine", "Spine", 0.50, 0.35, parent_id="root"),
        TemplateJointDef("head", "Head", 0.50, 0.18, parent_id="spine"),
        TemplateJointDef("limb_left_mid", "Left Mid", 0.38, 0.55, parent_id="root"),
        TemplateJointDef("limb_left_tip", "Left Tip", 0.30, 0.75, parent_id="limb_left_mid", is_ik_end_effector=True),
        TemplateJointDef("limb_right_mid", "Right Mid", 0.62, 0.55, parent_id="root"),
        TemplateJointDef("limb_right_tip", "Right Tip", 0.70, 0.75, parent_id="limb_right_mid", is_ik_end_effector=True),
    ],
)

TEMPLATES: Dict[str, SkeletonTemplate] = {
    "human": HUMAN_TEMPLATE,
    "quadruped": QUADRUPED_TEMPLATE,
    "bird": BIRD_TEMPLATE,
    "creature": CREATURE_TEMPLATE,
    "generic": GENERIC_TEMPLATE,
}
