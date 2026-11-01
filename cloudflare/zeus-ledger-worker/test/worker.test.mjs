import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const TOKEN = "x".repeat(48);

class FakeStatement {
  constructor(db, sql) { this.db = db; this.sql = sql; this.params = []; }
  bind(...params) { this.params = params; return this; }
  async run() {
    if (this.sql.startsWith("INSERT INTO zeus_tasks")) {
      const [task_id, domain, specialist, created_at, updated_at] = this.params;
      if (this.db.tasks.has(task_id)) throw new Error("duplicate");
      const row = { task_id, domain, specialist, status: "queued", created_at, updated_at, started_at: null, completed_at: null, expires_at: null, attempt_count: 0, error_code: null };
      this.db.tasks.set(task_id, row);
      this.db.events.push({ event_id: this.db.events.length + 1, task_id, event_type: "created", from_status: null, to_status: "queued", occurred_at: created_at });
      return { meta: { changes: 1 } };
    }
    if (this.sql.startsWith("UPDATE zeus_tasks SET status")) {
      const [status, updated_at, started_at, completed_at, expires_at, increment, error_code, task_id, from_status] = this.params;
      const row = this.db.tasks.get(task_id);
      if (!row || row.status !== from_status) return { meta: { changes: 0 } };
      const previous = row.status;
      row.status = status; row.updated_at = updated_at;
      row.started_at = started_at || row.started_at;
      row.completed_at = completed_at || row.completed_at;
      row.expires_at = expires_at || row.expires_at;
      row.attempt_count += increment; row.error_code = error_code;
      this.db.events.push({ event_id: this.db.events.length + 1, task_id, event_type: "status_changed", from_status: previous, to_status: status, occurred_at: updated_at });
      return { meta: { changes: 1 } };
    }
    throw new Error("unexpected run SQL");
  }
  async first() {
    const [taskId] = this.params;
    return this.db.tasks.get(taskId) || null;
  }
  async all() {
    if (this.sql.includes("FROM zeus_tasks ORDER BY")) return { results: [...this.db.tasks.values()].slice(0, this.params[0]) };
    if (this.sql.includes("FROM zeus_task_events")) return { results: this.db.events.filter(event => event.task_id === this.params[0]) };
    throw new Error("unexpected all SQL");
  }
}

class FakeD1 {
  constructor() { this.tasks = new Map(); this.events = []; }
  prepare(sql) { return new FakeStatement(this, sql); }
}

function request(path, method = "GET", body = undefined, token = TOKEN) {
  const headers = new Headers();
  if (token) headers.set("authorization", "Bearer " + token);
  if (body !== undefined) headers.set("content-type", "application/json");
  return new Request("https://ledger.test" + path, {
    method, headers, body: body === undefined ? undefined : JSON.stringify(body),
  });
}
function env(db = new FakeD1()) { return { ZEUS_DB: db, ZEUS_LEDGER_TOKEN: TOKEN }; }

test("rejects unauthenticated requests", async () => {
  const response = await worker.fetch(request("/v1/tasks", "GET", undefined, null), env());
  assert.equal(response.status, 401);
});

test("creates a minimal task record without objective or payload", async () => {
  const bindings = env();
  const response = await worker.fetch(request("/v1/tasks", "POST", {
    task_id: "test-1", domain: "markets", specialist: "HERMES",
  }), bindings);
  assert.equal(response.status, 201);
  const stored = bindings.ZEUS_DB.tasks.get("test-1");
  assert.equal(stored.status, "queued");
  assert.equal("objective" in stored, false);
  assert.equal("payload" in stored, false);
  assert.equal(bindings.ZEUS_DB.events.length, 1);
});

test("rejects domain-specialist mismatch", async () => {
  const response = await worker.fetch(request("/v1/tasks", "POST", {
    task_id: "bad-1", domain: "markets", specialist: "ATENA",
  }), env());
  assert.equal(response.status, 400);
});

test("applies valid state transition and appends event", async () => {
  const bindings = env();
  await worker.fetch(request("/v1/tasks", "POST", {
    task_id: "task-2", domain: "fitness", specialist: "ATENA",
  }), bindings);
  const response = await worker.fetch(request("/v1/tasks/task-2/status", "POST", {
    from_status: "queued", to_status: "assigned",
  }), bindings);
  assert.equal(response.status, 200);
  assert.equal((await response.json()).task.status, "assigned");
  assert.equal(bindings.ZEUS_DB.events.length, 2);
});

test("rejects invalid transition and stale expected state", async () => {
  const bindings = env();
  await worker.fetch(request("/v1/tasks", "POST", {
    task_id: "task-3", domain: "markets", specialist: "HERMES",
  }), bindings);
  const invalid = await worker.fetch(request("/v1/tasks/task-3/status", "POST", {
    from_status: "queued", to_status: "completed",
  }), bindings);
  assert.equal(invalid.status, 400);
  const stale = await worker.fetch(request("/v1/tasks/task-3/status", "POST", {
    from_status: "assigned", to_status: "running",
  }), bindings);
  assert.equal(stale.status, 409);
});

test("lists task events without exposing stored user content", async () => {
  const bindings = env();
  await worker.fetch(request("/v1/tasks", "POST", {
    task_id: "task-4", domain: "investment_research", specialist: "HERMES",
  }), bindings);
  const response = await worker.fetch(request("/v1/tasks/task-4/events"), bindings);
  assert.equal(response.status, 200);
  const data = await response.json();
  assert.equal(data.events.length, 1);
  assert.equal(data.events[0].event_type, "created");
});

test("unknown methods and paths are not exposed", async () => {
  const response = await worker.fetch(request("/v1/tasks/task-4", "DELETE"), env());
  assert.equal(response.status, 404);
});
