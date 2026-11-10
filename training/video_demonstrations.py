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
    "fzs_kettlebell_lateral_deadlift_mzd6t7yo0sw": {
        "video_id": "mzD6t7Yo0Sw",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Mrtvi dvig s kettlebellom bočno",
        "source_url": "https://www.youtube.com/watch?v=mzD6t7Yo0Sw",
        "embed_url": "https://www.youtube-nocookie.com/embed/mzD6t7Yo0Sw",
        "movement_pattern": "hinge",
        "exercise_id": None,
        "exercise_variant_id": "kettlebell_lateral_deadlift",
        "learning_method_id": None,
        "content_scope": "exercise_demonstration_pending_catalogue_mapping",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_reverse_lunge_srggzkwg5ri": {
        "video_id": "SRGGZKWG5rI",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Izpadni korak nazaj",
        "source_url": "https://www.youtube.com/watch?v=SRGGZKWG5rI",
        "embed_url": "https://www.youtube-nocookie.com/embed/SRGGZKWG5rI",
        "movement_pattern": "lunge",
        "exercise_id": "reverse_lunge",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_goblet_squat_dxhdegodgpm": {
        "video_id": "dxHdegoDGPM",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Goblet squat",
        "source_url": "https://www.youtube.com/watch?v=dxHdegoDGPM",
        "embed_url": "https://www.youtube-nocookie.com/embed/dxHdegoDGPM",
        "movement_pattern": "squat",
        "exercise_id": "squat_goblet",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_heel_elevated_squat_rhuoqaqe_we": {
        "video_id": "rHUOqAQE_WE",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Počep s podprtimi petami",
        "source_url": "https://www.youtube.com/watch?v=rHUOqAQE_WE",
        "embed_url": "https://www.youtube-nocookie.com/embed/rHUOqAQE_WE",
        "movement_pattern": "squat",
        "exercise_id": "heel_elevated_squat",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_hip_hinge_he_fe0hwgnw": {
        "video_id": "he_fE0HwGNw",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Predklon",
        "source_url": "https://www.youtube.com/watch?v=he_fE0HwGNw",
        "embed_url": "https://www.youtube-nocookie.com/embed/he_fE0HwGNw",
        "movement_pattern": "hinge",
        "exercise_id": "bodyweight_hip_hinge",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "hinge_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_barbell_overhead_press_d5rhxg7ahfi": {
        "video_id": "D5RhXg7ahfI",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Potisk nad glavo z drogom",
        "source_url": "https://www.youtube.com/watch?v=D5RhXg7ahfI",
        "embed_url": "https://www.youtube-nocookie.com/embed/D5RhXg7ahfI",
        "movement_pattern": "vertical_push",
        "exercise_id": "barbell_overhead_press",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_plate_overhead_press_grcaxh06x8": {
        "video_id": "GrcA2Xh06x8",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Potisk nad glavo s kolutom",
        "source_url": "https://www.youtube.com/watch?v=GrcA2Xh06x8",
        "embed_url": "https://www.youtube-nocookie.com/embed/GrcA2Xh06x8",
        "movement_pattern": "vertical_push",
        "exercise_id": None,
        "exercise_variant_id": "plate_overhead_press",
        "learning_method_id": None,
        "content_scope": "exercise_demonstration_pending_catalogue_mapping",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_reaching_squat_f6lsipadds": {
        "video_id": "f6LSIpaDdSA",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Reaching squat – s kolutom v predročenju",
        "source_url": "https://www.youtube.com/watch?v=f6LSIpaDdSA",
        "embed_url": "https://www.youtube-nocookie.com/embed/f6LSIpaDdSA",
        "movement_pattern": "squat",
        "exercise_id": "reaching_squat",
        "exercise_variant_id": "reaching_counterbalance",
        "learning_method_id": "reaching_counterbalance",
        "content_scope": "exact_learning_method_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_push_up_4sxnioaeu5u": {
        "video_id": "4SXniOAEU5U",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Skleca",
        "source_url": "https://www.youtube.com/watch?v=4SXniOAEU5U",
        "embed_url": "https://www.youtube-nocookie.com/embed/4SXniOAEU5U",
        "movement_pattern": "horizontal_push",
        "exercise_id": "push_up",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
        "active": True,
    },
    "fzs_barbell_bent_over_row_2quhyicwgpu": {
        "video_id": "2QuHyICgWPU",
        "provider": "youtube",
        "channel_name": "Fitnes zveza Slovenije (FZS)",
        "title": "Veslanje v predklonu",
        "source_url": "https://www.youtube.com/watch?v=2QuHyICgWPU",
        "embed_url": "https://www.youtube-nocookie.com/embed/2QuHyICgWPU",
        "movement_pattern": "horizontal_pull",
        "exercise_id": "barbell_bent_over_row",
        "exercise_variant_id": None,
        "learning_method_id": None,
        "content_scope": "exact_exercise_demonstration",
        "duration_seconds": None,
        "language": "sl",
        "rights_status": "youtube_platform_embed_only",
        "embed_allowed": None,
        "review_status": "pending",
        "review_notes": "URL and exercise label supplied by the user. Verify video content, exact execution and YouTube embed availability before public display.",
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
