import sqlite3

from flask import Flask

from coach_routes import coach_bp
from training.catalogue import load_catalogue
from training.movement_coaching import PATTERN_DEFINITIONS


def _client(monkeypatch, tmp_path, *, health_consent=True):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "phase17-pilot-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "phase17-test-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'phase17.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    client = app.test_client()
    created = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "phase17-pilot-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "phase17-test-v1",
            "health_data_consent": health_consent,
            "profile": {
                "goal": "functional",
                "experience": "beginner",
                "equipment": ["bodyweight", "resistance_band"],
                "sessions_per_week": 2,
                "session_minutes": 45,
            },
        },
    )
    assert created.status_code == 201
    payload = created.get_json()
    return client, payload["profile"]["profile_id"], payload["profile_access_token"], tmp_path / "phase17.sqlite3"


def test_movement_assessment_is_persisted_only_with_separate_health_consent(monkeypatch, tmp_path):
    client, profile_id, token, _ = _client(monkeypatch, tmp_path, health_consent=False)
    response = client.put(
        f"/coach/profile/{profile_id}/assessment",
        headers={"X-Profile-Token": token},
        json={"movement_tasks": {"squat": {"status": "needs_support"}}},
    )
    assert response.status_code == 403

    client, profile_id, token, _ = _client(monkeypatch, tmp_path, health_consent=True)
    response = client.put(
        f"/coach/profile/{profile_id}/assessment",
        headers={"X-Profile-Token": token},
        json={"movement_tasks": {
            "squat": {"status": "needs_support"},
            "hinge": {"status": "comfortable"},
        }},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["assessment_stored"] is True
    assert body["assessment"]["is_diagnosis"] is False
    assert body["assessment"]["automatic_programme_change"] == "none"



def _save_six_pattern_assessment(client, profile_id, token, *, status="comfortable"):
    response = client.put(
        f"/coach/profile/{profile_id}/movement-assessment",
        headers={"X-Profile-Token": token},
        json={
            "movement_assessment_consent": True,
            "movement_patterns": {
                pattern: {"status": status} for pattern in PATTERN_DEFINITIONS
            },
        },
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_saved_movement_assessment_is_used_when_generating_next_programme(monkeypatch, tmp_path):
    import coach_routes

    client, profile_id, token, _ = _client(monkeypatch, tmp_path, health_consent=True)
    saved = _save_six_pattern_assessment(client, profile_id, token)

    called = {}
    def fake_generate_program(profile, feedback=None, movement_assessment=None, movement_decisions=None):
        called["movement_assessment"] = movement_assessment
        called["movement_decisions"] = movement_decisions
        return {"goal": profile["goal"], "sessions": [{"session": 1, "exercises": []}]}

    monkeypatch.setattr(coach_routes, "generate_program", fake_generate_program)
    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 200
    assert called["movement_assessment"] is None
    assert set(called["movement_decisions"]) == set(PATTERN_DEFINITIONS)
    assert response.get_json()["movement_assessment_applied"] is True
    assert response.get_json()["program_stored"] is True


def test_saved_profile_programme_blocks_when_all_patterns_are_unassessable(monkeypatch, tmp_path):
    client, profile_id, token, _ = _client(monkeypatch, tmp_path, health_consent=True)
    _save_six_pattern_assessment(client, profile_id, token, status="not_assessed")
    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 409
    body = response.get_json()
    assert body["blocked"] is True
    assert body["assessment_required"] is True
    assert "vsaj en vzorec varno oceniti" in body["message"]


def test_programme_versions_are_listed_and_included_in_export(monkeypatch, tmp_path):
    import coach_routes

    client, profile_id, token, _ = _client(monkeypatch, tmp_path)
    _save_six_pattern_assessment(client, profile_id, token)
    monkeypatch.setattr(
        coach_routes, "generate_program",
        lambda profile, feedback=None, movement_assessment=None, movement_decisions=None: {
            "goal": profile["goal"], "sessions": [{"session": 1, "exercises": []}]
        },
    )
    generated = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert generated.status_code == 200
    version_id = generated.get_json()["program_version_id"]

    history = client.get(
        f"/coach/profile/{profile_id}/programs",
        headers={"X-Profile-Token": token},
    )
    assert history.status_code == 200
    versions = history.get_json()["program_versions"]
    assert len(versions) == 1
    assert versions[0]["program_version_id"] == version_id
    assert versions[0]["program"]["goal"] == "functional"

    exported = client.get(
        f"/coach/profile/{profile_id}/export",
        headers={"X-Profile-Token": token},
    )
    assert exported.status_code == 200
    assert exported.get_json()["export_version"] == "1.1"
    assert len(exported.get_json()["program_versions"]) == 1


def test_health_data_consent_withdrawal_erases_assessment_and_heart_rate(monkeypatch, tmp_path):
    client, profile_id, token, database = _client(monkeypatch, tmp_path, health_consent=True)
    headers = {"X-Profile-Token": token}
    assessment = client.put(
        f"/coach/profile/{profile_id}/assessment",
        headers=headers,
        json={"movement_tasks": {"squat": {"status": "symptoms_reported"}}},
    )
    assert assessment.status_code == 200

    exercise_id = next(item["id"] for item in load_catalogue() if item["id"] == "push_up")
    logged = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers=headers,
        json={
            "session_date": "2026-11-08",
            "duration_minutes": 30,
            "difficulty": "moderate",
            "recovery": "good",
            "completed": True,
            "exercises": [{
                "exercise_id": exercise_id,
                "planned_sets": 1,
                "target_reps_min": 8,
                "target_reps_max": 12,
                "execution_quality": "controlled",
                "set_results": [{"reps": 8, "load_kg": 0, "rir": 3}],
            }],
            "conditioning": [{
                "modality": "aerobic_base",
                "protocol_id": "walk-20",
                "work_seconds": 1200,
                "duration_seconds": 1200,
                "intervals_completed": 1,
                "rpe": 3,
                "average_heart_rate": 110,
            }],
            "discomfort_reported": False,
        },
    )
    assert logged.status_code == 201

    withdrawn = client.post(
        f"/coach/profile/{profile_id}/consent",
        headers=headers,
        json={"health_data_consent": False},
    )
    assert withdrawn.status_code == 200
    conn = sqlite3.connect(database)
    assessment_count = conn.execute(
        "SELECT COUNT(*) FROM atena_movement_assessments WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()[0]
    session_json = conn.execute(
        "SELECT session_json FROM atena_training_sessions WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()[0]
    conn.close()
    assert assessment_count == 0
    assert "average_heart_rate" not in session_json



def test_average_heart_rate_requires_separate_health_data_consent(monkeypatch, tmp_path):
    client, profile_id, token, _ = _client(monkeypatch, tmp_path, health_consent=False)
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-08",
            "duration_minutes": 20,
            "difficulty": "moderate",
            "recovery": "good",
            "completed": True,
            "exercises": [],
            "conditioning": [{
                "modality": "aerobic_base",
                "protocol_id": "walk-20",
                "work_seconds": 1200,
                "duration_seconds": 1200,
                "intervals_completed": 1,
                "rpe": 3,
                "average_heart_rate": 110,
            }],
        },
    )
    assert response.status_code == 403
