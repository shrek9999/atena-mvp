const MAX_BODY_BYTES = 8192;
const MAX_LIST_LIMIT = 100;
const TERMINAL = new Set(["completed", "failed", "blocked", "cancelled"]);
const SPECIALIST_BY_DOMAIN = {
  fitness: "ATENA",
  human_performance: "ATENA",
  markets: "HERMES",
  investment_research: "HERMES",
};
const TRANSITIONS = {
  queued: new Set(["assigned", "cancelled"]),
  assigned: new Set(["running", "blocked", "cancelled"]),
  running: new Set(["completed", "failed", "blocked"]),
};
const ERROR_CODES = new Set([
  "approval_required",
  "specialist_unavailable",
  "specialist_execution_failed",
  "cancelled_by_request",
]);

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function safeEqual(a, b) {
  const left = new TextEncoder().encode(a);
  const right = new TextEncoder().encode(b);
  let diff = left.length ^ right.length;
  const size = Math.max(left.length, right.length);
  for (let i = 0; i < size; i += 1) {
    diff |= (left[i] || 0) ^ (right[i] || 0);
  }
  return diff === 0;
}

async function authorized(request, env) {
  const expected = env.ZEUS_LEDGER_TOKEN;
  const header = request.headers.get("authorization") || "";
  if (typeof expected !== "string" || expected.length < 32) return false;
  if (!header.startsWith("Bearer ")) return false;
  return safeEqual(header.slice(7), expected);
}

async function readBody(request) {
  const declared = Number(request.headers.get("content-length") || 0);
  if (declared > MAX_BODY_BYTES) throw new Error("body_too_large");
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) throw new Error("body_too_large");
  try {
    return JSON.parse(raw);
  } catch {
    throw new Error("invalid_json");
  }
}

function validTaskId(value) {
  return typeof value === "string" && /^[a-zA-Z0-9_-]{1,100}$/.test(value);
}

async function handle(request, env) {
  if (!(await authorized(request, env))) return json({ error: "unauthorized" }, 401);
  if (!env.ZEUS_DB) return json({ error: "ledger_unavailable" }, 503);

  const url = new URL(request.url);
  const parts = url.pathname.split("/").filter(Boolean);
  const now = new Date().toISOString();

  if (request.method === "POST" && url.pathname === "/v1/tasks") {
    let body;
    try { body = await readBody(request); }
    catch (error) {
      return json({ error: error.message === "body_too_large" ? "body_too_large" : "invalid_json" }, 400);
    }
    if (!body || typeof body !== "object" || Array.isArray(body)) return json({ error: "invalid_body" }, 400);
    if (Object.keys(body).some((key) => !["task_id", "domain", "specialist"].includes(key))) return json({ error: "unknown_field" }, 400);
    if (!validTaskId(body.task_id)) return json({ error: "invalid_task_id" }, 400);
    if (typeof body.domain !== "string" || !SPECIALIST_BY_DOMAIN[body.domain]) {
      return json({ error: "invalid_domain" }, 400);
    }
    const specialist = SPECIALIST_BY_DOMAIN[body.domain];
    if (body.specialist !== specialist) return json({ error: "specialist_domain_mismatch" }, 400);
    try {
      await env.ZEUS_DB.prepare(
        "INSERT INTO zeus_tasks (task_id, domain, specialist, status, created_at, updated_at) VALUES (?, ?, ?, 'queued', ?, ?)"
      ).bind(body.task_id, body.domain, specialist, now, now).run();
      return json({ task_id: body.task_id, status: "queued", created_at: now }, 201);
    } catch {
      return json({ error: "task_create_conflict" }, 409);
    }
  }

  if (request.method === "GET" && url.pathname === "/v1/tasks") {
    const rawLimit = Number(url.searchParams.get("limit") || 50);
    const limit = Number.isInteger(rawLimit) ? Math.max(1, Math.min(MAX_LIST_LIMIT, rawLimit)) : 50;
    const result = await env.ZEUS_DB.prepare(
      "SELECT task_id, domain, specialist, status, created_at, updated_at, started_at, completed_at, expires_at, attempt_count, error_code FROM zeus_tasks ORDER BY created_at DESC LIMIT ?"
    ).bind(limit).all();
    return json({ tasks: result.results || [] });
  }

  if (parts.length === 3 && parts[0] === "v1" && parts[1] === "tasks" && request.method === "GET") {
    const taskId = parts[2];
    if (!validTaskId(taskId)) return json({ error: "invalid_task_id" }, 400);
    const task = await env.ZEUS_DB.prepare(
      "SELECT task_id, domain, specialist, status, created_at, updated_at, started_at, completed_at, expires_at, attempt_count, error_code FROM zeus_tasks WHERE task_id = ?"
    ).bind(taskId).first();
    return task ? json({ task }) : json({ error: "not_found" }, 404);
  }

  if (parts.length === 4 && parts[0] === "v1" && parts[1] === "tasks" && parts[3] === "status" && request.method === "POST") {
    const taskId = parts[2];
    if (!validTaskId(taskId)) return json({ error: "invalid_task_id" }, 400);
    let body;
    try { body = await readBody(request); }
    catch (error) {
      return json({ error: error.message === "body_too_large" ? "body_too_large" : "invalid_json" }, 400);
    }
    if (!body || typeof body !== "object" || Array.isArray(body)) return json({ error: "invalid_body" }, 400);
    if (Object.keys(body).some((key) => !["from_status", "to_status", "error_code"].includes(key))) return json({ error: "unknown_field" }, 400);
    const fromStatus = body.from_status;
    const toStatus = body.to_status;
    if (!TRANSITIONS[fromStatus] || !TRANSITIONS[fromStatus].has(toStatus)) {
      return json({ error: "invalid_transition" }, 400);
    }
    const errorCode = body.error_code || null;
    if (errorCode !== null && !ERROR_CODES.has(errorCode)) return json({ error: "invalid_error_code" }, 400);

    const startedAt = toStatus === "running" ? now : null;
    const completedAt = TERMINAL.has(toStatus) ? now : null;
    const expiresAt = TERMINAL.has(toStatus) ? new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString() : null;
    const attemptIncrement = toStatus === "running" ? 1 : 0;
    const result = await env.ZEUS_DB.prepare(
      "UPDATE zeus_tasks SET status = ?, updated_at = ?, started_at = COALESCE(?, started_at), completed_at = COALESCE(?, completed_at), expires_at = COALESCE(?, expires_at), attempt_count = attempt_count + ?, error_code = ? WHERE task_id = ? AND status = ?"
    ).bind(toStatus, now, startedAt, completedAt, expiresAt, attemptIncrement, errorCode, taskId, fromStatus).run();
    if (!result.meta || result.meta.changes !== 1) return json({ error: "task_missing_or_state_conflict" }, 409);
    const task = await env.ZEUS_DB.prepare(
      "SELECT task_id, domain, specialist, status, created_at, updated_at, started_at, completed_at, expires_at, attempt_count, error_code FROM zeus_tasks WHERE task_id = ?"
    ).bind(taskId).first();
    return json({ task });
  }

  if (parts.length === 4 && parts[0] === "v1" && parts[1] === "tasks" && parts[3] === "events" && request.method === "GET") {
    const taskId = parts[2];
    if (!validTaskId(taskId)) return json({ error: "invalid_task_id" }, 400);
    const result = await env.ZEUS_DB.prepare(
      "SELECT event_id, task_id, event_type, from_status, to_status, occurred_at FROM zeus_task_events WHERE task_id = ? ORDER BY event_id ASC"
    ).bind(taskId).all();
    return json({ events: result.results || [] });
  }

  return json({ error: "not_found" }, 404);
}

export default {
  fetch(request, env) {
    return handle(request, env);
  },
};

export { handle };
