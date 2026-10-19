"""Skeletal rigging and semi-automatic suggestion package."""

from app.rigging.image_analysis import estimate_image_foreground_bounds
from app.rigging.suggestion_engine import RigSuggestionEngine
from app.rigging.templates import TEMPLATES, SkeletonTemplate

__all__ = [
    "RigSuggestionEngine",
    "SkeletonTemplate",
    "TEMPLATES",
    "estimate_image_foreground_bounds",
]
