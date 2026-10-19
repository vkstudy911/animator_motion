"""Versioned JSON serialization and schema validation for skeletal animation projects.

Provides safe atomic saving, loading, and structural validation with no insecure
deserialization mechanisms (such as pickle).
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict, Optional, Tuple

from app.animation.interpolation import SkeletonAnimation
from app.models.skeleton import HierarchyValidationError, Skeleton


class ProjectSerializationError(ValueError):
    """Raised when serialized project JSON is malformed or invalid."""
    pass


class RigProjectSerializer:
    """Handles versioned schema serialization and deserialization for 2D skeletal projects."""

    CURRENT_SCHEMA_VERSION = 3

    @classmethod
    def serialize_to_dict(
        cls,
        skeleton: Optional[Skeleton],
        animation: Optional[SkeletonAnimation],
        canvas_width: int = 1280,
        canvas_height: int = 720,
        fps: int = 24,
        metadata: Optional[Dict[str, Any]] = None,
        reference_image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Serialize skeletal animation project to a versioned dictionary."""
        data: Dict[str, Any] = {
            "schema_version": cls.CURRENT_SCHEMA_VERSION,
            "metadata": metadata or {"name": "Skeletal Project", "generator": "AI Doodle Studio Rigging"},
            "canvas": {
                "width": int(canvas_width),
                "height": int(canvas_height),
                "fps": int(fps),
            },
            "reference_image": {
                "path": reference_image_path or "",
            },
            "skeleton": skeleton.to_dict() if skeleton else None,
            "animation": animation.to_dict() if animation else None,
        }
        return data

    @classmethod
    def deserialize_from_dict(
        cls,
        data: Dict[str, Any],
    ) -> Tuple[Optional[Skeleton], Optional[SkeletonAnimation], Dict[str, Any]]:
        """Validate and deserialize project dictionary into Skeleton and SkeletonAnimation instances."""
        if not isinstance(data, dict):
            raise ProjectSerializationError("Root serialized data must be a JSON object.")

        version = data.get("schema_version", 1)
        if version > cls.CURRENT_SCHEMA_VERSION:
            raise ProjectSerializationError(f"Unsupported future schema version: {version}")

        # Validate canvas
        canvas_info = data.get("canvas", {})
        width = int(canvas_info.get("width", 1280))
        height = int(canvas_info.get("height", 720))
        fps = int(canvas_info.get("fps", 24))

        skeleton: Optional[Skeleton] = None
        skel_data = data.get("skeleton")
        if skel_data:
            try:
                skeleton = Skeleton.from_dict(skel_data)
            except HierarchyValidationError as exc:
                raise ProjectSerializationError(f"Invalid skeleton hierarchy: {exc}") from exc
            except Exception as exc:
                raise ProjectSerializationError(f"Malformed skeleton data: {exc}") from exc

        animation: Optional[SkeletonAnimation] = None
        anim_data = data.get("animation")
        if anim_data:
            try:
                animation = SkeletonAnimation.from_dict(anim_data)
            except Exception as exc:
                raise ProjectSerializationError(f"Malformed animation keyframe data: {exc}") from exc

        meta = {
            "schema_version": version,
            "width": width,
            "height": height,
            "fps": fps,
            "reference_image_path": data.get("reference_image", {}).get("path", ""),
            "metadata": data.get("metadata", {}),
        }
        return skeleton, animation, meta

    @classmethod
    def save_to_file(
        cls,
        file_path: str,
        skeleton: Optional[Skeleton],
        animation: Optional[SkeletonAnimation],
        canvas_width: int = 1280,
        canvas_height: int = 720,
        fps: int = 24,
        metadata: Optional[Dict[str, Any]] = None,
        reference_image_path: Optional[str] = None,
    ) -> None:
        """Atomically serialize project to a JSON file."""
        data = cls.serialize_to_dict(
            skeleton=skeleton,
            animation=animation,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            fps=fps,
            metadata=metadata,
            reference_image_path=reference_image_path,
        )

        target_dir = os.path.dirname(os.path.abspath(file_path)) or "."
        os.makedirs(target_dir, exist_ok=True)

        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".rig_tmp_")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(json_bytes)
            os.replace(tmp_path, file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @classmethod
    def load_from_file(
        cls,
        file_path: str,
    ) -> Tuple[Optional[Skeleton], Optional[SkeletonAnimation], Dict[str, Any]]:
        """Safely load and validate project from a JSON file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Project file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ProjectSerializationError(f"Malformed JSON in '{file_path}': {exc}") from exc

        return cls.deserialize_from_dict(data)
