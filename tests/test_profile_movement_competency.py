import pytest

from coach_routes import _validate_profile


BASE = {
    "goal": "strength",
    "experience": "advanced",
    "equipment": ["bodyweight"],
    "sessions_per_week": 2,
    "session_minutes": 60,
    "available_days": [],
}


def test_saved_profile_defaults_pistol_squat_competency_to_false():
    profile = _validate_profile(BASE)
    assert profile["pistol_squat_capable"] is False


def test_saved_profile_preserves_explicitly_assessed_pistol_squat_competency():
    profile = _validate_profile({**BASE, "pistol_squat_capable": True})
    assert profile["pistol_squat_capable"] is True


def test_saved_profile_rejects_non_boolean_pistol_squat_competency():
    with pytest.raises(ValueError, match="pistol_squat_capable"):
        _validate_profile({**BASE, "pistol_squat_capable": "yes"})
