import hashlib
import sqlite3

from flask import Flask

from coach_routes import coach_bp
from training.catalogue import load_catalogue


def _client(monkeypatch, tmp_path, *, health_consent=False):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-test-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "test-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'atena-test.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def _create(client, *, health_consent=False):
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "health_data_consent": health_consent,
            "profile": {
                "goal": "hypertrophy",
                "experience": "intermediate",
                "equipment": ["barbell", "rack", "dumbbell", "bench"],
                "sessions_per_week": 2,
                "session_minutes": 60,
                "available_days": ["monday", "thursday"],
            },
        },
    )
    assert response.status_code == 201
    return response.get_json()


def test_profile_creation_requires_pilot_authorization(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post("/coach/profile", json={
        "privacy_notice_acknowledged": True,
        "privacy_notice_version": "test-v1",
        "profile": {
            "goal": "hypertrophy", "experience": "beginner", "equipment": [],
            "sessions_per_week": 2, "session_minutes": 45,
        },
    })
    assert response.status_code == 403


def test_profile_creation_requires_privacy_notice_acknowledgement(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post("/coach/profile", headers={"X-Pilot-Token": "pilot-test-secret"}, json={
        "privacy_notice_version": "test-v1",
        "profile": {
            "goal": "hypertrophy", "experience": "beginner", "equipment": [],
            "sessions_per_week": 2, "session_minutes": 45,
        },
    })
    assert response.status_code == 400


def test_profile_access_token_is_returned_once_and_only_hash_is_stored(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    assert len(token) >= 40

    conn = sqlite3.connect(tmp_path / "atena-test.sqlite3")
    stored_hash = conn.execute(
        "SELECT token_hash FROM atena_profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0]
    conn.close()
    assert stored_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored_hash != token


def test_profile_isolated_from_other_tokens_and_can_be_updated(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]

    denied = client.get(f"/coach/profile/{profile_id}", headers={"X-Profile-Token": "wrong-token"})
    assert denied.status_code == 404

    loaded = client.get(f"/coach/profile/{profile_id}", headers={"X-Profile-Token": token})
    assert loaded.status_code == 200
    assert loaded.get_json()["profile"]["profile"]["goal"] == "hypertrophy"

    updated = client.put(
        f"/coach/profile/{profile_id}",
        headers={"X-Profile-Token": token},
        json={"profile": {
            "goal": "strength", "experience": "intermediate",
            "equipment": ["barbell", "rack"], "sessions_per_week": 3,
            "session_minutes": 75, "available_days": ["tuesday", "friday"],
        }},
    )
    assert updated.status_code == 200
    assert updated.get_json()["profile"]["profile"]["goal"] == "strength"


def test_profile_rejects_unapproved_or_unnecessary_personal_fields(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "profile": {
                "goal": "hypertrophy", "experience": "beginner", "equipment": [],
                "sessions_per_week": 2, "session_minutes": 45,
                "full_name": "Not stored",
            },
        },
    )
    assert response.status_code == 400


def test_training_history_accepts_catalogue_exercises_and_lists_them(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    headers = {"X-Profile-Token": token}
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers=headers,
        json={
            "session_date": "2026-11-01",
            "duration_minutes": 55,
            "difficulty": "moderate",
            "completed": True,
            "exercises": [{
                "exercise_id": exercise_id, "sets_completed": 3,
                "reps_completed": 10, "load_kg": 40, "rir": 2,
            }],
        },
    )
    assert response.status_code == 201
    sessions = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers)
    assert sessions.status_code == 200
    assert len(sessions.get_json()["sessions"]) == 1
    assert sessions.get_json()["sessions"][0]["session"]["exercises"][0]["exercise_id"] == exercise_id


def test_health_related_feedback_requires_separate_explicit_consent(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, health_consent=False)
    created = _create(client, health_consent=False)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01", "duration_minutes": 40,
            "difficulty": "easy", "completed": True,
            "exercises": [{"exercise_id": exercise_id, "sets_completed": 2, "reps_completed": 12}],
            "discomfort_reported": False,
        },
    )
    assert response.status_code == 403


def test_health_related_feedback_is_stored_only_after_separate_consent(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, health_consent=True)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01", "duration_minutes": 40,
            "difficulty": "moderate", "completed": True,
            "exercises": [{"exercise_id": exercise_id, "sets_completed": 2, "reps_completed": 12}],
            "discomfort_reported": False,
        },
    )
    assert response.status_code == 201
    saved = client.get(f"/coach/profile/{profile_id}/sessions", headers={"X-Profile-Token": token})
    assert saved.get_json()["sessions"][0]["session"]["discomfort_reported"] is False


def test_training_history_rejects_free_text_and_non_catalogue_exercises(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    base = {
        "session_date": "2026-11-01", "duration_minutes": 40,
        "difficulty": "moderate", "completed": True, "exercises": [],
    }
    with_free_text = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={**base, "notes": "Free text medical history"},
    )
    assert with_free_text.status_code == 400
    unknown_exercise = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={**base, "exercises": [{
            "exercise_id": "invented-exercise", "sets_completed": 3, "reps_completed": 10,
        }]},
    )
    assert unknown_exercise.status_code == 400


def test_profile_deletion_removes_profile_and_training_history(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01", "duration_minutes": 40,
            "difficulty": "moderate", "completed": True,
            "exercises": [{"exercise_id": exercise_id, "sets_completed": 2, "reps_completed": 12}],
        },
    )
    deleted = client.delete(f"/coach/profile/{profile_id}", headers={"X-Profile-Token": token})
    assert deleted.status_code == 200
    assert client.get(f"/coach/profile/{profile_id}", headers={"X-Profile-Token": token}).status_code == 404


def test_profile_storage_is_disabled_without_operator_flags(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "false")
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "profile": {
                "goal": "hypertrophy", "experience": "beginner", "equipment": [],
                "sessions_per_week": 2, "session_minutes": 45,
            },
        },
    )
    assert response.status_code == 503


def test_withdrawing_health_consent_erases_previously_stored_discomfort_flags(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    assert created["profile"]["health_data_consent_at"]
    headers = {"X-Profile-Token": token}
    exercise_id = load_catalogue()[0]["id"]
    logged = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers=headers,
        json={
            "session_date": "2026-11-01", "duration_minutes": 40,
            "difficulty": "moderate", "completed": True,
            "exercises": [{"exercise_id": exercise_id, "sets_completed": 2, "reps_completed": 12}],
            "discomfort_reported": True,
        },
    )
    assert logged.status_code == 201

    withdrawn = client.post(
        f"/coach/profile/{profile_id}/consent",
        headers=headers,
        json={"health_data_consent": False},
    )
    assert withdrawn.status_code == 200
    assert withdrawn.get_json()["profile"]["health_data_consent"] is False
    assert withdrawn.get_json()["profile"]["health_data_consent_at"] is None
    history = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers).get_json()["sessions"]
    assert "discomfort_reported" not in history[0]["session"]


def test_profile_preflight_allows_profile_token_and_rest_methods(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.options(
        "/coach/profile/example",
        headers={
            "Origin": "https://gregajenko.si",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,x-profile-token",
        },
    )
    assert response.status_code == 204
    assert "PUT" in response.headers["Access-Control-Allow-Methods"]
    assert "X-Profile-Token" in response.headers["Access-Control-Allow-Headers"]


def test_profile_rejects_equipment_not_supported_by_curated_catalogue(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "profile": {
                "goal": "hypertrophy", "experience": "beginner",
                "equipment": ["imaginary_machine"], "sessions_per_week": 2,
                "session_minutes": 45,
            },
        },
    )
    assert response.status_code == 400


def test_profile_storage_stays_disabled_without_privacy_approval(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "false")
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "profile": {
                "goal": "hypertrophy", "experience": "beginner", "equipment": [],
                "sessions_per_week": 2, "session_minutes": 45,
            },
        },
    )
    assert response.status_code == 503



def test_database_connectivity_endpoint_is_protected_and_read_only(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    denied = client.get("/coach/storage/check")
    assert denied.status_code == 403

    import coach_routes
    monkeypatch.setattr(coach_routes, "store_check_database_connection", lambda: True)
    checked = client.get("/coach/storage/check", headers={"X-Pilot-Token": "pilot-test-secret"})
    assert checked.status_code == 200
    assert checked.get_json() == {
        "database": "reachable",
        "user_data_storage": "still_disabled",
    }


def test_database_connectivity_endpoint_reports_unavailable_without_leaking_details(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    import coach_routes
    from coach_store import StorageUnavailable

    def fail():
        raise StorageUnavailable("private connection detail")

    monkeypatch.setattr(coach_routes, "store_check_database_connection", fail)
    checked = client.get("/coach/storage/check", headers={"X-Pilot-Token": "pilot-test-secret"})
    assert checked.status_code == 503
    assert checked.get_json() == {
        "database": "unavailable",
        "reason": "storage_unavailable",
        "user_data_storage": "still_disabled",
    }



def test_jsonb_decoder_accepts_psycopg_decoded_objects():
    from coach_store import _decode_json

    profile = {"goal": "strength", "equipment": ["barbell", "rack"]}
    session = {"completed": True, "exercises": [{"exercise_id": "squat"}]}
    assert _decode_json(profile) == profile
    assert _decode_json(session) == session
    assert _decode_json('{"goal":"strength"}') == {"goal": "strength"}


def test_saved_profile_limits_match_program_generator():
    from coach_routes import _validate_profile
    import pytest

    base = {
        "goal": "hypertrophy",
        "experience": "beginner",
        "equipment": ["bodyweight"],
        "sessions_per_week": 2,
        "session_minutes": 45,
        "available_days": ["monday", "thursday"],
    }
    assert _validate_profile(base)["sessions_per_week"] == 2
    for invalid in (
        {**base, "sessions_per_week": 1},
        {**base, "sessions_per_week": 5},
        {**base, "session_minutes": 20},
        {**base, "session_minutes": 121},
    ):
        with pytest.raises(ValueError):
            _validate_profile(invalid)
