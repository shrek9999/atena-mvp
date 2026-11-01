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
