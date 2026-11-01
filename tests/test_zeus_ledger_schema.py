import sqlite3
from pathlib import Path


def test_zeus_d1_schema_creates_metadata_tables_and_append_only_events():
    schema_path = Path(__file__).parents[1] / "cloudflare" / "zeus-ledger-worker" / "schema.sql"
    connection = sqlite3.connect(":memory:")
    connection.executescript(schema_path.read_text(encoding="utf-8"))

    connection.execute(
        "INSERT INTO zeus_tasks (task_id, domain, specialist, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("schema-task", "markets", "HERMES", "queued", "2026-11-01T00:00:00Z", "2026-11-01T00:00:00Z"),
    )
    connection.execute(
        "UPDATE zeus_tasks SET status = ?, updated_at = ? WHERE task_id = ?",
        ("assigned", "2026-11-01T00:01:00Z", "schema-task"),
    )
    events = connection.execute(
        "SELECT event_type, from_status, to_status FROM zeus_task_events WHERE task_id = ? ORDER BY event_id",
        ("schema-task",),
    ).fetchall()

    assert events == [
        ("created", None, "queued"),
        ("status_changed", "queued", "assigned"),
    ]


def test_zeus_d1_schema_rejects_domain_specialist_mismatch():
    schema_path = Path(__file__).parents[1] / "cloudflare" / "zeus-ledger-worker" / "schema.sql"
    connection = sqlite3.connect(":memory:")
    connection.executescript(schema_path.read_text(encoding="utf-8"))

    try:
        connection.execute(
            "INSERT INTO zeus_tasks (task_id, domain, specialist, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("bad-task", "markets", "ATENA", "queued", "2026-11-01T00:00:00Z", "2026-11-01T00:00:00Z"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("domain/specialist mismatch should be rejected")



def test_zeus_restart_recovery_migration_adds_constrained_marker():
    root = Path(__file__).parents[1] / "cloudflare" / "zeus-ledger-worker"
    schema = (root / "schema.sql").read_text(encoding="utf-8")
    schema_without_recovery = schema.replace(
        "  recovery_code TEXT CHECK (recovery_code IS NULL OR recovery_code IN ('runtime_restarted')),\n",
        "",
    )
    connection = sqlite3.connect(":memory:")
    connection.executescript(schema_without_recovery)
    connection.executescript(
        (root / "migrations" / "0002_add_recovery_code.sql").read_text(encoding="utf-8")
    )
    connection.execute(
        "INSERT INTO zeus_tasks (task_id, domain, specialist, status, created_at, updated_at, recovery_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("recovered-task", "fitness", "ATENA", "blocked", "2026-11-01T00:00:00Z", "2026-11-01T00:01:00Z", "runtime_restarted"),
    )
    try:
        connection.execute(
            "UPDATE zeus_tasks SET recovery_code = ? WHERE task_id = ?",
            ("unapproved_reason", "recovered-task"),
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("unknown recovery markers should be rejected")



def test_worker_ledger_listing_uses_stable_pagination_and_returns_recovery_marker():
    worker = (
        Path(__file__).parents[1]
        / "cloudflare"
        / "zeus-ledger-worker"
        / "src"
        / "index.js"
    ).read_text(encoding="utf-8")
    assert "ORDER BY created_at DESC, task_id DESC LIMIT ? OFFSET ?" in worker
    assert 'url.searchParams.get("offset")' in worker
    assert "error_code, recovery_code FROM zeus_tasks WHERE task_id = ?" in worker


def test_worker_transition_guard_accepts_d1_trigger_write_counts():
    worker = (
        Path(__file__).parents[1]
        / "cloudflare"
        / "zeus-ledger-worker"
        / "src"
        / "index.js"
    ).read_text(encoding="utf-8")
    assert "result.meta.changes < 1" in worker
    assert "result.meta.changes !== 1" not in worker
