"""Procedural 2D vector character skinning and rendering engine.

Provides CPU-based vector artwork using QPainter, attaching customizable shapes,
capsules, and polygons to bones and joints with consistent layering and styling.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from app.models.skeleton import Bone, Joint, Skeleton


class VectorSkinRenderer:
    """Renders procedural vector character anatomy attached to a Skeleton."""

    def __init__(self) -> None:
        self.enabled: bool = True
        self.skin_color: QColor = QColor(208, 188, 255, 230)      # Neon Violet tint
        self.clothing_color: QColor = QColor(76, 215, 246, 230)  # Electric Cyan
        self.joint_accent_color: QColor = QColor(255, 176, 205)  # Vivid Magenta
        self.outline_color: QColor = QColor(24, 27, 37, 240)     # Obsidian dark outline
        self.stroke_width: float = 2.5
        self.limb_width_ratio: float = 0.22  # Width relative to bone length

    def render_skin(
        self,
        painter: QPainter,
        skeleton: Skeleton,
        scale: float = 1.0,
        offset: Tuple[float, float] = (0.0, 0.0),
    ) -> None:
        """Render the complete procedural vector character following the skeleton rig."""
        if not self.enabled or not skeleton.joints:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        ox, oy = offset

        # Layer 1: Limbs (Bones rendered as rounded capsules)
        pen = QPen(self.outline_color, self.stroke_width * scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        for bone in skeleton.bones:
            pj = skeleton.joints.get(bone.parent_joint_id)
            cj = skeleton.joints.get(bone.child_joint_id)
            if not pj or not cj:
                continue

            p1 = QPointF(pj.x * scale + ox, pj.y * scale + oy)
            p2 = QPointF(cj.x * scale + ox, cj.y * scale + oy)

            dx = p2.x() - p1.x()
            dy = p2.y() - p1.y()
            length = math.hypot(dx, dy)
            if length < 1.0:
                continue

            # Capsule thickness
            thickness = max(8.0 * scale, min(35.0 * scale, length * self.limb_width_ratio))
            nx = -dy / length * (thickness * 0.5)
            ny = dx / length * (thickness * 0.5)

            # Capsule polygon path
            path = QPainterPath()
            path.moveTo(p1.x() + nx, p1.y() + ny)
            path.lineTo(p2.x() + nx * 0.75, p2.y() + ny * 0.75)
            path.quadTo(p2.x() + dx / length * (thickness * 0.4), p2.y() + dy / length * (thickness * 0.4),
                        p2.x() - nx * 0.75, p2.y() - ny * 0.75)
            path.lineTo(p1.x() - nx, p1.y() - ny)
            path.closeSubpath()

            # Choose color depending on upper vs lower limb
            is_torso_bone = "spine" in bone.id or "chest" in bone.id
            fill_col = self.clothing_color if is_torso_bone else self.skin_color
            painter.setBrush(QBrush(fill_col))
            painter.drawPath(path)

        # Layer 2: Torso / Core polygon if spine/chest/pelvis exist
        pelvis = skeleton.joints.get("pelvis") or skeleton.joints.get("root")
        chest = skeleton.joints.get("chest") or skeleton.joints.get("thorax")
        if pelvis and chest:
            p_pelvis = QPointF(pelvis.x * scale + ox, pelvis.y * scale + oy)
            p_chest = QPointF(chest.x * scale + ox, chest.y * scale + oy)
            torso_w = 40.0 * scale
            torso_path = QPainterPath()
            torso_path.addRoundedRect(
                QRectF(min(p_pelvis.x(), p_chest.x()) - torso_w * 0.5,
                       min(p_pelvis.y(), p_chest.y()),
                       torso_w,
                       abs(p_pelvis.y() - p_chest.y()) + 20.0 * scale),
                12.0 * scale, 12.0 * scale
            )
            painter.setBrush(QBrush(self.clothing_color))
            painter.drawPath(torso_path)

        # Layer 3: Joints & Head
        for jid, joint in skeleton.joints.items():
            pos = QPointF(joint.x * scale + ox, joint.y * scale + oy)
            if "head" in jid:
                # Head circle
                radius = 22.0 * scale
                painter.setBrush(QBrush(self.skin_color))
                painter.drawEllipse(pos, radius, radius)
                # Face indicator / eyes
                painter.setBrush(QBrush(self.outline_color))
                painter.drawEllipse(QPointF(pos.x() + 6 * scale, pos.y() - 2 * scale), 2.5 * scale, 2.5 * scale)
            elif joint.is_ik_end_effector:
                # End-effector paw/hand/foot cap
                radius = 7.0 * scale
                painter.setBrush(QBrush(self.joint_accent_color))
                painter.drawEllipse(pos, radius, radius)
            else:
                # Articulated joint cap
                radius = 4.5 * scale
                painter.setBrush(QBrush(self.skin_color))
                painter.drawEllipse(pos, radius, radius)

        painter.restore()
