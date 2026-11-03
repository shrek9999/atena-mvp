"""End-to-end lifecycle test for the authenticated ATENA pilot profile."""
import hashlib
import sqlite3

from flask import Flask

from coach_routes import coach_bp
from training.catalogue import load_catalogue


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "pilot-lifecycle-test-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "lifecycle-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'lifecycle.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client(), tmp_path / "lifecycle.sqlite3"


def test_complete_profile_lifecycle_create_update_log_review_export_withdraw_delete(monkeypatch, tmp_path):
    client, database = _app(monkeypatch, tmp_path)
    pilot_headers = {"X-Pilot-Token": "pilot-lifecycle-test-secret"}
    created = client.post(
        "/coach/profile",
        headers=pilot_headers,
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "lifecycle-v1",
            "health_data_consent": True,
            "profile": {
                "goal": "strength_hypertrophy",
                "experience": "intermediate",
                "equipment": ["barbell", "rack", "dumbbell", "bench", "bodyweight"],
                "sessions_per_week": 2,
                "session_minutes": 60,
                "available_days": ["monday", "thursday"],
            },
        },
    )
    assert created.status_code == 201
    profile = created.get_json()["profile"]
    profile_id = profile["profile_id"]
    access_token = created.get_json()["profile_access_token"]
    headers = {"X-Profile-Token": access_token}

    # Only a hash of the one-time access token may be persisted.
    conn = sqlite3.connect(database)
    token_hash = conn.execute(
        "SELECT token_hash FROM atena_profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0]
    conn.close()
    assert token_hash == hashlib.sha256(access_token.encode()).hexdigest()
    assert token_hash != access_token

    # Authenticated profile read and update.
    assert client.get(f"/coach/profile/{profile_id}", headers=headers).status_code == 200
    updated = client.put(
        f"/coach/profile/{profile_id}",
        headers=headers,
        json={"profile": {
            "goal": "strength",
            "experience": "intermediate",
            "equipment": ["barbell", "rack", "dumbbell", "bench", "bodyweight"],
            "sessions_per_week": 2,
            "session_minutes": 60,
            "available_days": ["tuesday", "friday"],
        }},
    )
    assert updated.status_code == 200
    assert updated.get_json()["profile"]["profile"]["goal"] == "strength"

    exercise_id = load_catalogue()[0]["id"]
    logged = client.post(
        f"/coach/profile/{profile_id}/sessions",
        headers=headers,
        json={
            "session_date": "2026-11-02",
            "duration_minutes": 52,
            "difficulty": "moderate",
            "recovery": "good",
            "completed": True,
            "exercises": [{
                "exercise_id": exercise_id,
                "planned_sets": 3,
                "target_reps_min": 8,
                "target_reps_max": 12,
                "execution_quality": "controlled",
                "set_results": [
                    {"reps": 10, "load_kg": 40, "rir": 3},
                    {"reps": 10, "load_kg": 40, "rir": 3},
                    {"reps": 9, "load_kg": 40, "rir": 2},
                ],
            }],
            "conditioning": [{
                "modality": "aerobic_base",
                "protocol_id": "zone2-bike-30",
                "work_seconds": 1800,
                "duration_seconds": 2100,
                "intervals_completed": 1,
                "rpe": 4,
                "distance_m": 12000,
                "average_heart_rate": 132,
            }],
            "discomfort_reported": True,
        },
    )
    assert logged.status_code == 201
    assert logged.get_json()["session"]["session"]["conditioning"][0]["modality"] == "aerobic_base"

    # Wrong credentials never reveal the profile, history, progress, or export.
    wrong = {"X-Profile-Token": "not-the-profile-token"}
    for suffix in ("", "/sessions", "/progress", "/adaptation", "/export"):
        method = client.get(f"/coach/profile/{profile_id}{suffix}", headers=wrong)
        assert method.status_code == 404

    history = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers)
    assert history.status_code == 200
    assert len(history.get_json()["sessions"]) == 1

    progress = client.get(f"/coach/profile/{profile_id}/progress", headers=headers)
    assert progress.status_code == 200
    progress_data = progress.get_json()
    assert progress_data["source"] == "recorded_training_history"
    assert progress_data["automatic_load_changes"] is False
    assert progress_data["proactive_checkin"]["status"] == "symptom_follow_up"
    assert progress_data["longitudinal_response"]["status"] == "building_baseline"
    assert progress_data["longitudinal_response"]["automatic_program_changes"] is False
    assert progress_data["conditioning_progression"]

    adaptation = client.get(f"/coach/profile/{profile_id}/adaptation", headers=headers)
    assert adaptation.status_code == 200
    assert adaptation.get_json()["automatic_program_changes"] is False

    # A current, explicit safety confirmation is required before generating the next programme.
    blocked = client.post(
        f"/coach/profile/{profile_id}/program",
        headers=headers,
        json={"no_current_pain_or_restrictions": False},
    )
    assert blocked.status_code == 409
    assert blocked.get_json()["blocked"] is True

    allowed = client.post(
        f"/coach/profile/{profile_id}/program",
        headers=headers,
        json={"no_current_pain_or_restrictions": True},
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["source"] == "saved_profile_and_exercise_level_training_feedback"
    assert allowed.get_json()["pilot"] is True

    exported = client.get(f"/coach/profile/{profile_id}/export", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["Cache-Control"] == "no-store, private"
    assert "attachment" in exported.headers["Content-Disposition"]
    export_data = exported.get_json()
    assert export_data["export_version"] == "1.0"
    assert len(export_data["sessions"]) == 1
    assert export_data["sessions"][0]["session"]["discomfort_reported"] is True

    # Consent withdrawal must erase previously stored discomfort flags, not the workout itself.
    withdrawn = client.post(
        f"/coach/profile/{profile_id}/consent",
        headers=headers,
        json={"health_data_consent": False},
    )
    assert withdrawn.status_code == 200
    assert withdrawn.get_json()["profile"]["health_data_consent"] is False
    after_withdrawal = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers)
    saved_session = after_withdrawal.get_json()["sessions"][0]["session"]
    assert "discomfort_reported" not in saved_session
    assert saved_session["exercises"]
    assert saved_session["conditioning"]

    safe_export = client.get(f"/coach/profile/{profile_id}/export", headers=headers)
    assert safe_export.status_code == 200
    assert "discomfort_reported" not in str(safe_export.get_json())

    # Deletion is authenticated and cascades to the stored training history.
    denied_delete = client.delete(f"/coach/profile/{profile_id}", headers=wrong)
    assert denied_delete.status_code == 404
    deleted = client.delete(f"/coach/profile/{profile_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.get_json()["deleted"] is True
    assert client.get(f"/coach/profile/{profile_id}", headers=headers).status_code == 404

    conn = sqlite3.connect(database)
    remaining_profiles = conn.execute(
        "SELECT COUNT(*) FROM atena_profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0]
    remaining_sessions = conn.execute(
        "SELECT COUNT(*) FROM atena_training_sessions WHERE profile_id = ?", (profile_id,)
    ).fetchone()[0]
    conn.close()
    assert remaining_profiles == 0
    assert remaining_sessions == 0


def test_two_recorded_training_exposures_flow_into_progress_review_and_next_program(monkeypatch, tmp_path):
    client, _database = _app(monkeypatch, tmp_path)
    pilot_headers = {"X-Pilot-Token": "pilot-lifecycle-test-secret"}
    created = client.post(
        "/coach/profile",
        headers=pilot_headers,
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "lifecycle-v1",
            "health_data_consent": False,
            "profile": {
                "goal": "strength_hypertrophy",
                "experience": "beginner",
                "equipment": ["dumbbell"],
                "sessions_per_week": 2,
                "session_minutes": 60,
                "available_days": ["monday", "thursday"],
            },
        },
    )
    assert created.status_code == 201
    profile_id = created.get_json()["profile"]["profile_id"]
    headers = {"X-Profile-Token": created.get_json()["profile_access_token"]}

    def log_exposure(day, reps):
        return client.post(
            f"/coach/profile/{profile_id}/sessions",
            headers=headers,
            json={
                "session_date": day,
                "duration_minutes": 55,
                "difficulty": "moderate",
                "recovery": "good",
                "completed": True,
                "exercises": [{
                    "exercise_id": "squat_goblet",
                    "planned_sets": 3,
                    "target_reps_min": 8,
                    "target_reps_max": 12,
                    "execution_quality": "controlled",
                    "set_results": [
                        {"reps": value, "load_kg": 20, "rir": reserve}
                        for value, reserve in zip(reps, (4, 4, 3))
                    ],
                }],
            },
        )

    first = log_exposure("2026-10-29", (12, 12, 12))
    second = log_exposure("2026-11-02", (12, 12, 12))
    assert first.status_code == 201
    assert second.status_code == 201

    history = client.get(f"/coach/profile/{profile_id}/sessions", headers=headers)
    assert history.status_code == 200
    assert [row["session_date"] for row in history.get_json()["sessions"]] == [
        "2026-11-02", "2026-10-29"
    ]

    progress = client.get(f"/coach/profile/{profile_id}/progress", headers=headers)
    assert progress.status_code == 200
    progress_data = progress.get_json()
    squat_progression = next(
        item for item in progress_data["exercise_progressions"]
        if item["exercise_id"] == "squat_goblet"
    )
    assert squat_progression["decision"] == "increase_load"
    assert squat_progression["recent_load_kg"] == 20
    assert progress_data["automatic_load_changes"] is False

    # A new programme is generated only after explicit current-safety confirmation.
    next_program = client.post(
        f"/coach/profile/{profile_id}/program",
        headers=headers,
        json={"no_current_pain_or_restrictions": True},
    )
    assert next_program.status_code == 200
    result = next_program.get_json()
    assert result["source"] == "saved_profile_and_exercise_level_training_feedback"
    assert result["pilot"] is True
    assert result["exercise_progressions"] == progress_data["exercise_progressions"]
    assert result["training_cycle"]["automatic_program_changes"] is False

    # The recorded exercise recommendation is carried into the next plan when
    # that same exercise is selected; no external load is invented or applied.
    planned = [
        exercise
        for session in result["program"]["sessions"]
        for exercise in session["exercises"]
        if exercise["exercise_id"] == "squat_goblet"
    ]
    if planned:
        progression = planned[0]["prescription"].get("exercise_progression", {})
        assert progression.get("decision") == "increase_load"
        assert progression.get("automatic_load_change") is False
