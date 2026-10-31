"""SQLite-backed profile and training-history storage for the ATENA pilot.

The database path is configurable with ATENA_DATABASE_PATH. The default path is
local to the application and is suitable for development/tests, not durable
Render storage unless it is mapped to a persistent volume.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from training.program import validate_profile

PROFILE_FIELDS = {
    "goal", "experience", "equipment", "sessions_per_week", "session_minutes",
    "excluded_exercise_ids", "excluded_patterns", "include_accessories",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _database_path() -> str:
    configured = os.getenv("ATENA_DATABASE_PATH", "data/atena.sqlite3").strip()
    if configured == ":memory:":
        return configured
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(_database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    try:
        _initialize(connection)
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            profile_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS programs (
            program_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
            program_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workout_logs (
            workout_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
            program_id TEXT NOT NULL REFERENCES programs(program_id),
            session_number INTEGER NOT NULL,
            duration_minutes INTEGER,
            completed INTEGER NOT NULL,
            feedback_json TEXT NOT NULL,
            exercises_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS check_ins (
            check_in_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
            feedback_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_programs_profile_created
            ON programs(profile_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_workouts_profile_created
            ON workout_logs(profile_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_checkins_profile_created
            ON check_ins(profile_id, created_at DESC);
        """
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def normalize_profile(profile: object) -> dict:
    """Validate and retain only the small, supported training-profile schema."""
    normalized = validate_profile(profile)
    result = {key: normalized[key] for key in PROFILE_FIELDS if key in normalized}
    result["equipment"] = sorted(set(result["equipment"]))
    result["excluded_exercise_ids"] = sorted(set(result.get("excluded_exercise_ids", [])))
    result["excluded_patterns"] = sorted(set(result.get("excluded_patterns", [])))
    return result


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_profile(profile: object) -> dict:
    normalized = normalize_profile(profile)
    profile_id = uuid.uuid4().hex
    profile_token = secrets.token_urlsafe(32)
    timestamp = _now()
    with _connection() as connection:
        connection.execute(
            "INSERT INTO profiles(profile_id, token_hash, profile_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (profile_id, _token_hash(profile_token), _json(normalized), timestamp, timestamp),
        )
    # The raw profile token is returned once and is never stored.
    return {"profile_id": profile_id, "profile_token": profile_token, "profile": normalized}


def get_profile_by_token(profile_token: str) -> dict | None:
    if not isinstance(profile_token, str) or not 20 <= len(profile_token) <= 200:
        return None
    with _connection() as connection:
        row = connection.execute(
            "SELECT profile_id, profile_json, created_at, updated_at FROM profiles WHERE token_hash = ?",
            (_token_hash(profile_token),),
        ).fetchone()
    if row is None:
        return None
    return {
        "profile_id": row["profile_id"],
        "profile": json.loads(row["profile_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def update_profile(profile_id: str, profile: object) -> dict:
    normalized = normalize_profile(profile)
    timestamp = _now()
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE profiles SET profile_json = ?, updated_at = ? WHERE profile_id = ?",
            (_json(normalized), timestamp, profile_id),
        )
        if cursor.rowcount != 1:
            return None
    return {"profile_id": profile_id, "profile": normalized, "updated_at": timestamp}


def save_program(profile_id: str, program: dict) -> str:
    program_id = uuid.uuid4().hex
    with _connection() as connection:
        connection.execute(
            "INSERT INTO programs(program_id, profile_id, program_json, created_at) VALUES (?, ?, ?, ?)",
            (program_id, profile_id, _json(program), _now()),
        )
    return program_id


def get_program(profile_id: str, program_id: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT program_json, created_at FROM programs WHERE profile_id = ? AND program_id = ?",
            (profile_id, program_id),
        ).fetchone()
    if row is None:
        return None
    return {"program": json.loads(row["program_json"]), "created_at": row["created_at"]}


def list_programs(profile_id: str, limit: int = 20) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute(
            "SELECT program_id, program_json, created_at FROM programs "
            "WHERE profile_id = ? ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
    return [
        {"program_id": row["program_id"], "program": json.loads(row["program_json"]), "created_at": row["created_at"]}
        for row in rows
    ]


def save_workout(
    profile_id: str,
    program_id: str,
    session_number: int,
    duration_minutes: int | None,
    feedback: dict,
    exercises: list[dict],
) -> dict:
    workout_id = uuid.uuid4().hex
    timestamp = _now()
    with _connection() as connection:
        connection.execute(
            """INSERT INTO workout_logs(
                workout_id, profile_id, program_id, session_number, duration_minutes,
                completed, feedback_json, exercises_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                workout_id, profile_id, program_id, session_number, duration_minutes,
                int(feedback["completed"]), _json(feedback), _json(exercises), timestamp,
            ),
        )
    return {"workout_id": workout_id, "created_at": timestamp}


def list_workouts(profile_id: str, limit: int = 30) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute(
            """SELECT workout_id, program_id, session_number, duration_minutes, completed,
                      feedback_json, exercises_json, created_at
               FROM workout_logs WHERE profile_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (profile_id, limit),
        ).fetchall()
    return [
        {
            "workout_id": row["workout_id"],
            "program_id": row["program_id"],
            "session": row["session_number"],
            "duration_minutes": row["duration_minutes"],
            "completed": bool(row["completed"]),
            "feedback": json.loads(row["feedback_json"]),
            "exercises": json.loads(row["exercises_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def save_check_in(profile_id: str, feedback: dict) -> dict:
    check_in_id = uuid.uuid4().hex
    timestamp = _now()
    with _connection() as connection:
        connection.execute(
            "INSERT INTO check_ins(check_in_id, profile_id, feedback_json, created_at) VALUES (?, ?, ?, ?)",
            (check_in_id, profile_id, _json(feedback), timestamp),
        )
    return {"check_in_id": check_in_id, "created_at": timestamp}


def latest_feedback(profile_id: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            """SELECT feedback_json FROM (
                   SELECT feedback_json, created_at FROM workout_logs WHERE profile_id = ?
                   UNION ALL
                   SELECT feedback_json, created_at FROM check_ins WHERE profile_id = ?
               ) ORDER BY created_at DESC LIMIT 1""",
            (profile_id, profile_id),
        ).fetchone()
    return json.loads(row["feedback_json"]) if row else None
