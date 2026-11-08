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
        return psycopg.connect(url, connect_timeout=8), "postgres"
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
    elif sqlstate in {"42P01", "42703", "42804", "42883"}:
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
            program_version_id TEXT REFERENCES atena_program_versions(program_version_id) ON DELETE SET NULL,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS atena_movement_assessments (
            profile_id TEXT PRIMARY KEY REFERENCES atena_profiles(profile_id) ON DELETE CASCADE,
            assessment_json JSONB NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS atena_program_versions (
            program_version_id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL REFERENCES atena_profiles(profile_id) ON DELETE CASCADE,
            program_json JSONB NOT NULL,
            decision_json JSONB NOT NULL,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS atena_sessions_profile_date ON atena_training_sessions(profile_id, session_date)",
        "CREATE INDEX IF NOT EXISTS atena_program_versions_profile_created ON atena_program_versions(profile_id, created_at)"
    ]
    for statement in statements:
        _execute(conn, dialect, statement)
    if dialect == "sqlite":
        session_columns = {row[1] for row in conn.execute("PRAGMA table_info(atena_training_sessions)")}
        if "program_version_id" not in session_columns:
            conn.execute(
                "ALTER TABLE atena_training_sessions ADD COLUMN program_version_id "
                "TEXT REFERENCES atena_program_versions(program_version_id) ON DELETE SET NULL"
            )
    _execute(conn, dialect, "CREATE INDEX IF NOT EXISTS atena_sessions_program_version ON atena_training_sessions(program_version_id)")
    if dialect == "postgres":
        # These tables live in Supabase's exposed public schema. The app connects
        # through the server-side database role; browser/API roles must never
        # be able to read or mutate profile data directly.
        postgres_safety = [
            "ALTER TABLE atena_profiles ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE atena_training_sessions ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE atena_movement_assessments ENABLE ROW LEVEL SECURITY",
            "ALTER TABLE atena_program_versions ENABLE ROW LEVEL SECURITY",
            "REVOKE ALL PRIVILEGES ON TABLE atena_profiles FROM PUBLIC, anon, authenticated",
            "REVOKE ALL PRIVILEGES ON TABLE atena_training_sessions FROM PUBLIC, anon, authenticated",
            "REVOKE ALL PRIVILEGES ON TABLE atena_movement_assessments FROM PUBLIC, anon, authenticated",
            "REVOKE ALL PRIVILEGES ON TABLE atena_program_versions FROM PUBLIC, anon, authenticated",
        ]
        for statement in postgres_safety:
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

def create_profile(profile_id: str, token: str, profile: dict, health_data_consent: bool, notice_version: str):
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

def update_profile(profile_id: str, token: str, profile: dict):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect, "UPDATE atena_profiles SET profile_json = %s, updated_at = %s WHERE profile_id = %s",
                 (_encode_json(profile, dialect), now, profile_id))
        conn.commit()
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()

def add_session(
    profile_id: str, token: str, session_id: str, session_date: str,
    session: dict, *, program_version_id: str | None = None,
):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        if program_version_id is not None:
            if not isinstance(program_version_id, str) or not program_version_id.strip() or len(program_version_id) > 128:
                raise ValueError("Različica programa ni veljavna.")
            version = _execute(
                conn, dialect,
                "SELECT 1 FROM atena_program_versions WHERE program_version_id = %s AND profile_id = %s",
                (program_version_id, profile_id),
            ).fetchone()
            if not version:
                raise ValueError("Različica programa ne pripada temu profilu ali ne obstaja.")
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_training_sessions
            (session_id, profile_id, session_date, session_json, program_version_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (session_id, profile_id, session_date, _encode_json(session, dialect), program_version_id, now))
        conn.commit()
        return {
            "session_id": session_id, "session_date": session_date, "session": session,
            "program_version_id": program_version_id, "created_at": now,
        }
    finally:
        conn.close()

def list_sessions(profile_id: str, token: str, limit: int = 50):
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        rows = _execute(conn, dialect, """SELECT session_id, session_date, session_json, program_version_id, created_at
            FROM atena_training_sessions WHERE profile_id = %s
            ORDER BY session_date DESC, created_at DESC LIMIT %s""",
            (profile_id, limit)).fetchall()
        return [{
            "session_id": row[0], "session_date": row[1],
            "session": _decode_json(row[2]), "program_version_id": row[3],
            "created_at": row[4],
        } for row in rows]
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
        _execute(conn, dialect,
                 "UPDATE atena_profiles SET health_data_consent = %s, health_data_consent_at = %s, updated_at = %s WHERE profile_id = %s",
                 (bool(consent), _now() if consent else None, _now(), profile_id))
        if not consent:
            # Movement self-assessment, discomfort flags and heart-rate values
            # are health-related data. Withdrawal erases those fields while
            # retaining ordinary training-performance records.
            _execute(conn, dialect,
                     "DELETE FROM atena_movement_assessments WHERE profile_id = %s",
                     (profile_id,))
            # Saved programme decisions can contain symptom-derived reason codes
            # or exercise choices. Remove programme history on withdrawal rather
            # than retaining a potentially health-inferred record.
            _execute(conn, dialect,
                     "DELETE FROM atena_program_versions WHERE profile_id = %s",
                     (profile_id,))
            rows = _execute(conn, dialect,
                            "SELECT session_id, session_json FROM atena_training_sessions WHERE profile_id = %s",
                            (profile_id,)).fetchall()
            for session_id, session_json in rows:
                record = _decode_json(session_json)
                record.pop("discomfort_reported", None)
                conditioning = record.get("conditioning")
                if isinstance(conditioning, list):
                    for block in conditioning:
                        if isinstance(block, dict):
                            block.pop("average_heart_rate", None)
                _execute(conn, dialect,
                         "UPDATE atena_training_sessions SET session_json = %s WHERE session_id = %s",
                         (_encode_json(record, dialect), session_id))
        conn.commit()
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()


def save_movement_assessment(profile_id: str, token: str, assessment: dict):
    """Store the latest self-reported movement assessment with explicit health-data consent."""
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        profile = _authorized_profile(conn, dialect, profile_id, token)
        if not profile["health_data_consent"]:
            raise StorageUnavailable(
                "Separate health-data consent is required.",
                "health_data_consent_required",
            )
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_movement_assessments
            (profile_id, assessment_json, updated_at) VALUES (%s, %s, %s)
            ON CONFLICT(profile_id) DO UPDATE SET
                assessment_json = excluded.assessment_json,
                updated_at = excluded.updated_at""",
            (profile_id, _encode_json(assessment, dialect), now))
        conn.commit()
        return {"assessment": assessment, "updated_at": now}
    finally:
        conn.close()


def get_movement_assessment(profile_id: str, token: str):
    """Return the latest consented movement self-assessment, if one exists."""
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        profile = _authorized_profile(conn, dialect, profile_id, token)
        if not profile["health_data_consent"]:
            return None
        row = _execute(conn, dialect,
            "SELECT assessment_json, updated_at FROM atena_movement_assessments WHERE profile_id = %s",
            (profile_id,)).fetchone()
        if not row:
            return None
        return {"assessment": _decode_json(row[0]), "updated_at": row[1]}
    finally:
        conn.close()


def add_program_version(profile_id: str, token: str, program_version_id: str,
                        program: dict, decision: dict):
    """Persist an immutable version of a generated programme and its decision context."""
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_program_versions
            (program_version_id, profile_id, program_json, decision_json, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            (program_version_id, profile_id, _encode_json(program, dialect),
             _encode_json(decision, dialect), now))
        conn.commit()
        return {
            "program_version_id": program_version_id,
            "program": program,
            "decision": decision,
            "created_at": now,
        }
    finally:
        conn.close()


def list_program_versions(profile_id: str, token: str, limit: int = 10):
    """List recent immutable programme versions for an authenticated profile."""
    conn, dialect = _connect(require_enabled=False)
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        rows = _execute(conn, dialect, """SELECT program_version_id, program_json,
            decision_json, created_at FROM atena_program_versions
            WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s""",
            (profile_id, limit)).fetchall()
        return [{
            "program_version_id": row[0],
            "program": _decode_json(row[1]),
            "decision": _decode_json(row[2]),
            "created_at": row[3],
        } for row in rows]
    finally:
        conn.close()
