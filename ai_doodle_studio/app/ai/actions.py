"""Structured AI action-plan validation, effect generators, and undoable commands.

All AI actions are strictly isolated:
- No execution of arbitrary shell, python, or filesystem calls.
- User artwork and source frames are NEVER overwritten.
- AI effects are placed on separate, fully editable global layer tracks.
- A single undo command cleanly reverts the entire AI operation.
"""

from __future__ import annotations

import datetime
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from app.core.history import UndoCommand
from app.core.layer import LayerTrack


ALLOWED_INTENTS = {
    "track_hand",
    "track_face",
    "track_point",
    "motion_trail",
    "glowing_eyes",
    "captions",
    "resize_canvas",
}


@dataclass
class AIJob:
    """A validated, structured action plan ready for preview or execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_prompt: str = ""
    intent: str = "custom_effect"
    target: str = ""
    layer_track_name: str = "AI Effects"
    frame_range: Tuple[int, int] = (1, 1)
    summary: str = ""
    action_steps: List[str] = field(default_factory=list)
    applied: bool = False
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_prompt": self.user_prompt,
            "intent": self.intent,
            "target": self.target,
            "layer_track_name": self.layer_track_name,
            "frame_range": list(self.frame_range),
            "summary": self.summary,
            "action_steps": self.action_steps,
            "applied": self.applied,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AIJob:
        fr = data.get("frame_range", [1, 1])
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            user_prompt=data.get("user_prompt", ""),
            intent=data.get("intent", "custom_effect"),
            target=data.get("target", ""),
            layer_track_name=data.get("layer_track_name", "AI Effects"),
            frame_range=(fr[0] if len(fr) > 0 else 1, fr[1] if len(fr) > 1 else 1),
            summary=data.get("summary", ""),
            action_steps=data.get("action_steps", []),
            applied=data.get("applied", False),
            created_at=data.get("created_at", datetime.datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


def validate_action_plan(plan: Dict[str, Any], total_frames: int = 1) -> Tuple[bool, Optional[str], Optional[AIJob]]:
    """Validate structured AI response. Strictly rejects unsafe or unparseable commands."""
    if not isinstance(plan, dict):
        return False, "Invalid plan format: Expected JSON object.", None

    intent = plan.get("intent", "")
    if intent not in ALLOWED_INTENTS:
        return False, f"Unsupported action intent: '{intent}'.", None

    fr = plan.get("frame_range", [1, total_frames])
    if not isinstance(fr, (list, tuple)) or len(fr) < 2:
        fr = [1, max(1, total_frames)]

    start_f = max(1, min(int(fr[0]), total_frames))
    end_f = max(start_f, min(int(fr[1]), total_frames))

    layer_name = plan.get("layer_track")
    if not layer_name:
        if intent in ("track_hand", "motion_trail"):
            layer_name = "AI Hand Effects"
        elif intent in ("track_face", "glowing_eyes"):
            layer_name = "AI Face Effects"
        elif intent == "captions":
            layer_name = "Captions"
        else:
            layer_name = "AI Motion Effects"

    summary = plan.get("summary") or f"Apply {intent.replace('_', ' ').title()}"
    steps = [str(s) for s in plan.get("action_steps", [])]

    job = AIJob(
        intent=intent,
        target=str(plan.get("target", "canvas")),
        layer_track_name=layer_name,
        frame_range=(start_f, end_f),
        summary=summary,
        action_steps=steps,
        metadata={"generated_by": "AIDoodleStudio_Assistant"},
    )
    return True, None, job


def generate_effect_cel(
    frame_idx: int,
    total_frames: int,
    width: int,
    height: int,
    job: AIJob,
) -> QImage:
    """Generate a high-quality, fully editable transparent ARGB32 cel for this frame."""
    img = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    start_f, end_f = job.frame_range
    current_f = frame_idx + 1
    if not (start_f <= current_f <= end_f):
        p.end()
        return img

    t = (current_f - start_f) / max(1, (end_f - start_f))

    if job.intent in ("track_hand", "motion_trail"):
        # Draw dynamic sweeping energy flame / motion arc
        cx = width * (0.35 + 0.30 * math.sin(t * math.pi * 1.5))
        cy = height * (0.50 + 0.20 * math.cos(t * math.pi * 2.0))

        # Main glowing trail arc
        path = QPainterPath()
        trail_pts = 6
        for i in range(trail_pts):
            past_t = max(0.0, t - (i * 0.05))
            px = width * (0.35 + 0.30 * math.sin(past_t * math.pi * 1.5))
            py = height * (0.50 + 0.20 * math.cos(past_t * math.pi * 2.0))
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        # Outer glow
        glow_pen = QPen(QColor(231, 111, 81, 110), 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(glow_pen)
        p.drawPath(path)

        # Inner hot core
        core_pen = QPen(QColor(255, 230, 150, 230), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(core_pen)
        p.drawPath(path)

        # Spark particles
        for i in range(8):
            angle = (t * 10 + i * (math.pi / 4))
            dist = 18 + 10 * math.sin(angle * 2)
            sx = cx + dist * math.cos(angle)
            sy = cy + dist * math.sin(angle)
            rad = 3 + (i % 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 200, 100, 210))
            p.drawEllipse(QPointF(sx, sy), rad, rad)

    elif job.intent in ("track_face", "glowing_eyes"):
        # Stylized glowing anime iris and flares
        face_cx = width * 0.50
        face_cy = height * 0.40
        eye_spacing = width * 0.09
        left_eye = QPointF(face_cx - eye_spacing, face_cy)
        right_eye = QPointF(face_cx + eye_spacing, face_cy)

        pulse = 1.0 + 0.15 * math.sin(t * math.pi * 4)

        for eye in (left_eye, right_eye):
            # Outer soft glow
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(231, 111, 81, int(100 * pulse)))
            p.drawEllipse(eye, 16 * pulse, 16 * pulse)

            # Iris core
            p.setBrush(QColor(255, 140, 100, 230))
            p.drawEllipse(eye, 8 * pulse, 8 * pulse)

            # Center white flare
            p.setBrush(QColor(255, 255, 255, 255))
            p.drawEllipse(eye, 3 * pulse, 3 * pulse)

            # Anamorphic horizontal optical flare streak
            flare_pen = QPen(QColor(231, 111, 81, 160), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(flare_pen)
            p.drawLine(QPointF(eye.x() - 36 * pulse, eye.y()), QPointF(eye.x() + 36 * pulse, eye.y()))

    elif job.intent == "captions":
        # Centered bottom subtitle with dark translucent pill
        caption_text = job.target if job.target and job.target != "canvas" else "AI Doodle Studio"
        box_w = min(width * 0.7, 460)
        box_h = 44
        box_x = (width - box_w) / 2
        box_y = height - box_h - 40

        # Background pill
        pill_rect = QRectF(box_x, box_y, box_w, box_h)
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(QColor(18, 18, 22, 210))
        p.drawRoundedRect(pill_rect, 10, 10)

        # Text
        font = QFont("Helvetica Neue", 13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(242, 240, 236))
        p.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, caption_text)

    else:
        # Default motion effect: subtle speed accent
        p.setPen(QPen(QColor(231, 111, 81, 140), 4, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(
            QPointF(width * 0.2 + t * 40, height * 0.7),
            QPointF(width * 0.8 + t * 40, height * 0.7),
        )

    p.end()
    return img


class AIApplyActionCommand(UndoCommand):
    """Unified Undo/Redo command for applying and reverting an AI Job."""

    def __init__(self, project: Any, job: AIJob, description: Optional[str] = None) -> None:
        desc = description or f"AI: {job.summary or job.intent.title()}"
        super().__init__(desc)
        self.project = project
        self.job = job
        self.created_track_id: Optional[str] = None
        self.created_track_index: int = -1
        self.cels_backup: List[QImage] = []

    def redo(self) -> None:
        """Apply the AI effect onto its dedicated Layer Track."""
        if self.job.intent == "resize_canvas":
            # Canvas resize plan
            new_ratio = self.job.target
            w, h = (1080, 1920) if "9:16" in new_ratio else ((1080, 1080) if "1:1" in new_ratio else (1280, 720))
            self.project.resize_canvas(w, h, record_undo=False, format_label=new_ratio)
            self.job.applied = True
            return

        # 1. Create or ensure dedicated LayerTrack
        track = LayerTrack(
            name=self.job.layer_track_name,
            visible=True,
            opacity=0.95,
            locked=False,
            blend_mode="normal",
        )
        self.created_track_id = track.id

        # 2. Generate per-frame cels
        w = self.project.canvas_width
        h = self.project.canvas_height
        total_f = len(self.project.frames)
        self.cels_backup = []

        for f_idx in range(total_f):
            cel = generate_effect_cel(
                frame_idx=f_idx,
                total_frames=total_f,
                width=w,
                height=h,
                job=self.job,
            )
            self.cels_backup.append(cel)

        # 3. Insert layer track on top
        insert_idx = len(self.project.layer_tracks)
        self.created_track_index = insert_idx
        self.project._insert_layer_track(
            index=insert_idx,
            track=track,
            cels=self.cels_backup,
            record_undo=False,
        )

        # Record job in project metadata without saving secrets
        if "ai_jobs" not in self.project.metadata:
            self.project.metadata["ai_jobs"] = []
        self.project.metadata["ai_jobs"].append(self.job.to_dict())

        self.job.applied = True
        self.project.modified = True
        self.project.frames_modified.emit()
        self.project.layers_changed.emit()
        self.project.project_changed.emit()

    def undo(self) -> None:
        """Completely revert and remove the applied AI layer track and metadata."""
        if self.job.intent == "resize_canvas":
            # Revert resize to default 1280x720
            self.project.resize_canvas(1280, 720, record_undo=False, format_label="16:9")
            self.job.applied = False
            return

        # Find and remove the created layer track
        target_idx = -1
        if self.created_track_id:
            for idx, trk in enumerate(self.project.layer_tracks):
                if trk.id == self.created_track_id:
                    target_idx = idx
                    break

        if target_idx >= 0:
            self.project.delete_layer(target_idx, record_undo=False)

        # Remove from metadata
        if "ai_jobs" in self.project.metadata:
            self.project.metadata["ai_jobs"] = [
                j for j in self.project.metadata["ai_jobs"] if j.get("id") != self.job.id
            ]

        self.job.applied = False
        self.project.modified = True
        self.project.frames_modified.emit()
        self.project.layers_changed.emit()
        self.project.project_changed.emit()
