from training.program import _learning_task_videos
from training.video_demonstrations import (
    FUNCTIONAL_SKILL_CATEGORIES,
    VIDEO_DEMONSTRATIONS,
    get_functional_skill_categories,
    get_video_demonstrations,
)


def test_all_ten_user_supplied_fzs_videos_are_registered():
    expected = {
        "mzD6t7Yo0Sw": ("hinge", "kettlebell_lateral_deadlift"),
        "SRGGZKWG5rI": ("lunge", "reverse_lunge"),
        "dxHdegoDGPM": ("squat", "squat_goblet"),
        "rHUOqAQE_WE": ("squat", "heel_elevated_squat"),
        "he_fE0HwGNw": ("hinge", "bodyweight_hip_hinge"),
        "D5RhXg7ahfI": ("vertical_push", "barbell_overhead_press"),
        "GrcA2Xh06x8": ("vertical_push", "plate_overhead_press"),
        "f6LSIpaDdSA": ("squat", "reaching_squat"),
        "4SXniOAEU5U": ("horizontal_push", "push_up"),
        "2QuHyICgWPU": ("horizontal_pull", "barbell_bent_over_row"),
    }
    for video_id, (pattern, exercise_id) in expected.items():
        video = next(v for v in VIDEO_DEMONSTRATIONS.values() if v["video_id"] == video_id)
        assert video["movement_pattern"] == pattern
        assert video["exercise_id"] == exercise_id
        assert video["review_status"] == "pending"
        assert video["embed_allowed"] is None
        assert video["duration_seconds"] is None


def test_exact_exercise_videos_are_returned_for_their_exercise():
    assert get_video_demonstrations(exercise_id="reverse_lunge")[0]["video_id"] == "SRGGZKWG5rI"
    assert get_video_demonstrations(exercise_id="squat_goblet")[0]["video_id"] == "dxHdegoDGPM"
    assert get_video_demonstrations(exercise_id="barbell_bent_over_row")[0]["video_id"] == "2QuHyICgWPU"


def test_reaching_squat_video_is_linked_to_exact_learning_method():
    videos = get_video_demonstrations(learning_method_id="reaching_counterbalance")
    assert any(v["video_id"] == "f6LSIpaDdSA" for v in videos)


def test_lookup_filters_by_movement_pattern():
    assert len(get_video_demonstrations(movement_pattern="squat")) == 4
    assert len(get_video_demonstrations(movement_pattern="hinge")) == 2


def test_video_lookup_returns_copies():
    videos = get_video_demonstrations()
    videos[0]["title"] = "mutated"
    assert all(v["title"] != "mutated" for v in VIDEO_DEMONSTRATIONS.values())


def test_future_functional_skills_are_taxonomy_not_fake_video_records():
    skills = get_functional_skill_categories()
    assert {"burpee", "box_jump", "wall_ball"}.issubset(skills)
    assert all("video_id" not in item for item in skills.values())


def test_exact_video_links_are_not_cross_applied_to_other_patterns():
    assert _learning_task_videos("hinge", None, "reverse_lunge") == []
    assert _learning_task_videos("horizontal_push", None, "squat_goblet") == []


def test_new_video_variations_are_real_catalogue_exercises():
    from training.catalogue import get_exercise
    assert get_exercise("kettlebell_lateral_deadlift")["equipment"] == ["kettlebell"]
    assert get_exercise("plate_overhead_press")["equipment"] == ["weight_plate"]
    assert get_video_demonstrations(exercise_id="kettlebell_lateral_deadlift")[0]["video_id"] == "mzD6t7Yo0Sw"
    assert get_video_demonstrations(exercise_id="plate_overhead_press")[0]["video_id"] == "GrcA2Xh06x8"


def test_vertical_pull_has_exact_demonstrations_for_all_three_core_variants():
    expected = {
        "pull_up": "lkqw5Ysf3zA",
        "band_assisted_pull_up": "fzsc4e6rSZ0",
        "foot_assisted_pull_up": "vBGFAQ4nT0g",
    }
    for exercise_id, video_id in expected.items():
        videos = get_video_demonstrations(exercise_id=exercise_id)
        assert any(video["video_id"] == video_id for video in videos)
        assert all(video["movement_pattern"] == "vertical_pull" for video in videos)
