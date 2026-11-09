"""Curated video demonstrations for ATENA.

Videos are mapped to an exact exercise or learning method, not merely to a
muscle group. A video may be owner-approved for content while embed availability
and rights status remain independently verifiable.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

VIDEO_REGISTRY_VERSION = "video-demonstrations-v1"

# The user supplied and approved this short FZS squat demonstration.
# Do not infer its precise squat variation until the actual frames are reviewed.
VIDEO_DEMONSTRATIONS: dict[str, dict[str, Any]] = {
    "fzs_squat_ciwsqlgenas": {
        "video_id": "CIwsqlgeNAs",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS) – attribution to be verified",
        "title": "Počep",
        "source_url": "https://www.youtube.com/watch?v=CIwsqlgeNAs",
        "embed_url": "https://www.youtube-nocookie.com/embed/CIwsqlgeNAs",
        "movement_pattern": "squat",
        "exercise_id": None,
        "learning_method_id": None,
        "content_scope": "general_squat_demonstration",
        "duration_seconds": 5,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "owner_approved",
        "review_notes": (
            "User confirms this is an excellent, short (~5 s) movement-only "
            "demonstration. Exact variation and embed availability must be "
            "checked before final UI publication."
        ),
        "active": True,
    },
}

# Future catalogue taxonomy. These are intentionally not video records:
# no video IDs are fabricated. Add a record only after receiving and checking
# the exact source URL.
FUNCTIONAL_SKILL_CATEGORIES: dict[str, dict[str, str]] = {
    "burpee": {
        "label": "Burpee",
        "category": "functional_skill",
        "movement_pattern": "multi_pattern",
    },
    "box_jump": {
        "label": "Skok na box",
        "category": "functional_skill",
        "movement_pattern": "jump_landing",
    },
    "wall_ball": {
        "label": "Wall ball",
        "category": "functional_skill",
        "movement_pattern": "squat_throw",
    },
}


def get_video_demonstrations(
    *,
    movement_pattern: str | None = None,
    exercise_id: str | None = None,
    learning_method_id: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """Return video records matching an exact learning/exercise context."""
    records = []
    for record in VIDEO_DEMONSTRATIONS.values():
        if not include_inactive and not record.get("active", False):
            continue
        if movement_pattern and record.get("movement_pattern") != movement_pattern:
            continue
        if exercise_id and record.get("exercise_id") != exercise_id:
            continue
        if learning_method_id and record.get("learning_method_id") != learning_method_id:
            continue
        records.append(deepcopy(record))
    return records


def get_functional_skill_categories() -> dict[str, dict[str, str]]:
    """Return supported future functional-skill categories (without fake videos)."""
    return deepcopy(FUNCTIONAL_SKILL_CATEGORIES)
