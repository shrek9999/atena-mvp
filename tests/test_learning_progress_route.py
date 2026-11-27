import pytest
from flask import Flask

from coach_routes import coach_bp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "test-only-token")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def test_learning_progress_accepts_partial_pattern_and_preserves_previous_results(monkeypatch, client):
    import coach_routes

    criteria = {
        "tempo": True,
        "balance": False,
        "foot_stability": False,
        "knee_control": False,
        "trunk_control": False,
        "tolerated_rom": False,
    }
    previous_hinge = {
        "status": "completed",
        "criteria": {
            "tempo": True,
            "hip_movement": True,
            "knee_control": True,
            "spine_control": True,
            "balance": True,
            "tolerated_rom": True,
        },
    }
    captured = {}
    monkeypatch.setattr(coach_routes, "storage_enabled", lambda: True)
    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    monkeypatch.setattr(
        coach_routes, "store_get_learning_progress",
        lambda profile_id, token: {
            "version": "guided-six-pattern-learning-v2",
            "patterns": {"hinge": previous_hinge},
        },
    )

    def save(profile_id, token, record):
        captured["record"] = record
        return {"learning_progress": record}

    monkeypatch.setattr(coach_routes, "store_save_learning_progress", save)
    response = client.put(
        "/coach/profile/test-profile/learning-progress",
        headers={"X-Profile-Token": "profile-token"},
        json={"patterns": {"squat": {"status": "in_progress", "criteria": criteria}}},
    )

    assert response.status_code == 200
    saved = response.get_json()["learning_progress"]
    assert set(saved["patterns"]) == {"squat", "hinge"}
    assert saved["patterns"]["squat"]["status"] == "in_progress"
    assert saved["patterns"]["hinge"] == previous_hinge
    assert captured["record"]["version"] == "guided-six-pattern-learning-v2"


def test_learning_progress_get_returns_saved_checklists_without_health_consent(monkeypatch, client):
    import coach_routes
    saved = {
        "version": "guided-six-pattern-learning-v2",
        "patterns": {"squat": {"status": "in_progress", "criteria": {}}},
    }
    monkeypatch.setattr(coach_routes, "storage_enabled", lambda: True)
    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    monkeypatch.setattr(coach_routes, "store_get_learning_progress", lambda profile_id, token: saved)

    response = client.get(
        "/coach/profile/test-profile/learning-progress",
        headers={"X-Profile-Token": "profile-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["learning_progress"] == saved
    assert response.headers["Cache-Control"] == "no-store, private"


def test_learning_progress_rejects_unknown_patterns(monkeypatch, client):
    import coach_routes
    monkeypatch.setattr(coach_routes, "storage_enabled", lambda: True)
    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    response = client.put(
        "/coach/profile/test-profile/learning-progress",
        headers={"X-Profile-Token": "profile-token"},
        json={"patterns": {"jumping": {"status": "in_progress", "criteria": {}}}},
    )
    assert response.status_code == 400
    assert "neznane vzorce" in response.get_json()["error"]


def test_learning_progress_rejects_completed_pattern_with_unchecked_criteria(monkeypatch, client):
    import coach_routes
    monkeypatch.setattr(coach_routes, "storage_enabled", lambda: True)
    monkeypatch.setattr(coach_routes, "_profile_token", lambda: "profile-token")
    response = client.put(
        "/coach/profile/test-profile/learning-progress",
        headers={"X-Profile-Token": "profile-token"},
        json={"patterns": {"squat": {
            "status": "completed",
            "criteria": {
                "tempo": True, "balance": False, "foot_stability": True,
                "knee_control": True, "trunk_control": True, "tolerated_rom": True,
            },
        }}},
    )
    assert response.status_code == 400
    assert "ni dokončan" in response.get_json()["error"]
