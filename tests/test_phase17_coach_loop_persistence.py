import sqlite3

from flask import Flask

from coach_routes import coach_bp
from training.catalogue import load_catalogue
from training.movement_coaching import PATTERN_DEFINITIONS


def _client(monkeypatch, tmp_path, *, health_consent=True, profile=None, database_name="phase17.sqlite3"):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "phase17-pilot-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "phase17-test-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    database = tmp_path / database_name
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{database}")
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
            "profile": profile or {
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
    return client, payload["profile"]["profile_id"], payload["profile_access_token"], database


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



def _save_six_pattern_assessment(client, profile_id, token, *, status="comfortable", statuses=None):
    response = client.put(
        f"/coach/profile/{profile_id}/movement-assessment",
        headers={"X-Profile-Token": token},
        json={
            "movement_assessment_consent": True,
            "movement_patterns": {
                pattern: {"status": (statuses or {}).get(pattern, status)}
                for pattern in PATTERN_DEFINITIONS
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

def test_five_persona_saved_profile_training_feedback_cycle(monkeypatch, tmp_path):
    """Exercise the persisted profile -> assessment -> programme -> session -> next programme loop.

    This is a deterministic backend integration test. It deliberately avoids
    Gemini/paid calls and uses a temporary SQLite database for each persona.
    """
    personas = {
        "beginner_no_equipment": {
            "profile": {
                "goal": "strength", "experience": "beginner",
                "equipment": ["bodyweight", "chair", "wall", "household_support"],
                "sessions_per_week": 2, "session_minutes": 30,
            },
            "statuses": {
                "squat": "needs_support", "hinge": "needs_support",
                "horizontal_push": "needs_support", "horizontal_pull": "not_assessed",
                "vertical_push": "not_assessed", "lunge": "needs_support",
            },
        },
        "regular_functional_bands": {
            "profile": {
                "goal": "functional", "experience": "intermediate",
                "equipment": ["bodyweight", "resistance_band", "anchor_point",
                              "pull_up_bar", "chair", "household_support"],
                "sessions_per_week": 3, "session_minutes": 45,
            },
            "statuses": {},
        },
        "mobility_limited": {
            "profile": {
                "goal": "functional", "experience": "beginner",
                "equipment": ["bodyweight", "chair", "wall", "household_support",
                              "resistance_band", "anchor_point"],
                "sessions_per_week": 2, "session_minutes": 45,
            },
            "statuses": {
                "squat": "needs_support", "hinge": "needs_support",
                "lunge": "needs_support",
            },
        },
        "muscle_mass_full_gym": {
            "profile": {
                "goal": "hypertrophy", "experience": "advanced",
                "equipment": ["bodyweight", "barbell", "rack", "dumbbell", "bench",
                              "pull_up_bar", "kettlebell", "cable", "resistance_band",
                              "anchor_point", "weight_plate"],
                "sessions_per_week": 3, "session_minutes": 75,
            },
            "statuses": {},
        },
        "conditioning_focused": {
            "profile": {
                "goal": "endurance", "experience": "beginner",
                "equipment": ["bodyweight", "resistance_band", "anchor_point",
                              "bicycle", "jump_rope", "step", "chair", "wall",
                              "household_support"],
                "sessions_per_week": 3, "session_minutes": 45,
            },
            "statuses": {},
        },
    }

    for persona_name, scenario in personas.items():
        client, profile_id, token, _database = _client(
            monkeypatch,
            tmp_path,
            health_consent=True,
            profile=scenario["profile"],
            database_name=f"{persona_name}.sqlite3",
        )
        headers = {"X-Profile-Token": token}

        saved_assessment = _save_six_pattern_assessment(
            client, profile_id, token, statuses=scenario["statuses"]
        )
        assert saved_assessment["assessment_stored"] is True, persona_name
        assert set(saved_assessment["movement_decisions"]) == set(PATTERN_DEFINITIONS), persona_name

        first_response = client.post(
            f"/coach/profile/{profile_id}/program",
            headers=headers,
            json={"no_current_pain_or_restrictions": True},
        )
        assert first_response.status_code == 200, (persona_name, first_response.get_json())
        first = first_response.get_json()
        first_version = first["program_version_id"]
        assert first["program_stored"] is True, persona_name
        assert first["movement_assessment_applied"] is True, persona_name
        sessions = first["program"]["sessions"]
        assert len(sessions) == scenario["profile"]["sessions_per_week"], persona_name
        assert all(len(item["exercises"]) <= 6 for item in sessions), persona_name
        assert all(
            item["estimated_minutes"] <= scenario["profile"]["session_minutes"]
            for item in sessions
        ), persona_name

        first_exercise = sessions[0]["exercises"][0] if sessions[0]["exercises"] else None
        exercise_log = [{
            "exercise_id": first_exercise["exercise_id"],
            "planned_sets": 1,
            "target_reps_min": 1,
            "target_reps_max": 30,
            "execution_quality": "controlled",
            "set_results": [{"reps": 8, "load_kg": 0, "rir": 3}],
        }] if first_exercise else []
        logged = client.post(
            f"/coach/profile/{profile_id}/sessions",
            headers=headers,
            json={
                "session_date": "2026-11-10",
                "duration_minutes": min(30, scenario["profile"]["session_minutes"]),
                "difficulty": "moderate",
                "recovery": "good",
                "completed": True,
                "program_version_id": first_version,
                "exercises": exercise_log,
                "discomfort_reported": False,
            },
        )
        assert logged.status_code == 201, (persona_name, logged.get_json())
        assert logged.get_json()["session"]["program_version_id"] == first_version

        history = client.get(
            f"/coach/profile/{profile_id}/sessions", headers=headers
        )
        assert history.status_code == 200, persona_name
        assert history.get_json()["sessions"][0]["program_version_id"] == first_version

        progress = client.get(
            f"/coach/profile/{profile_id}/progress", headers=headers
        )
        assert progress.status_code == 200, persona_name
        assert progress.get_json()["source"] == "recorded_training_history", persona_name
        assert progress.get_json()["automatic_load_changes"] is False, persona_name

        next_response = client.post(
            f"/coach/profile/{profile_id}/program",
            headers=headers,
            json={"no_current_pain_or_restrictions": True},
        )
        assert next_response.status_code == 200, (persona_name, next_response.get_json())
        second = next_response.get_json()
        assert second["program_stored"] is True, persona_name
        assert second["program_version_id"] != first_version, persona_name
        assert second["adaptation_guidance"] is not None, persona_name

        versions = client.get(
            f"/coach/profile/{profile_id}/programs", headers=headers
        )
        assert versions.status_code == 200, persona_name
        version_ids = {
            item["program_version_id"]
            for item in versions.get_json()["program_versions"]
        }
        assert {first_version, second["program_version_id"]}.issubset(version_ids), persona_name

