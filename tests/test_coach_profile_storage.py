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


def test_postgres_profile_tables_enable_rls_and_revoke_public_access(monkeypatch):
    import coach_store

    statements = []
    monkeypatch.setattr(
        coach_store,
        "_execute",
        lambda conn, dialect, sql, params=(): statements.append(sql),
    )
    coach_store._init(object(), "postgres")

    assert "ALTER TABLE atena_profiles ENABLE ROW LEVEL SECURITY" in statements
    assert "ALTER TABLE atena_training_sessions ENABLE ROW LEVEL SECURITY" in statements
    assert any("atena_profiles FROM PUBLIC, anon, authenticated" in sql for sql in statements)
    assert any("atena_training_sessions FROM PUBLIC, anon, authenticated" in sql for sql in statements)



def test_coach_status_is_protected_and_reports_only_safe_readiness(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    denied = client.get("/coach/status")
    assert denied.status_code == 403

    monkeypatch.setenv("GEMINI_API_KEY", "test-provider-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    response = client.get(
        "/coach/status",
        headers={"X-Pilot-Token": "pilot-test-secret"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["chat_available"] is True
    assert data["program_available"] is True
    assert data["catalogue_count"] == len(load_catalogue())
    assert "GEMINI_API_KEY" not in str(data)
    assert "test-provider-key-not-real" not in str(data)


def test_profile_program_requires_current_safety_confirmation(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]

    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": False},
    )
    assert response.status_code == 409
    assert response.get_json()["blocked"] is True


def test_profile_program_keeps_global_feedback_out_of_generator_and_exposes_adaptive_decision(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    logged = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01",
            "duration_minutes": 55,
            "difficulty": "hard",
            "recovery": "poor",
            "completed": False,
            "exercises": [{
                "exercise_id": exercise_id, "sets_completed": 2,
                "reps_completed": 8,
            }],
        },
    )
    assert logged.status_code == 201

    import coach_routes
    captured = {}
    def fake_generate(profile, feedback=None):
        captured["profile"] = profile
        captured["feedback"] = feedback
        return {"goal": profile["goal"], "feedback_applied": feedback, "sessions": []}
    monkeypatch.setattr(coach_routes, "generate_program", fake_generate)

    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 200
    assert captured["profile"]["goal"] == "hypertrophy"
    # Session feedback is consumed by the explainable decision layer, not
    # applied globally to every exercise by the programme generator.
    assert captured["feedback"] is None
    data = response.get_json()
    # Poor recovery is a higher-priority signal than an unspecified
    # incomplete-session reason, so the engine requests a recovery review.
    assert data["adaptive_decision"]["decision"] == "recovery_review"
    assert data["adaptive_decision"]["clarifying_question"]


def test_profile_program_holds_progression_after_logged_discomfort_and_fresh_safety_recheck(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, health_consent=True)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    logged = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01",
            "duration_minutes": 40,
            "difficulty": "moderate",
            "completed": True,
            "exercises": [{
                "exercise_id": exercise_id, "sets_completed": 2,
                "reps_completed": 8,
            }],
            "discomfort_reported": True,
        },
    )
    assert logged.status_code == 201
    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["adaptation_guidance"]["decision"] == "pause_and_review"
    assert data["adaptive_decision"]["decision"] == "pause_and_review"
    assert data["adaptive_decision"]["automatic_program_changes"] is False
    assert data["program"]["feedback_applied"] is None



def test_time_based_exercise_history_stores_seconds_without_faking_repetitions(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    response = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01",
            "duration_minutes": 45,
            "difficulty": "moderate",
            "recovery": "good",
            "completed": True,
            "exercises": [{
                "exercise_id": exercise_id,
                "sets_completed": 2,
                "work_seconds_completed": 30,
            }],
        },
    )
    assert response.status_code == 201
    saved = client.get(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
    ).get_json()["sessions"][0]["session"]["exercises"][0]
    assert saved["work_seconds_completed"] == 30
    assert "reps_completed" not in saved


def test_time_based_progress_uses_work_duration_trend():
    from training.progress import summarize_progress

    profile = {"profile": {"goal": "mobility"}}
    sessions = [
        {
            "session_date": "2026-10-27",
            "session": {
                "completed": True,
                "exercises": [{"exercise_id": "timed-exercise", "sets_completed": 2, "work_seconds_completed": 20}],
            },
        },
        {
            "session_date": "2026-10-30",
            "session": {
                "completed": True,
                "exercises": [{"exercise_id": "timed-exercise", "sets_completed": 2, "work_seconds_completed": 30}],
            },
        },
    ]
    result = summarize_progress(profile, sessions)
    assert result["exercise_trends"][0]["status"] == "work_duration_increased"



def test_existing_profile_remains_readable_exportable_and_deletable_when_storage_is_disabled(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "false")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "false")

    headers = {"X-Profile-Token": token}
    profile_response = client.get(f"/coach/profile/{profile_id}", headers=headers)
    sessions_response = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers)
    export_response = client.get(f"/coach/profile/{profile_id}/export", headers=headers)
    assert profile_response.status_code == 200
    assert sessions_response.status_code == 200
    assert export_response.status_code == 200

    delete_response = client.delete(f"/coach/profile/{profile_id}", headers=headers)
    assert delete_response.status_code == 200
    missing = client.get(f"/coach/profile/{profile_id}", headers=headers)
    assert missing.status_code == 404


def test_health_consent_can_be_withdrawn_and_erased_when_storage_is_disabled(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, health_consent=True)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    exercise_id = load_catalogue()[0]["id"]
    saved = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
        json={
            "session_date": "2026-11-01",
            "duration_minutes": 45,
            "difficulty": "moderate",
            "completed": True,
            "exercises": [{"exercise_id": exercise_id, "sets_completed": 2, "reps_completed": 8}],
            "discomfort_reported": True,
        },
    )
    assert saved.status_code == 201
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "false")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "false")

    withdrawn = client.post(
        f"/coach/profile/{profile_id}/consent",
        headers={"X-Profile-Token": token},
        json={"health_data_consent": False},
    )
    assert withdrawn.status_code == 200
    sessions = client.get(
        f"/coach/profile/{profile_id}/sessions",
        headers={"X-Profile-Token": token},
    ).get_json()["sessions"]
    assert "discomfort_reported" not in sessions[0]["session"]


def test_new_profile_writes_remain_blocked_when_storage_is_disabled(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "false")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "false")
    response = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "pilot-test-secret"},
        json={
            "profile": {
                "goal": "hypertrophy", "experience": "beginner",
                "equipment": ["bodyweight"], "sessions_per_week": 2,
                "session_minutes": 45, "available_days": [],
            },
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "test-v1",
            "health_data_consent": False,
        },
    )
    assert response.status_code == 503



def test_profile_next_program_is_blocked_when_storage_is_paused(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "false")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "false")
    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 503


def test_new_profiles_persist_canonical_athlete_state(monkeypatch, tmp_path):
    created = _create(_client(monkeypatch, tmp_path))
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]
    saved = created["profile"]["profile"]
    state = saved["athlete_state"]

    assert state["schema_version"] == 1
    assert state["profile_id"] == profile_id
    assert state["goal"]["canonical_goal"] == "strength_muscle"
    assert state["equipment"] == ["barbell", "rack", "dumbbell", "bench"]
    assert state["availability"]["sessions_per_week"] == 2
    assert state["availability"]["session_duration_minutes"] == 60
    assert state["availability"]["available_days"] == ["monday", "thursday"]
    # Legacy False is a default, not evidence that the user cannot perform it.
    assert state["capabilities"]["self_reported"] == {}
    assert state["symptoms"]["status"] == "not_asked"
    assert all(
        item["status"] == "not_assessed"
        for item in state["movement_assessment"]["tasks"].values()
    )

    loaded = _client(monkeypatch, tmp_path).get(
        f"/coach/profile/{profile_id}", headers={"X-Profile-Token": token}
    )
    assert loaded.status_code == 200
    assert loaded.get_json()["profile"]["profile"]["athlete_state"] == state


def test_legacy_profile_is_lazily_migrated_and_persisted_on_authenticated_read(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    from coach_store import create_profile as store_create_profile

    profile_id = "legacy-profile-001"
    token = "legacy-profile-secret-token"
    legacy_profile = {
        "goal": "hypertrophy",
        "experience": "intermediate",
        "equipment": ["barbell", "rack"],
        "sessions_per_week": 2,
        "session_minutes": 60,
        "available_days": ["monday", "thursday"],
        "pistol_squat_capable": False,
    }
    store_create_profile(profile_id, token, legacy_profile, False, "test-v1")

    response = client.get(
        f"/coach/profile/{profile_id}", headers={"X-Profile-Token": token}
    )
    assert response.status_code == 200
    state = response.get_json()["profile"]["profile"]["athlete_state"]
    assert state["schema_version"] == 1
    assert state["symptoms"]["status"] == "not_asked"
    assert all(
        item["status"] == "not_assessed"
        for item in state["movement_assessment"]["tasks"].values()
    )

    conn = sqlite3.connect(tmp_path / "atena-test.sqlite3")
    import json
    persisted = json.loads(conn.execute(
        "SELECT profile_json FROM atena_profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0])
    conn.close()
    assert persisted["athlete_state"] == state


def test_profile_update_preserves_existing_movement_and_symptom_context(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]

    from coach_store import update_profile as store_update_profile
    from training.profile_state_adapter import attach_athlete_state

    original = created["profile"]["profile"]
    stateful = attach_athlete_state(original, profile_id)
    stateful["athlete_state"]["movement_assessment"]["tasks"]["squat"] = {
        "status": "needs_support",
        "source": "observed",
        "recorded_at": "2026-11-06T09:00:00+00:00",
        "note": "potreben je nadzor pri spuščanju",
    }
    stateful["athlete_state"]["symptoms"] = {
        "status": "present_stable",
        "items": [{"location": "koleno", "side": "levo", "provoking_task": "izpadni korak"}],
    }
    store_update_profile(profile_id, token, stateful)

    response = client.put(
        f"/coach/profile/{profile_id}",
        headers={"X-Profile-Token": token},
        json={"profile": {
            "goal": "strength",
            "experience": "intermediate",
            "equipment": ["barbell", "rack"],
            "sessions_per_week": 3,
            "session_minutes": 75,
            "available_days": ["tuesday", "friday"],
        }},
    )
    assert response.status_code == 200
    saved = response.get_json()["profile"]["profile"]
    assert saved["goal"] == "strength"
    assert saved["athlete_state"]["availability"]["sessions_per_week"] == 3
    assert saved["athlete_state"]["movement_assessment"]["tasks"]["squat"]["status"] == "needs_support"
    assert saved["athlete_state"]["movement_assessment"]["tasks"]["squat"]["source"] == "observed"
    assert saved["athlete_state"]["symptoms"]["status"] == "present_stable"
    assert saved["athlete_state"]["symptoms"]["items"][0]["location"] == "koleno"


def test_program_generator_receives_legacy_profile_view_not_canonical_envelope(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    created = _create(client)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]

    import coach_routes
    captured = {}

    def fake_generate(profile, feedback=None):
        captured["profile"] = profile
        return {"goal": profile["goal"], "sessions": []}

    monkeypatch.setattr(coach_routes, "generate_program", fake_generate)
    response = client.post(
        f"/coach/profile/{profile_id}/program",
        headers={"X-Profile-Token": token},
        json={"no_current_pain_or_restrictions": True},
    )
    assert response.status_code == 200
    assert "athlete_state" not in captured["profile"]
    assert captured["profile"]["goal"] == "hypertrophy"


def test_withdrawing_health_consent_erases_canonical_symptom_and_movement_data(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path, health_consent=True)
    created = _create(client, health_consent=True)
    profile_id = created["profile"]["profile_id"]
    token = created["profile_access_token"]

    from coach_store import update_profile as store_update_profile
    from training.profile_state_adapter import attach_athlete_state

    profile = attach_athlete_state(created["profile"]["profile"], profile_id)
    profile["athlete_state"]["symptoms"] = {
        "status": "present_stable",
        "items": [{"location": "rama", "side": "desno", "provoking_task": "potisk nad glavo"}],
    }
    profile["athlete_state"]["movement_assessment"]["tasks"]["overhead_press"] = {
        "status": "needs_support",
        "source": "observed",
        "recorded_at": "2026-11-06T09:00:00+00:00",
        "note": "opazovana omejitev nadzora",
    }
    profile["athlete_state"]["constraints"]["excluded_patterns"] = ["overhead_push"]
    store_update_profile(profile_id, token, profile)

    response = client.post(
        f"/coach/profile/{profile_id}/consent",
        headers={"X-Profile-Token": token},
        json={"health_data_consent": False},
    )
    assert response.status_code == 200
    state = response.get_json()["profile"]["profile"]["athlete_state"]
    assert state["symptoms"] == {"status": "not_asked", "items": []}
    assert state["movement_assessment"]["tasks"]["overhead_press"] == {
        "status": "not_assessed",
        "source": None,
        "recorded_at": None,
        "note": None,
    }
    assert state["constraints"]["excluded_patterns"] == []


def test_profile_update_preserves_explicit_capability_without_inventing_false(monkeypatch, tmp_path):
    from training.profile_state_adapter import attach_athlete_state

    created = _create(_client(monkeypatch, tmp_path))
    profile_id = created["profile"]["profile_id"]
    original = created["profile"]["profile"]
    original["pistol_squat_capable"] = True
    stateful = attach_athlete_state(original, profile_id)
    assert stateful["athlete_state"]["capabilities"]["self_reported"]["pistol_squat"] is True

    edited = {
        "goal": original["goal"],
        "experience": original["experience"],
        "equipment": original["equipment"],
        "sessions_per_week": original["sessions_per_week"],
        "session_minutes": original["session_minutes"],
        "available_days": original["available_days"],
        "pistol_squat_capable": False,
    }
    updated = attach_athlete_state(edited, profile_id, previous_profile=stateful)
    assert updated["athlete_state"]["capabilities"]["self_reported"]["pistol_squat"] is True

    unknown = attach_athlete_state({**edited, "pistol_squat_capable": False}, "new-profile")
    assert unknown["athlete_state"]["capabilities"]["self_reported"] == {}

def test_profile_adaptation_preserves_unknown_feedback_instead_of_inventing_defaults(monkeypatch):
    import coach_routes

    monkeypatch.setattr(
        coach_routes, "assess_next_step",
        lambda _sessions: {"progression_allowed": False, "decision": "collect_context"},
    )
    feedback, guidance = coach_routes._build_profile_adaptation([{
        "session_date": "2026-11-06",
        "session": {"exercises": []},
    }])
    assert feedback is None
    assert guidance["decision"] == "collect_context"


def test_profile_adaptation_never_rewrites_reported_discomfort_as_pain_free(monkeypatch):
    import coach_routes

    monkeypatch.setattr(
        coach_routes, "assess_next_step",
        lambda _sessions: {"progression_allowed": False, "decision": "pause_and_review"},
    )
    feedback, _ = coach_routes._build_profile_adaptation([{
        "session_date": "2026-11-06",
        "session": {"discomfort_reported": True, "completed": False},
    }])
    assert feedback == {"discomfort": "yes", "completed": False}


def test_profile_adaptation_records_pain_free_only_when_explicitly_reported(monkeypatch):
    import coach_routes

    monkeypatch.setattr(
        coach_routes, "assess_next_step",
        lambda _sessions: {"progression_allowed": False, "decision": "collect_context"},
    )
    unknown, _ = coach_routes._build_profile_adaptation([{
        "session_date": "2026-11-06", "session": {"completed": True},
    }])
    explicit_no, _ = coach_routes._build_profile_adaptation([{
        "session_date": "2026-11-06", "session": {
            "completed": True, "discomfort_reported": False,
        },
    }])
    assert unknown == {"completed": True}
    assert explicit_no == {"completed": True, "discomfort": "no"}

def test_unknown_completion_status_requests_context_instead_of_treating_session_as_incomplete():
    from training.adaptation import assess_next_step
    from training.adaptive_decision import decide_adaptation

    history = [{
        "session_date": "2026-11-06",
        "session": {"difficulty": "moderate", "recovery": "normal"},
    }]
    simple = assess_next_step(history)
    detailed = decide_adaptation(history)
    assert simple["decision"] == "collect_context"
    assert simple["reason_codes"] == ["completion_status_unknown"]
    assert detailed["decision"] == "collect_context"
    assert detailed["reason_codes"] == ["completion_status_unknown"]
    assert detailed["automatic_program_changes"] is False


def test_explicitly_incomplete_session_still_triggers_reason_review():
    from training.adaptation import assess_next_step
    from training.adaptive_decision import decide_adaptation

    history = [{
        "session_date": "2026-11-06",
        "session": {"completed": False, "completion_reason": "time_constraint"},
    }]
    simple = assess_next_step(history)
    detailed = decide_adaptation(history)
    assert simple["decision"] == "maintain_and_reschedule"
    assert simple["volume_change"] == "maintain"
    assert detailed["decision"] == "restructure_session"
