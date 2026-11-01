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
from urllib.parse import quote, urlsplit, urlunsplit


def _normalize_supabase_pooler_username(url: str) -> str:
    """Apply Supabase's project-scoped username when a shared pooler URI uses bare postgres."""
    try:
        parsed = urlsplit(url)
        hostname = (parsed.hostname or "").lower()
        username = parsed.username or ""
        project_ref = os.getenv("ATENA_SUPABASE_PROJECT_REF", "gxgmxvtfkhjfpbtfmmcs").strip()
        if not (hostname.endswith(".pooler.supabase.com") and username == "postgres" and project_ref):
            return url
        # Preserve the password exactly as supplied (including URL-encoded characters).
        raw_userinfo, _, hostport = parsed.netloc.rpartition("@")
        if not hostport:
            return url
        raw_password = raw_userinfo.partition(":")[2] if ":" in raw_userinfo else None
        normalized_userinfo = "postgres." + project_ref
        if raw_password is not None:
            normalized_userinfo += ":" + raw_password
        return urlunsplit((parsed.scheme, normalized_userinfo + "@" + hostport,
                           parsed.path, parsed.query, parsed.fragment))
    except (TypeError, ValueError):
        return url

class StorageUnavailable(RuntimeError):
    def __init__(self, message: str, reason: str = "storage_unavailable"):
        super().__init__(message)
        self.reason = reason

class ProfileNotFound(RuntimeError):
    pass

def _config():
    enabled = os.getenv("ATENA_DATA_STORAGE_ENABLED", "").strip().lower() == "true"
    notice_approved = os.getenv("ATENA_PRIVACY_NOTICE_APPROVED", "").strip().lower() == "true"
    url = os.getenv("ATENA_DATABASE_URL", "").strip()
    if not enabled or not notice_approved or not url:
        raise StorageUnavailable("Profile storage is not enabled or configured.")
    return url

def _connect():
    url = _config()
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
    return psycopg.connect(url, connect_timeout=8), "postgres"

def _execute(conn, dialect, sql, params=()):
    statement = sql.replace("%s", "?") if dialect == "sqlite" else sql
    return conn.execute(statement, params)

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
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS atena_sessions_profile_date ON atena_training_sessions(profile_id, session_date)"
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

def create_profile(profile_id: str, token: str, profile: dict, health_data_consent: bool, notice_version: str):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_profiles
            (profile_id, token_hash, profile_json, privacy_notice_version,
             privacy_acknowledged, health_data_consent, health_data_consent_at, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (profile_id, hash_access_token(token), json.dumps(profile, ensure_ascii=False),
             notice_version, 1, int(health_data_consent), now if health_data_consent else None, now, now))
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
    return {"profile_id": profile_id, "profile": json.loads(profile_json), "created_at": created_at,
            "updated_at": updated_at, "health_data_consent": bool(health_consent), "health_data_consent_at": health_consent_at,
            "privacy_notice_version": notice_version}

def get_profile(profile_id: str, token: str):
    conn, dialect = _connect()
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
                 (json.dumps(profile, ensure_ascii=False), now, profile_id))
        conn.commit()
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()

def add_session(profile_id: str, token: str, session_id: str, session_date: str, session: dict):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        now = _now()
        _execute(conn, dialect, """INSERT INTO atena_training_sessions
            (session_id, profile_id, session_date, session_json, created_at)
            VALUES (%s, %s, %s, %s, %s)""",
            (session_id, profile_id, session_date, json.dumps(session, ensure_ascii=False), now))
        conn.commit()
        return {"session_id": session_id, "session_date": session_date, "session": session, "created_at": now}
    finally:
        conn.close()

def list_sessions(profile_id: str, token: str, limit: int = 50):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        rows = _execute(conn, dialect, """SELECT session_id, session_date, session_json, created_at
            FROM atena_training_sessions WHERE profile_id = %s
            ORDER BY session_date DESC, created_at DESC LIMIT %s""",
            (profile_id, limit)).fetchall()
        return [{"session_id": row[0], "session_date": row[1],
                 "session": json.loads(row[2]), "created_at": row[3]} for row in rows]
    finally:
        conn.close()

def delete_profile(profile_id: str, token: str):
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        _execute(conn, dialect, "DELETE FROM atena_profiles WHERE profile_id = %s", (profile_id,))
        conn.commit()
    finally:
        conn.close()


def set_health_data_consent(profile_id: str, token: str, consent: bool):
    """Update separate health-data consent; withdrawal also erases stored symptom flags."""
    conn, dialect = _connect()
    try:
        _init(conn, dialect)
        _authorized_profile(conn, dialect, profile_id, token)
        _execute(conn, dialect,
                 "UPDATE atena_profiles SET health_data_consent = %s, health_data_consent_at = %s, updated_at = %s WHERE profile_id = %s",
                 (int(consent), _now() if consent else None, _now(), profile_id))
        if not consent:
            rows = _execute(conn, dialect,
                            "SELECT session_id, session_json FROM atena_training_sessions WHERE profile_id = %s",
                            (profile_id,)).fetchall()
            for session_id, session_json in rows:
                record = json.loads(session_json)
                record.pop("discomfort_reported", None)
                _execute(conn, dialect,
                         "UPDATE atena_training_sessions SET session_json = %s WHERE session_id = %s",
                         (json.dumps(record, ensure_ascii=False), session_id))
        conn.commit()
        return _authorized_profile(conn, dialect, profile_id, token)
    finally:
        conn.close()
