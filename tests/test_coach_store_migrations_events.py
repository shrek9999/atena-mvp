import json
import sqlite3

import pytest

import coach_store
from coach_store import (
    DecisionEventError,
    append_decision_event,
    create_profile,
    get_profile,
    list_decision_events,
    set_health_data_consent,
    add_program_version,
    list_program_versions,
)


def configure_sqlite(monkeypatch, tmp_path):
    database = tmp_path / "atena-test.sqlite3"
    monkeypatch.setenv("ATENA_DATABASE_URL", "sqlite:///" + str(database))
    monkeypatch.setenv("ATENA_ALLOW_SQLITE_STORAGE", "true")
    monkeypatch.setenv("ATENA_DATA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("ATENA_PRIVACY_NOTICE_APPROVED", "true")
    return database


def event(profile_id, *, event_id="evt-001", event_type="session_completed",
          classification="operational", payload=None):
    return {
        "schema_version": 1,
        "event_id": event_id,
        "profile_id": profile_id,
        "event_type": event_type,
        "occurred_at": "2026-11-07T10:15:00+01:00",
        "source": "user",
        "data_classification": classification,
        "payload": payload or {"completed": True},
    }


def test_migrations_are_versioned_idempotent_and_use_text_json(monkeypatch, tmp_path):
    database = configure_sqlite(monkeypatch, tmp_path)
    create_profile("profile-1", "a-long-random-test-token", {"name": "Test"}, False, "v1")
    profile = get_profile("profile-1", "a-long-random-test-token")
    assert profile["profile"] == {"name": "Test"}

    conn = sqlite3.connect(database)
    try:
        versions = conn.execute(
            "SELECT version FROM atena_schema_migrations ORDER BY version"
        ).fetchall()
        assert versions == [(1,), (2,), (3,)]
        assert conn.execute(
            "SELECT COUNT(*) FROM atena_decision_events"
        ).fetchone()[0] == 0
        # Re-running the initializer must not create duplicate migration rows.
        coach_store._init(conn, "sqlite")
        versions_after = conn.execute(
            "SELECT version FROM atena_schema_migrations ORDER BY version"
        ).fetchall()
        assert versions_after == versions
    finally:
        conn.close()


def test_existing_profile_and_session_schema_is_adopted_without_data_loss(monkeypatch, tmp_path):
    database = configure_sqlite(monkeypatch, tmp_path)
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE atena_profiles (
            profile_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
            profile_json TEXT NOT NULL, privacy_notice_version TEXT NOT NULL,
            privacy_acknowledged INTEGER NOT NULL, health_data_consent INTEGER NOT NULL,
            health_data_consent_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE atena_training_sessions (
            session_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES atena_profiles(profile_id) ON DELETE CASCADE,
            session_date TEXT NOT NULL, session_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX atena_sessions_profile_date
            ON atena_training_sessions(profile_id, session_date);
    """)
    now = "2026-11-07T10:00:00+00:00"
    conn.execute(
        """INSERT INTO atena_profiles
        (profile_id, token_hash, profile_json, privacy_notice_version,
         privacy_acknowledged, health_data_consent, health_data_consent_at,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("profile-legacy", coach_store.hash_access_token("legacy-token"),
         json.dumps({"legacy": True}), "v1", 1, 0, None, now, now),
    )
    conn.execute(
        """INSERT INTO atena_training_sessions
        (session_id, profile_id, session_date, session_json, created_at)
        VALUES (?, ?, ?, ?, ?)""",
        ("session-1", "profile-legacy", "2026-11-07",
         json.dumps({"completed": True}), now),
    )
    conn.commit()
    conn.close()

    profile = get_profile("profile-legacy", "legacy-token")
    assert profile["profile"] == {"legacy": True}

    conn = sqlite3.connect(database)
    try:
        assert conn.execute(
            "SELECT session_json FROM atena_training_sessions WHERE session_id = ?",
            ("session-1",),
        ).fetchone()[0] == '{"completed": true}'
        assert conn.execute(
            "SELECT MAX(version) FROM atena_schema_migrations"
        ).fetchone()[0] == 3
    finally:
        conn.close()


def test_operational_event_is_persisted_and_returned_in_order(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "another-long-random-test-token"
    create_profile("profile-2", token, {}, False, "v1")
    saved = append_decision_event(
        "profile-2", token, event("profile-2", payload={"completed": True})
    )
    history = list_decision_events("profile-2", token)
    assert saved["event"]["event_id"] == "evt-001"
    assert len(history) == 1
    assert history[0]["event"]["payload"] == {"completed": True}


def test_health_sensitive_event_requires_explicit_profile_consent(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "health-consent-test-token"
    create_profile("profile-3", token, {}, False, "v1")
    with pytest.raises(DecisionEventError, match="privolitev"):
        append_decision_event(
            "profile-3", token,
            event("profile-3", event_type="symptom_context_recorded",
                  classification="health_sensitive", payload={"location": "knee"}),
        )
    assert list_decision_events("profile-3", token) == []


def test_health_sensitive_event_type_cannot_be_misclassified(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "health-consent-test-token-2"
    create_profile("profile-4", token, {}, True, "v1")
    with pytest.raises(DecisionEventError, match="zdravstveno občutljiva"):
        append_decision_event(
            "profile-4", token,
            event("profile-4", event_type="movement_assessment_recorded",
                  classification="operational"),
        )


def test_consent_withdrawal_erases_health_sensitive_events_but_keeps_operational_history(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "withdraw-consent-token"
    create_profile("profile-5", token, {}, True, "v1")
    append_decision_event(
        "profile-5", token,
        event("profile-5", event_id="evt-op", event_type="session_completed"),
    )
    append_decision_event(
        "profile-5", token,
        event("profile-5", event_id="evt-health",
              event_type="symptom_context_recorded",
              classification="health_sensitive",
              payload={"location": "knee", "trend": "stable"}),
    )

    set_health_data_consent("profile-5", token, False)
    history = list_decision_events("profile-5", token)
    assert [item["event"]["event_id"] for item in history] == ["evt-op"]


def test_event_cannot_be_written_to_another_profile(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "profile-binding-test-token"
    create_profile("profile-6", token, {}, False, "v1")
    with pytest.raises(DecisionEventError, match="ne pripada"):
        append_decision_event("profile-6", token, event("different-profile"))


def test_event_history_is_deleted_with_profile(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "profile-delete-test-token"
    create_profile("profile-7", token, {}, False, "v1")
    append_decision_event("profile-7", token, event("profile-7"))
    from coach_store import delete_profile
    delete_profile("profile-7", token)
    with pytest.raises(coach_store.ProfileNotFound):
        list_decision_events("profile-7", token)


def test_session_save_and_event_log_commit_together(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "session-event-atomic-test-token"
    create_profile("profile-8", token, {}, False, "v1")
    from coach_store import add_session
    saved = add_session(
        "profile-8", token, "session-8", "2026-11-07",
        {"completed": True, "duration_minutes": 42, "exercises": [{"exercise_id": "squat"}]},
    )
    assert saved["session_id"] == "session-8"
    history = list_decision_events("profile-8", token)
    assert len(history) == 1
    assert history[0]["event"]["event_type"] == "session_completed"
    assert history[0]["event"]["payload"]["session_id"] == "session-8"
    assert history[0]["event"]["payload"]["exercise_count"] == 1


def test_program_version_is_saved_with_hash_decision_and_history(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "program-version-test-token"
    create_profile("profile-9", token, {}, False, "v1")
    saved = add_program_version(
        "profile-9", token, "program-v1",
        {"goal": "strength", "sessions": [{"exercises": ["squat"]}]},
        {"adaptive_decision": {"decision": "maintain_and_monitor"}},
        athlete_state_version=1,
    )
    assert len(saved["program_hash"]) == 64
    history = list_program_versions("profile-9", token)
    assert len(history) == 1
    assert history[0]["program_version_id"] == "program-v1"
    assert history[0]["program"]["goal"] == "strength"
    events = list_decision_events("profile-9", token)
    assert events[-1]["event"]["event_type"] == "program_created"


def test_program_created_from_health_context_requires_consent(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "program-health-consent-token"
    create_profile("profile-10", token, {}, False, "v1")
    with pytest.raises(DecisionEventError, match="privolitev"):
        add_program_version(
            "profile-10", token, "program-health-v1", {"sessions": []}, {},
            health_context_used=True,
        )


def test_consent_withdrawal_erases_programs_derived_from_health_context_only(monkeypatch, tmp_path):
    configure_sqlite(monkeypatch, tmp_path)
    token = "program-withdraw-consent-token"
    create_profile("profile-11", token, {}, True, "v1")
    add_program_version(
        "profile-11", token, "program-general", {"goal": "strength"}, {},
        health_context_used=False,
    )
    add_program_version(
        "profile-11", token, "program-health", {"goal": "functional", "adapted": True}, {},
        health_context_used=True,
    )
    set_health_data_consent("profile-11", token, False)
    history = list_program_versions("profile-11", token)
    assert [item["program_version_id"] for item in history] == ["program-general"]
    events = list_decision_events("profile-11", token)
    assert all(item["event"]["data_classification"] == "operational" for item in events)
