from training.video_demonstrations import (
    FUNCTIONAL_SKILL_CATEGORIES,
    VIDEO_DEMONSTRATIONS,
    get_functional_skill_categories,
    get_video_demonstrations,
)


def test_owner_approved_fzs_squat_video_is_registered():
    video = VIDEO_DEMONSTRATIONS["fzs_squat_ciwsqlgenas"]
    assert video["video_id"] == "CIwsqlgeNAs"
    assert video["title"] == "Počep"
    assert video["duration_seconds"] == 5
    assert video["movement_pattern"] == "squat"
    assert video["review_status"] == "owner_approved"
    assert video["exercise_id"] is None


def test_video_lookup_filters_by_movement_pattern():
    videos = get_video_demonstrations(movement_pattern="squat")
    assert [video["video_id"] for video in videos] == ["CIwsqlgeNAs"]
    assert get_video_demonstrations(movement_pattern="hinge") == []


def test_video_lookup_returns_copies():
    videos = get_video_demonstrations()
    videos[0]["title"] = "mutated"
    assert VIDEO_DEMONSTRATIONS["fzs_squat_ciwsqlgenas"]["title"] == "Počep"


def test_future_functional_skills_are_taxonomy_not_fake_video_records():
    skills = get_functional_skill_categories()
    assert {"burpee", "box_jump", "wall_ball"}.issubset(skills)
    assert all("video_id" not in item for item in skills.values())
