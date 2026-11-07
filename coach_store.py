"""Privacy-conscious, opt-in profile and training-history storage.

PostgreSQL is the only supported hosted store. SQLite is deliberately limited to
explicit local/test use; Render free services have ephemeral filesystems.
Storage remains disabled unless ATENA_DATA_STORAGE_ENABLED=true and
ATENA_PRIVACY_NOTICE_APPROVED=true are both configured by the operator.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit

from training.decision_event import DecisionEventError, validate_decision_event


def _normalize_supabase_pooler_username(url: str) -> str:
    """Normalize shared Supabase pooler credentials without exposing or changing the password."""
    try:
        scheme, separator, remainder = url.partition("://")
        if not separator:
            return url
        # Parse the user-info boundary using the known Supabase pooler host suffix.
        # This remains robust when a password contains URI-reserved characters such as [ ] / ? # @.
        suffix = ".pooler.supabase.com"
        suffix_at = remainder.lower().find(suffix)
        if suffix_at >= 0:
            at_sign = remainder.rfind("@", 0, suffix_at)
            if at_sign < 0:
                return url
            raw_userinfo = remainder[:at_sign]
            host_and_rest = remainder[at_sign + 1:]
            raw_username, colon, raw_password = raw_userinfo.partition(":")
            username = unquote(raw_username)
            project_ref = os.getenv("ATENA_SUPABASE_PROJECT_REF", "gxgmxvtfkhjfpbtfmmcs").strip()
            if username == "postgres" and project_ref:
                username = "postgres." + project_ref
            encoded_user = quote(username, safe=".")
            if colon:
                # Decode then encode once so already-escaped passwords are not double-encoded.
                encoded_password = quote(unquote(raw_password), safe="")
                userinfo = encoded_user + ":" + encoded_password
            else:
                userinfo = encoded_user
            return scheme + "://" + userinfo + "@" + host_and_rest

        # For non-pooler PostgreSQL URLs, leave the URI unchanged.
        parsed = urlsplit(url)
        return url
    except (TypeError, ValueError):
        return url


class StorageUnavailable(RuntimeError):
    def __init__(self, message: str, reason: str = "storage_unavailable"):
        super().__init__(message)
        self.reason = reason

class ProfileNotFound(RuntimeError):
    pass

def storage_enabled():
    """True only when the operator has explicitly enabled storage and approved the notice."""
    return (
        os.getenv("ATENA_DATA_STORAGE_ENABLED", "").strip().lower() == "true"
        and os.getenv("ATENA_PRIVACY_NOTICE_APPROVED", "").strip().lower() == "true"
        and bool(os.getenv("ATENA_DATABASE_URL", "").strip())
    )


def _config(require_enabled=True):
    url = os.getenv("ATENA_DATABASE_URL", "").strip()
    if not url:
        raise StorageUnavailable("Profile database is not configured.")
    if require_enabled:
        enabled = os.getenv("ATENA_DATA_STORAGE_ENABLED", "").strip().lower() == "true"
        notice_approved = os.getenv("ATENA_PRIVACY_NOTICE_APPROVED", "").strip().lower() == "true"
        if not enabled or not notice_approved:
            raise StorageUnavailable("Profile storage is not enabled or approved.")
    return url

def _set_application_role(conn):
    """Restrict the current transaction to the non-login Coach database role."""
    with conn.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE atena_app")


def _connect(require_enabled=True):
    url = _config(require_enabled=require_enabled)
    if url.startswith("sqlite:///"):
        if os.getenv("ATENA_ALLOW_SQLITE_STORAGE", "").strip().lower() != "true":
            raise StorageUnavailable("SQLite is restricted to explicit local/test use.")
        path = url[len("sqlite:///"):]
        if not path:
            raise StorageUnavailable("SQLite database path is missing.")
        conn = sqlite3.connect(path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn, "sqlite"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        raise StorageUnavailable("Only PostgreSQL is supported for hosted storage.")
    try:
        import psycopg
    except ImportError as exc:
        raise StorageUnavailable("PostgreSQL driver is not installed.") from exc
    url = _normalize_supabase_pooler_username(url)
    try:
        conn = psycopg.connect(url, connect_timeout=8)
        try:
            # Use a dedicated NOLOGIN, NOBYPASSRLS application role. The role
            # is provisioned by the reviewed Supabase migration; the postgres
            # login is only the transport identity and must not run app queries.
            _set_application_role(conn)
            return conn, "postgres"
        except Exception as exc:
            conn.close()
            raise _classify_database_error(exc) from exc
    except StorageUnavailable:
        raise
    except Exception as exc:
        raise _classify_database_error(exc) from exc

def _classify_database_error(exc):
    """Map driver failures to safe categories; never expose connection details."""
    sqlstate = getattr(exc, "sqlstate", None)
    message = str(exc).lower()
    if sqlstate in ("28P01", "28000"):
        reason = "database_authentication_failed"
    elif sqlstate == "57P03":
        reason = "database_temporarily_unavailable"
    elif sqlstate and sqlstate.startswith("08"):
        reason = "database_network_connection_failed"
    elif sqlstate in {"42P01", "42703", "42804", "42883", "42704"}:
        reason = "database_schema_mismatch"
    elif sqlstate == "23505":
        reason = "database_record_conflict"
    elif "could not translate host name" in message or "name or service not known" in message or "temporary failure in name resolution" in message:
        reason = "database_dns_resolution_failed"
    elif "timeout" in message or "timed out" in message:
        reason = "database_connection_timeout"
    elif "connection refused" in message:
        reason = "database_connection_refused"
    elif "ssl" in message or "tls" in message or "certificate" in message:
        reason = "database_tls_configuration_failed"
    else:
        reason = "database_operation_failed"
    return StorageUnavailable("Database operation failed.", reason)


def _execute(conn, dialect, sql, params=()):
    statement = sql.replace("%s", "?") if dialect == "sqlite" else sql
    try:
        return conn.execute(statement, params)
    except StorageUnavailable:
        raise
    except Exception as exc:
        if dialect == "postgres":
            raise _classify_database_error(exc) from exc
        raise


def _encode_json(value, dialect):
    """Use psycopg's native JSONB adapter for hosted PostgreSQL."""
    if dialect == "postgres":
        from psycopg.types.json import Jsonb
        return Jsonb(value)
    return json.dumps(value, ensure_ascii=False)


def _decode_json(value):
    """psycopg returns decoded JSONB values; SQLite returns serialized text."""
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    return value

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _init(conn, dialect):
    """Initialize only disposable local SQLite stores.

    Hosted PostgreSQL schema is managed exclusively through reviewed migrations.
    Request handlers must never perform DDL or change grants/privileges.
    """
    if dialect != "sqlite":
        return
    statements = [
        """CREATE TABLE IF NOT EXISTS atena_profiles (
            profile_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL,
            profile_json TEXT NOT NULL,
            privacy_notice_version TEXT NOT NULL,
            privacy_acknowledged INTEGER NOT NULL,
            health_data_consent INTEGER NOT NULL,
            health_data_consent_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS atena_training_sessions (
            session_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES atena_profiles(profile_id) ON DELETE CASCADE,
            session_date TEXT NOT NULL,
            session_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS atena_decision_events (
            event_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES atena_profiles(profile_id) ON DELETE CASCADE,
            schema_version INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            source TEXT NOT NULL,
            data_classification TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            program_version_id TEXT,
            correlation_id TEXT,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS atena_sessions_profile_date ON atena_training_sessions(profile_id, session_date)",
        "CREATE INDEX IF NOT EXISTS atena_events_profile_occurred ON atena_decision_events(profile_id, occurred_at)",
    ]
    for statement in statements:
        _execute(conn, dialect, statement)


def check_database_connection():
    """Verify hosted PostgreSQL reachability without enabling or creating user-data tables."""
    url = os.getenv("ATENA_DATABASE_URL", "").strip()
    if not url:
        raise StorageUnavailable("Database connection string is not configured.", "missing_url")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql://"):
        raise StorageUnavailable("Hosted database must use PostgreSQL.", "unsupported_scheme")
    try:
        import psycopg
    except ImportError as exc:
        raise StorageUnavailable("PostgreSQL driver is not installed.", "driver_missing") from exc
    url = _normalize_supabase_pooler_username(url)
    try:
        with psycopg.connect(url, connect_timeout=8) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
        if not row or row[0] != 1:
            raise StorageUnavailable("Database connectivity check returned an unexpected result.")
        return True
    except StorageUnavailable:
        raise
    except Exception as exc:
        # Return only a safe failure category. Never expose driver text, host,
        # username, password, connection URI, or raw exception details.
        sqlstate = getattr(exc, "sqlstate", None)
        error_type = type(exc).__name__.lower()
        error_text = str(exc).lower()
        if sqlstate in ("28P01", "28000"):
            reason = "database_authentication_failed"
        elif sqlstate == "57P03":
            reason = "database_temporarily_unavailable"
        elif sqlstate and sqlstate.startswith("08"):
            reason = "database_network_connection_failed"
        elif "could not translate host name" in error_text or "name or service not known" in error_text or "temporary failure in name resolution" in error_text:
            reason = "database_dns_resolution_failed"
        elif "timeout" in error_text or "timed out" in error_text or "connection timeout" in error_text:
            reason = "database_connection_timeout"
        elif "connection refused" in error_text:
            reason = "database_connection_refused"
        elif "ssl" in error_text or "tls" in error_text or "certificate" in error_text:
            reason = "database_tls_configuration_failed"
        elif error_type in {"valueerror", "interfaceerror", "operationalerror"}:
            reason = "database_connection_configuration_failed"
        else:
            reason = "database_connection_failed"
        raise StorageUnavailable("Database connection check failed.", reason) from exc


def hash_access_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_profile(profile_id: str, token: str, profile: dict, health_data_consent: bool, notice_version: str, *, event: dict | None = None):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_profiles
            (profile_id, token_hash, profile_json, privacy_notice_version,
             privacy_acknowledged, health_data_consent, health_data_consent_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (profile_id, hash_access_token(token), _encode_json(profile, dialect),
             notice_version, True, bool(health_data_consent), now if health_data_consent else None, now, now))
        if event is not None:
            _insert_decision_event(
                conn, dialect, profile_id, event,
                health_consent_verified=bool(health_data_consent),
            )
        conn.commit()
        return {"profile_id": profile_id, "profile": profile, "created_at": now, "updated_at": now,
                "health_data_consent": bool(health_data_consent),
                "health_data_consent_at": now if health_data_consent else None,
                "privacy_notice_version": notice_version}
    finally:
        conn.close()

def _authorized_profile(conn, dialect, profile_id: str, token: str):
    row = _execute(conn, dialect,
        "SELECT token_hash, profile_json, privacy_notice_version, health_data_consent, health_data_consent_at, created_at, updated_at FROM atena_profiles WHERE profile_id = %s",
        (profile_id,)).fetchone()
    if not row:
        raise ProfileNotFound()
    stored_hash, profile_json, notice_version, health_consent, health_consent_at, created_at, updated_at = row
    if not token or not __import__("hmac").compare_digest(stored_hash, hash_access_token(token)):
        raise ProfileNotFound()
    return {"profile_id": profile_id, "profile": _decode_json(profile_json), "created_at": created_at,
            "updated_at": updated_at, "health_data_consent": bool(health_consent), "health_data_consent_at": health_consent_at,
            "privacy_notice_version": notice_version}

def get_profile(profile_id: str, token: str):
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()

def update_profile(profile_id: str, token: str, profile: dict, *, event: dict | None = None):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        authorized = _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect, "UPDATE atena_profiles SET profile_json = %s, updated_at = %s WHERE profile_id = %s",
                 (_encode_json(profile, dialect), now, profile_id))
        if event is not None:
            _insert_decision_event(
                conn, dialect, profile_id, event,
                health_consent_verified=authorized["health_data_consent"] is True,
            )
        conn.commit()
        if dialect == "postgres":
            _set_application_role(conn)
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()

def add_session(profile_id: str, token: str, session_id: str, session_date: str, session: dict, *, event: dict | None = None):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        authorized = _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_training_sessions
            (session_id, profile_id, session_date, session_json, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            (session_id, profile_id, session_date, _encode_json(session, dialect), now))
        if event is not None:
            _insert_decision_event(
                conn, dialect, profile_id, event,
                health_consent_verified=authorized["health_data_consent"] is True,
            )
        conn.commit()
        return {"session_id": session_id, "session_date": session_date, "session": session, "created_at": now}
    finally:
        conn.close()

def list_sessions(profile_id: str, token: str, limit: int = 50):
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        rows = _execute(conn, dialect, """SELECT session_id, session_date, session_json, created_at
            FROM atena_training_sessions WHERE profile_id = %s
            ORDER BY session_date DESC, created_at DESC LIMIT %s""",
            (profile_id, limit)).fetchall()
        return [{"session_id": row[0], "session_date": row[1],
                 "session": _decode_json(row[2]), "created_at": row[3]} for row in rows]
    finally:
        conn.close()

def _insert_decision_event(conn, dialect, profile_id, event, *, health_consent_verified):
    """Insert an event inside the caller's transaction after profile/consent validation."""
    if not isinstance(event, dict) or event.get("profile_id") != profile_id:
        raise DecisionEventError("Dogodek mora pripadati preverjenemu profilu.")
    normalized = validate_decision_event(
        event,
        health_consent_verified=health_consent_verified is True,
    )
    cursor = _execute(
        conn, dialect,
        """INSERT INTO atena_decision_events
            (event_id, profile_id, schema_version, event_type, occurred_at,
             source, data_classification, payload_json, program_version_id,
             correlation_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT(event_id) DO NOTHING""",
        (
            normalized["event_id"], profile_id, normalized["schema_version"],
            normalized["event_type"], normalized["occurred_at"],
            normalized["source"], normalized["data_classification"],
            _encode_json(normalized["payload"], dialect),
            normalized.get("program_version_id"), normalized.get("correlation_id"),
            _now(),
        ),
    )
    if cursor.rowcount == 0:
        raise DecisionEventError("Dogodek s tem identifikatorjem že obstaja.")
    return normalized


def append_decision_event(profile_id: str, token: str, event: dict):
    """Append one validated event after authenticating profile and checking consent."""
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        authorized = _authorized_profile(conn, dialect, profile_id, token)
        normalized = _insert_decision_event(
            conn, dialect, profile_id, event,
            health_consent_verified=authorized["health_data_consent"] is True,
        )
        conn.commit()
        return normalized
    finally:
        conn.close()



def list_decision_events(profile_id: str, token: str, limit: int = 50):
    """Return a bounded, authenticated event history for one profile."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 5000:
        raise ValueError("Omejitev dogodkov mora biti med 1 in 5000.")
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        rows = _execute(
            conn, dialect,
            """SELECT event_id, schema_version, event_type, occurred_at, source,
                      data_classification, payload_json, program_version_id,
                      correlation_id, created_at
                 FROM atena_decision_events
                WHERE profile_id = %s
                ORDER BY occurred_at DESC, created_at DESC, event_id DESC
                LIMIT %s""",
            (profile_id, limit),
        ).fetchall()
        events = []
        for row in rows:
            occurred_at = row[3]
            created_at = row[9]
            if hasattr(occurred_at, "isoformat"):
                occurred_at = occurred_at.isoformat()
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            events.append({
                "event_id": row[0],
                "schema_version": row[1],
                "profile_id": profile_id,
                "event_type": row[2],
                "occurred_at": occurred_at,
                "source": row[4],
                "data_classification": row[5],
                "payload": _decode_json(row[6]),
                "program_version_id": row[7],
                "correlation_id": row[8],
                "created_at": created_at,
            })
        return events
    finally:
        conn.close()


def delete_profile(profile_id: str, token: str):
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        _execute(conn, dialect, "DELETE FROM atena_profiles WHERE profile_id = %s", (profile_id,))
        conn.commit()
    finally:
        conn.close()


def set_health_data_consent(profile_id: str, token: str, consent: bool):
    """Allow withdrawal and erasure even while new profile storage is disabled."""
    conn, dialect = _connect(require_enabled=bool(consent))
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        authorized = _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect,
                 "UPDATE atena_profiles SET health_data_consent = %s, health_data_consent_at = %s, updated_at = %s WHERE profile_id = %s",
                 (bool(consent), now if consent else None, now, profile_id))
        if not consent:
            # Remove consent-gated longitudinal records in the same transaction.
            _execute(
                conn, dialect,
                "DELETE FROM atena_decision_events WHERE profile_id = %s AND data_classification = %s",
                (profile_id, "health_sensitive"),
            )
            # Health/movement observations are consent-gated. On withdrawal,
            # erase them from the canonical state as well as legacy session flags.
            profile_data = authorized["profile"]
            if isinstance(profile_data, dict):
                athlete_state = profile_data.get("athlete_state")
                if isinstance(athlete_state, dict):
                    athlete_state["symptoms"] = {"status": "not_asked", "items": []}
                    movement = athlete_state.get("movement_assessment")
                    if isinstance(movement, dict) and isinstance(movement.get("tasks"), dict):
                        for task in movement["tasks"].values():
                            if isinstance(task, dict):
                                task.update({
                                    "status": "not_assessed",
                                    "source": None,
                                    "recorded_at": None,
                                    "note": None,
                                })
                    constraints = athlete_state.get("constraints")
                    if isinstance(constraints, dict):
                        constraints["excluded_patterns"] = []
                        constraints["excluded_exercise_ids"] = []
                    profile_data["athlete_state"] = athlete_state
                    _execute(conn, dialect,
                             "UPDATE atena_profiles SET profile_json = %s WHERE profile_id = %s",
                             (_encode_json(profile_data, dialect), profile_id))
            rows = _execute(conn, dialect,
                            "SELECT session_id, session_json FROM atena_training_sessions WHERE profile_id = %s",
                            (profile_id,)).fetchall()
            for session_id, session_json in rows:
                record = _decode_json(session_json)
                record.pop("discomfort_reported", None)
                _execute(conn, dialect,
                         "UPDATE atena_training_sessions SET session_json = %s WHERE session_id = %s",
                         (_encode_json(record, dialect), session_id))
        consent_event = {
            "schema_version": 1,
            "event_id": __import__("uuid").uuid4().hex,
            "profile_id": profile_id,
            "event_type": "consent_changed",
            "occurred_at": now,
            "source": "user",
            "data_classification": "operational",
            "payload": {"health_data_consent": bool(consent)},
        }
        _insert_decision_event(
            conn, dialect, profile_id, consent_event,
            health_consent_verified=bool(consent),
        )
        conn.commit()
        if dialect == "postgres":
            _set_application_role(conn)
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()
