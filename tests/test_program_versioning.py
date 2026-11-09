"""End-to-end contract between the real programme generator and immutable snapshots."""
from flask import Flask

from coach_routes import coach_bp
from coach_store import get_program_version, list_program_versions, save_program_version
from training.program_context import generate_program_for_athlete
from uuid import uuid4
from datetime import datetime, timezone


def _pilot(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_COACH_TEST_TOKEN", "program-version-test-secret")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_VERSION", "program-v1")
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATABASE_URL", f"sqlite:///{tmp_path / 'program-version.sqlite3'}")
    app = Flask(__name__)
    app.register_blueprint(coach_bp)
    return app.test_client()


def test_real_generated_program_is_saved_as_an_exact_immutable_version(monkeypatch, tmp_path):
    client = _pilot(monkeypatch, tmp_path)
    created = client.post(
        "/coach/profile",
        headers={"X-Pilot-Token": "program-version-test-secret"},
        json={
            "privacy_notice_acknowledged": True,
            "privacy_notice_version": "program-v1",
            "health_data_consent": False,
            "profile": {
                "goal": "hypertrophy",
                "experience": "intermediate",
                "equipment": ["dumbbell", "bench", "bodyweight"],
                "sessions_per_week": 2,
                "session_minutes": 60,
                "available_days": ["monday", "thursday"],
            },
        },
    )
    assert created.status_code == 201
    profile_id = created.get_json()["profile"]["profile_id"]
    token = created.get_json()["profile_access_token"]
    headers = {"X-Profile-Token": token}

    loaded = client.get(f"/coach/profile/{profile_id}", headers=headers)
    assert loaded.status_code == 200
    profile = loaded.get_json()["profile"]["profile"]
    program = generate_program_for_athlete(profile)
    assert len(program["sessions"]) == 2

    version_id = str(uuid4())
    event = {
        "schema_version": 1,
        "event_id": str(uuid4()),
        "profile_id": profile_id,
        "event_type": "program_created",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "source": "system",
        "data_classification": "operational",
        "program_version_id": version_id,
        "payload": {
            "goal": profile["goal"],
            "experience": profile["experience"],
            "session_count": len(program["sessions"]),
        },
    }
    saved = save_program_version(
        profile_id,
        token,
        version_id,
        program,
        goal=profile["goal"],
        experience=profile["experience"],
        data_classification="operational",
        event=event,
        generation_context={"source_session_ids": [], "adaptive_decision": {"decision": "collect_baseline"}},
    )

    assert saved["version_number"] == 1
    assert saved["program"] == program
    assert saved["generation_context"]["adaptive_decision"]["decision"] == "collect_baseline"
    assert list_program_versions(profile_id, token)[0]["program_version_id"] == version_id
    exact = get_program_version(profile_id, token, version_id)
    assert exact["program"] == program
    assert exact["generation_context"] == saved["generation_context"]
