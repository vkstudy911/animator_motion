"""Semi-automatic rig suggestion engine driven by rule-based prompt analysis and templates.

Generates scalable 2D skeletons from natural language descriptions or template keys,
mapping normalized joint coordinates to arbitrary canvas dimensions or character bounding boxes.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from app.models.skeleton import Skeleton
from app.rigging.templates import GENERIC_TEMPLATE, SkeletonTemplate, TEMPLATES

Bounds = Tuple[float, float, float, float]  # (min_x, min_y, width, height)


class RigSuggestionEngine:
    """Parses text prompts and builds scaled Skeleton instances from templates."""

    @staticmethod
    def classify_prompt(prompt: str) -> str:
        """Classify a text prompt into a template key using keyword rules.

        Returns one of: 'human', 'quadruped', 'bird', 'creature', or 'generic'.
        """
        p = prompt.strip().lower()

        # Multi-limb / fantasy creature
        if re.search(r"\b(six legs|6 legs|creature|insect|spider|alien|monster)\b", p):
            return "creature"

        # Quadruped / Cat / Dog / Four legs
        if re.search(r"\b(cat|dog|feline|canine|horse|wolf|lion|tiger|quadruped|four legs|4 legs|long tail)\b", p):
            return "quadruped"

        # Bird / Avian / Wings
        if re.search(r"\b(bird|avian|wing|wings|eagle|parrot|falcon|duck|flying)\b", p):
            return "bird"

        # Human / Biped / Two arms and two legs
        if re.search(r"\b(human|person|man|woman|biped|character|boy|girl|warrior|hero|two arms|2 arms)\b", p):
            return "human"

        return "generic"

    def suggest_from_prompt(
        self,
        prompt: str,
        bounds: Optional[Bounds] = None,
        canvas_width: float = 1280.0,
        canvas_height: float = 720.0,
    ) -> Skeleton:
        """Generate a complete Skeleton from a text prompt, scaled to bounds or canvas."""
        template_key = self.classify_prompt(prompt)
        template = TEMPLATES.get(template_key, GENERIC_TEMPLATE)
        return self.instantiate_template(template, bounds, canvas_width, canvas_height)

    def instantiate_template(
        self,
        template: SkeletonTemplate,
        bounds: Optional[Bounds] = None,
        canvas_width: float = 1280.0,
        canvas_height: float = 720.0,
    ) -> Skeleton:
        """Instantiate and scale a SkeletonTemplate into real pixel coordinates."""
        skel = Skeleton(name=f"{template.name}_Rig")

        # Determine target bounding box
        if bounds is not None and bounds[2] > 20 and bounds[3] > 20:
            bx, by, bw, bh = bounds
        else:
            # Center on canvas with standard margin
            bw = min(canvas_width * 0.5, canvas_height * 0.75)
            bh = bw * 1.3
            bx = (canvas_width - bw) / 2.0
            by = (canvas_height - bh) / 2.0

        for jdef in template.joints:
            px = bx + jdef.norm_x * bw
            py = by + jdef.norm_y * bh
            skel.add_joint(
                name=jdef.name,
                x=px,
                y=py,
                parent_id=jdef.parent_id,
                joint_id=jdef.id,
                is_ik_end_effector=jdef.is_ik_end_effector,
                ik_bend_direction=jdef.ik_bend_direction,
            )

        return skel
