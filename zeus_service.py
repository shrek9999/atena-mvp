"""Authenticated HTTP entry point for the isolated ZEUS coordinator.

No request payloads or specialist results are written to the durable ledger.
All lifecycle writes are fail-closed when the ledger is configured.
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
from functools import wraps
from typing import Any

from flask import Flask, jsonify, make_response, request

from zeus.coordinator import (
    Coordinator,
    LedgerPersistenceUnavailable,
    TaskRequest,
    TaskStatus,
)
from zeus.factory import build_coordinator
from zeus.ledger_worker_client import LedgerWorkerClient


MAX_BODY_BYTES = 64_000
SAFE_TASK_FIELDS = (
    "task_id", "domain", "specialist", "status", "created_at", "updated_at",
    "started_at", "completed_at", "expires_at", "attempt_count", "error_code",
    "recovery_code",
)
SAFE_EVENT_FIELDS = (
    "event_id", "task_id", "event_type", "from_status", "to_status", "occurred_at",
)

DASHBOARD_HTML = r"""<!doctype html>
<html lang="sl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>ZEUS · Agent console</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#151d31;--line:#2a3650;--text:#eef3ff;--muted:#a9b5cb;--accent:#83b7ff;--good:#7ed6aa;--warn:#f4c978}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 15% 0%,#1a2a48 0,transparent 35%),var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1080px;margin:0 auto;padding:28px 18px 64px}header{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px}
h1{font-size:26px;margin:0;letter-spacing:.02em}h2{font-size:17px;margin:0 0 14px}p{margin:6px 0;color:var(--muted)}.sub{font-size:13px;color:var(--muted)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:linear-gradient(160deg,#17223a,#11192b);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 12px 35px #0003;margin-bottom:16px}
label{display:block;font-size:13px;color:var(--muted);margin:12px 0 6px}input,select,textarea{width:100%;background:#0d1526;color:var(--text);border:1px solid #34415c;border-radius:9px;padding:11px 12px;font:inherit}
textarea{min-height:210px;resize:vertical;font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
button{background:#2d5d9a;color:white;border:1px solid #477ab8;border-radius:9px;padding:10px 14px;font-weight:650;cursor:pointer;margin:6px 6px 0 0}
button.secondary{background:#202c42;border-color:#3a4965}button.danger{background:#512d39;border-color:#784555}button:disabled{opacity:.5;cursor:wait}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.row>*{flex:1}.row button{flex:0 0 auto}
.agent{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}.agent:last-child{border:0}
.status{font-size:12px;color:var(--good);border:1px solid #32694f;padding:2px 8px;border-radius:20px;white-space:nowrap}
.task{border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0;background:#0e1729}
.task-title{font-weight:650;overflow-wrap:anywhere}.meta{font-size:12px;color:var(--muted);margin-top:4px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#080e1a;border:1px solid var(--line);border-radius:10px;padding:14px;max-height:420px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace}
.notice{border-left:3px solid var(--accent);padding:8px 12px;color:var(--muted);font-size:13px;margin:12px 0}
#message{min-height:24px;color:var(--good);font-size:13px}#message.error{color:#ff9c9c}
@media(max-width:760px){.grid{grid-template-columns:1fr}header{align-items:flex-start;flex-direction:column}main{padding:18px 12px 48px}}
</style>
</head>
<body>
<main>
<header>
 <div><h1>ZEUS <span style="color:#83b7ff">/</span> AI agent console</h1><p>Enotna vstopna točka za ATENO in HERMES</p></div>
 <div class="sub">ZEUS coordinator · v1</div>
</header>
<div id="message" aria-live="polite"></div>
<section class="card" id="login">
 <h2>Povezava</h2>
 <label for="token">ZEUS API žeton</label>
 <div class="row"><input id="token" type="password" autocomplete="off" placeholder="Prilepi ZEUS_API_TOKEN"><button id="connect">Poveži</button></div>
 <div class="notice">Žeton najdeš v Render → zeus-coordinator → Environment → ZEUS_API_TOKEN. Shrani se samo v sessionStorage tega zavihka in se ne pošilja nikamor drugam kot v ZEUS API.</div>
</section>
<section id="workspace" hidden>
 <div class="grid">
  <section class="card"><h2>Agenti</h2><div id="agents"><p>Preverjam konfiguracijo …</p></div></section>
  <section class="card"><h2>Nova naloga</h2>
   <label for="domain">Specialist</label>
   <select id="domain"><option value="fitness">ATENA · vadba in človeška zmogljivost</option><option value="markets">HERMES · trgi in raziskave</option></select>
   <label for="objective">Cilj naloge</label>
   <input id="objective" value="Pripravi kratek strokovni predlog na podlagi podanih podatkov.">
   <label for="payload">Podatki (JSON)</label>
   <textarea id="payload" spellcheck="false"></textarea>
   <label><input id="approval" type="checkbox" style="width:auto;margin-right:8px"> Zahtevaj mojo odobritev pred izvedbo</label>
   <button id="create">Ustvari nalogo</button>
  </section>
 </div>
 <section class="card"><div class="row"><div><h2>Naloge</h2><p class="sub">D1 hrani samo metapodatke in zgodovino. Rezultat je prikazan ob izvedbi in se ne shranjuje.</p></div><button id="refresh" class="secondary">Osveži</button></div><div id="tasks"><p>Ni naloženih nalog.</p></div></section>
 <section class="card"><h2>Rezultat zadnje izvedbe</h2><pre id="result">Rezultat se bo prikazal tukaj po izvedbi naloge.</pre></section>
 <button id="logout" class="danger">Odjava</button>
</section>
</main>
<script>
const tokenInput=document.getElementById("token");
const message=document.getElementById("message");
const workspace=document.getElementById("workspace");
const login=document.getElementById("login");
const payloadInput=document.getElementById("payload");
const domainInput=document.getElementById("domain");
const resultBox=document.getElementById("result");
const atenaPayload={
 "goal":{"primary":"strength","secondary":"aerobic_fitness"},
 "person":{},
 "constraints":{},
 "state":{"performance":"stable","strength":"stable","rpe":7,"recovery":"stable","symptoms":"none","sleep":"normal","wellness":"normal"},
 "response":{"performance_response":"stable","recovery_response":"stable"},
 "question":"Should the current training stimulus be maintained?",
 "history":{}
};
const hermesPayload={
 "research_type":"macro",
 "subject":"Official public macro source research",
 "time_horizon":"unspecified",
 "source_urls":[
  "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
  "https://www.bls.gov/news.release/cpi.toc.htm",
  "https://www.federalreserve.gov/newsevents/pressreleases.htm"
 ]
};
function defaultPayload(){payloadInput.value=JSON.stringify(domainInput.value==="fitness"?atenaPayload:hermesPayload,null,2);}
function notify(text,error){message.textContent=text;message.className=error?"error":"";}
function headers(){return {"Authorization":"Bearer "+tokenInput.value.trim(),"Content-Type":"application/json"};}
async function api(path,options){
 const response=await fetch(path,{method:(options&&options.method)||"GET",headers:headers(),body:options&&options.body?JSON.stringify(options.body):undefined,cache:"no-store"});
 const data=await response.json().catch(()=>({}));
 if(!response.ok)throw new Error(data.error||("HTTP "+response.status));
 return data;
}
function addText(parent,tag,text,className){
 const el=document.createElement(tag);el.textContent=text;if(className)el.className=className;parent.appendChild(el);return el;
}
async function connect(){
 try{
  if(!tokenInput.value.trim())throw new Error("Vnesi API žeton.");
  sessionStorage.setItem("zeus_api_token",tokenInput.value.trim());
  await api("/v1/agents");
  login.hidden=true;workspace.hidden=false;notify("Povezava z ZEUS je uspešna.",false);
  await refreshAll();
 }catch(error){notify(error.message,true);}
}
async function loadAgents(){
 const data=await api("/v1/agents");const box=document.getElementById("agents");box.replaceChildren();
 addText(box,"div","ZEUS · koordinator nalog","agent");
 for(const agent of data.agents||[]){
  const row=document.createElement("div");row.className="agent";
  const left=document.createElement("div");addText(left,"strong",agent.name);addText(left,"div",agent.description,"sub");
  row.appendChild(left);addText(row,"span",agent.status||"configured","status");box.appendChild(row);
 }
}
async function loadTasks(){
 const data=await api("/v1/tasks");const box=document.getElementById("tasks");box.replaceChildren();
 if(!(data.tasks||[]).length){addText(box,"p","Trenutno ni nalog.");return;}
 for(const task of data.tasks){
  const card=document.createElement("div");card.className="task";
  addText(card,"div",task.task_id,"task-title");
  addText(card,"div",(task.specialist||"") +" · "+(task.status||"")+" · poskusov: "+(task.attempt_count||0),"meta");
  if(task.status==="queued"){
   const run=document.createElement("button");run.textContent="Izvedi";run.addEventListener("click",()=>runTask(task.task_id));card.appendChild(run);
   const approve=document.createElement("button");approve.textContent="Odobri in izvedi";approve.className="secondary";approve.addEventListener("click",()=>approveAndRun(task.task_id));card.appendChild(approve);
  }
  box.appendChild(card);
 }
}
async function refreshAll(){await Promise.all([loadAgents(),loadTasks()]);}
async function createTask(){
 try{
  const payload=JSON.parse(payloadInput.value);
  const data=await api("/v1/tasks",{method:"POST",body:{
   objective:document.getElementById("objective").value,
   domain:domainInput.value,
   payload:payload,
   requires_approval:document.getElementById("approval").checked
  }});
  notify("Naloga je ustvarjena: "+data.task.task_id,false);
  await loadTasks();
  if(!document.getElementById("approval").checked)await runTask(data.task.task_id);
 }catch(error){notify(error.message,true);}
}
async function runTask(id){
 try{
  const data=await api("/v1/tasks/"+encodeURIComponent(id)+"/run",{method:"POST"});
  const status=(data.task||{}).status||"unknown";
  resultBox.textContent=JSON.stringify(data.result||{status:status,error_code:(data.task||{}).error_code||null},null,2);
  if(status==="completed")notify("Naloga je uspešno zaključena.",false);
  else notify("Naloga se je končala s statusom: "+status,true);
  await loadTasks();
 }catch(error){notify(error.message,true);await loadTasks().catch(()=>{});}
}
async function approveAndRun(id){
 try{await api("/v1/tasks/"+encodeURIComponent(id)+"/approve",{method:"POST"});await runTask(id);}
 catch(error){notify(error.message,true);}
}
document.getElementById("connect").addEventListener("click",connect);
document.getElementById("create").addEventListener("click",createTask);
document.getElementById("refresh").addEventListener("click",()=>refreshAll().catch(e=>notify(e.message,true)));
document.getElementById("logout").addEventListener("click",()=>{sessionStorage.removeItem("zeus_api_token");tokenInput.value="";workspace.hidden=true;login.hidden=false;notify("Odjavljen.",false);});
domainInput.addEventListener("change",defaultPayload);
defaultPayload();
try{const saved=sessionStorage.getItem("zeus_api_token");if(saved){tokenInput.value=saved;connect();}}catch(_error){}
</script>
</body>
</html>"""



def _public_record(record) -> dict[str, Any]:
    data = Coordinator.as_dict(record)
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


def _public_metadata(data: dict[str, Any]) -> dict[str, Any]:
    # Explicit allowlist protects the API if the ledger schema gains fields.
    return {key: data.get(key) for key in SAFE_TASK_FIELDS}


def run_startup_smoke(ledger: LedgerWorkerClient, api_token: str) -> dict[str, Any]:
    """Run one deterministic synthetic API lifecycle against the live D1 ledger.

    This is opt-in via ZEUS_STARTUP_SMOKE=1. It uses a fixed, non-sensitive
    task ID and a stub ATENA adapter; it never contacts a real specialist.
    """
    task_id = "zeus-internal-smoke-v1"
    existing = ledger.get_task(task_id)
    if isinstance(existing.get("task"), dict):
        task = existing["task"]
        if task.get("status") == "completed":
            events = ledger.get_events(task_id).get("events", [])
            expected = ["queued", "assigned", "running", "completed"]
            if [event.get("to_status") for event in events] == expected:
                return {"status": "already_completed", "task_id": task_id}
        raise RuntimeError("ZEUS startup smoke task exists in an incomplete state")

    coordinator = Coordinator(
        adapters={"ATENA": lambda _task: {"smoke_test": "passed", "version": "v1"}},
        ledger=ledger,
    )
    client = create_app(coordinator=coordinator, api_token=api_token).test_client()
    auth = {"Authorization": "Bearer " + api_token}

    unauthorized = client.get("/v1/tasks")
    if unauthorized.status_code != 401:
        raise RuntimeError("ZEUS startup smoke authentication check failed")

    created = client.post("/v1/tasks", headers=auth, json={
        "task_id": task_id,
        "objective": "Synthetic ZEUS internal lifecycle validation",
        "domain": "fitness",
        "requires_approval": False,
    })
    if created.status_code != 201:
        raise RuntimeError("ZEUS startup smoke task creation failed")

    executed = client.post(f"/v1/tasks/{task_id}/run", headers=auth)
    execution_task = (executed.get_json() or {}).get("task", {})
    if executed.status_code != 200 or execution_task.get("status") != "completed":
        raise RuntimeError(
            "ZEUS startup smoke execution failed "
            f"(HTTP {executed.status_code}, status={execution_task.get('status')}, "
            f"error_code={execution_task.get('error_code')})"
        )

    retrieved = client.get(f"/v1/tasks/{task_id}", headers=auth)
    if retrieved.status_code != 200:
        raise RuntimeError("ZEUS startup smoke durable read failed")
    task = retrieved.get_json().get("task", {})
    if task.get("status") != "completed" or "objective" in task or "payload" in task:
        raise RuntimeError("ZEUS startup smoke metadata safety check failed")

    event_response = client.get(f"/v1/tasks/{task_id}/events", headers=auth)
    if event_response.status_code != 200:
        raise RuntimeError("ZEUS startup smoke event read failed")
    events = event_response.get_json().get("events", [])
    if [event.get("to_status") for event in events] != [
        "queued", "assigned", "running", "completed"
    ]:
        raise RuntimeError("ZEUS startup smoke event sequence was incomplete")

    return {
        "status": "passed",
        "task_id": task_id,
        "events": len(events),
        "checks": ["authentication", "create", "run", "durable_read", "event_history"],
    }



def run_live_agent_smoke(
    coordinator: Coordinator,
    ledger: LedgerWorkerClient,
    api_token: str,
) -> dict[str, Any]:
    """Exercise both real specialist adapters through ZEUS with synthetic inputs.

    Results remain in coordinator memory only. The D1 ledger receives only
    task metadata and lifecycle events. This check is opt-in and non-blocking
    for service availability.
    """
    client = create_app(coordinator=coordinator, api_token=api_token).test_client()
    auth = {"Authorization": "Bearer " + api_token}
    expected_events = ["queued", "assigned", "running", "completed"]
    atena_payload = {
        "goal": {"primary": "strength", "secondary": "aerobic_fitness"},
        "person": {},
        "constraints": {"available_time": "two sessions per week"},
        "state": {
            "performance": "stable",
            "strength": "stable",
            "rpe": 7,
            "recovery": "stable",
            "symptoms": "none",
            "sleep": "normal",
            "wellness": "normal",
        },
        "response": {
            "performance_response": "stable",
            "recovery_response": "stable",
        },
        "question": "Should the current training stimulus be maintained?",
        "history": {},
    }
    tasks = [
        {
            "task_id": "zeus-live-atena-v1",
            "specialist": "ATENA",
            "domain": "fitness",
            "objective": "Synthetic ATENA connectivity check; no personal data.",
            "payload": atena_payload,
        },
        {
            "task_id": "zeus-live-hermes-v1",
            "specialist": "HERMES",
            "domain": "markets",
            "objective": "Synthetic HERMES public-source connectivity check; no investment recommendation.",
            "payload": {
                "research_type": "macro",
                "subject": "Official public macro source connectivity check",
                "time_horizon": "unspecified",
                "source_urls": [
                    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL",
                    "https://www.bls.gov/news.release/cpi.toc.htm",
                    "https://www.federalreserve.gov/newsevents/pressreleases.htm",
                ],
            },
        },
    ]
    agent_results: dict[str, dict[str, Any]] = {}

    for item in tasks:
        task_id = item["task_id"]
        existing = ledger.get_task(task_id)
        if isinstance(existing.get("task"), dict):
            task = existing["task"]
            if task.get("status") == "completed":
                events = ledger.get_events(task_id).get("events", [])
                if [event.get("to_status") for event in events] == expected_events:
                    agent_results[item["specialist"]] = {
                        "status": "already_completed",
                        "events": len(events),
                    }
                    continue
            raise RuntimeError("ZEUS live-agent smoke task exists in an incomplete state")

        created = client.post("/v1/tasks", headers=auth, json={
            "task_id": task_id,
            "objective": item["objective"],
            "domain": item["domain"],
            "payload": item["payload"],
            "requires_approval": False,
        })
        if created.status_code != 201:
            raise RuntimeError(
                f"ZEUS live-agent smoke could not create {item['specialist']} task"
            )

        executed = client.post(f"/v1/tasks/{task_id}/run", headers=auth)
        execution_task = (executed.get_json() or {}).get("task", {})
        if executed.status_code != 200 or execution_task.get("status") != "completed":
            raise RuntimeError(
                f"ZEUS live-agent smoke execution failed for {item['specialist']}"
            )

        record = coordinator.get(task_id)
        result = record.result if record is not None else None
        if not isinstance(result, dict):
            raise RuntimeError(
                f"ZEUS live-agent smoke returned no structured {item['specialist']} result"
            )
        if item["specialist"] == "ATENA":
            valid_decisions = {
                "maintain", "progress", "reduce", "modify", "collect_data", "refer"
            }
            if (
                result.get("decision") not in valid_decisions
                or not isinstance(result.get("action"), str)
                or not result["action"].strip()
            ):
                raise RuntimeError("ATENA synthetic decision contract was invalid")
            evidence_count = 0
        else:
            documents = result.get("source_documents")
            if result.get("status") != "completed" or not isinstance(documents, list) or not documents:
                raise RuntimeError("HERMES did not retrieve an allowlisted public source")
            evidence_count = len(documents)

        retrieved = client.get(f"/v1/tasks/{task_id}", headers=auth)
        if retrieved.status_code != 200 or retrieved.get_json().get("task", {}).get("status") != "completed":
            raise RuntimeError(
                f"ZEUS live-agent smoke durable read failed for {item['specialist']}"
            )
        event_response = client.get(f"/v1/tasks/{task_id}/events", headers=auth)
        events = (event_response.get_json() or {}).get("events", [])
        if (
            event_response.status_code != 200
            or [event.get("to_status") for event in events] != expected_events
        ):
            raise RuntimeError(
                f"ZEUS live-agent smoke event history failed for {item['specialist']}"
            )
        agent_results[item["specialist"]] = {
            "status": "passed",
            "events": len(events),
            "evidence_count": evidence_count,
        }

    return {
        "status": "passed",
        "agents": agent_results,
        "checks": ["ZEUS routing", "specialist execution", "durable lifecycle", "event history"],
        "results_persisted": False,
    }

def create_app(
    coordinator: Coordinator | None = None,
    api_token: str | None = None,
) -> Flask:
    token = api_token or os.environ.get("ZEUS_API_TOKEN", "")
    if not isinstance(token, str) or len(token) < 32:
        raise RuntimeError("ZEUS_API_TOKEN must contain at least 32 characters")
    if coordinator is None:
        ledger = LedgerWorkerClient.from_environment()
        coordinator = build_coordinator(ledger=ledger)
        coordinator.recover_orphaned_tasks()
        if os.environ.get("ZEUS_STARTUP_SMOKE") == "1":
            try:
                result = run_startup_smoke(ledger, token)
                logging.getLogger("zeus").info(
                    "ZEUS startup smoke %s (task_id=%s, events=%s)",
                    result["status"], result["task_id"], result.get("events", 0),
                )
            except Exception as exc:
                logging.getLogger("zeus").error(
                    "ZEUS startup smoke failed (%s): %s", type(exc).__name__, exc
                )
                raise RuntimeError("ZEUS startup smoke failed") from None
        if os.environ.get("ZEUS_LIVE_AGENT_SMOKE") == "1" or os.environ.get("ZEUS_STARTUP_SMOKE") == "2":
            try:
                result = run_live_agent_smoke(coordinator, ledger, token)
                logging.getLogger("zeus").info(
                    "ZEUS live-agent smoke %s (agents=%s, results_persisted=%s)",
                    result["status"],
                    ",".join(sorted(result["agents"])),
                    result["results_persisted"],
                )
            except Exception as exc:
                # This opt-in integration probe must never make the public
                # coordinator unavailable when a specialist is temporarily down.
                logging.getLogger("zeus").error(
                    "ZEUS live-agent smoke failed (%s)", type(exc).__name__
                )

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

    @app.get("/")
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "ZEUS"})

    @app.get("/ready")
    def readiness():
        """Authenticated readiness probe; liveness remains available at /health."""
        try:
            # In production this performs a bounded read against the durable D1
            # ledger. It never exposes task metadata or dependency error details.
            coordinator.list_task_metadata(limit=1, offset=0)
        except Exception:
            return jsonify({
                "status": "not_ready",
                "service": "ZEUS",
                "dependencies": {"ledger": "unavailable"},
            }), 503
        return jsonify({
            "status": "ready",
            "service": "ZEUS",
            "dependencies": {"ledger": "ok"},
        })

    @app.get("/dashboard", strict_slashes=False)
    def dashboard():
        response = make_response(DASHBOARD_HTML)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self';"
        )
        return response

    @app.get("/favicon.ico")
    def favicon():
        return "", 204

    @app.before_request
    def require_authentication():
        public_paths = {"/", "/health", "/dashboard", "/favicon.ico"}
        if request.endpoint in {"health", "dashboard", "favicon"} or request.path.rstrip("/") in public_paths:
            return None
        supplied = request.headers.get("Authorization", "")
        expected = "Bearer " + token
        if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            return jsonify({"error": "unauthorized"}), 401
        return None

    @app.errorhandler(413)
    def body_too_large(_error):
        return jsonify({"error": "body_too_large"}), 413

    @app.get("/v1/agents")
    def list_agents():
        return jsonify({
            "orchestrator": "ZEUS",
            "agents": [
                {
                    "name": "ATENA",
                    "status": "configured",
                    "domains": ["fitness", "human_performance"],
                    "description": "Strokovna podpora pri vadbi in človeški zmogljivosti prek MCP.",
                },
                {
                    "name": "HERMES",
                    "status": "configured",
                    "domains": ["markets", "investment_research"],
                    "description": "Zbiranje preverljivih dokazov iz javnih finančnih in makroekonomskih virov.",
                },
            ],
        })

    @app.post("/v1/tasks")
    def create_task():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_json_object"}), 400
        allowed = {
            "task_id", "objective", "domain", "acceptance_criteria",
            "payload", "requires_approval",
        }
        if set(body) - allowed:
            return jsonify({"error": "unknown_field"}), 400
        if not isinstance(body.get("objective"), str) or not body["objective"].strip():
            return jsonify({"error": "objective_required"}), 400
        if not isinstance(body.get("domain"), str):
            return jsonify({"error": "domain_required"}), 400
        criteria = body.get("acceptance_criteria", [])
        if not isinstance(criteria, list):
            return jsonify({"error": "acceptance_criteria_must_be_a_list"}), 400
        payload = body.get("payload", {})
        if not isinstance(payload, dict):
            return jsonify({"error": "payload_must_be_an_object"}), 400
        requires_approval = body.get("requires_approval", False)
        if not isinstance(requires_approval, bool):
            return jsonify({"error": "requires_approval_must_be_boolean"}), 400
        try:
            task = TaskRequest(
                objective=body["objective"],
                domain=body["domain"],
                acceptance_criteria=tuple(criteria),
                payload=payload,
                requires_approval=requires_approval,
                approved=False,
                task_id=body.get("task_id") or __import__("uuid").uuid4().hex,
            )
            record = coordinator.enqueue(task)
        except ValueError as exc:
            return jsonify({"error": "invalid_task", "detail": str(exc)}), 400
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        except RuntimeError:
            return jsonify({"error": "coordinator_capacity_reached"}), 503
        return jsonify({"task": _public_record(record)}), 201

    @app.get("/v1/tasks")
    def list_tasks():
        try:
            tasks = [_public_metadata(item) for item in coordinator.list_task_metadata()]
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        return jsonify({"tasks": tasks})

    @app.get("/v1/tasks/<task_id>")
    def get_task(task_id: str):
        try:
            record = coordinator.get_task_metadata(task_id)
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if record is None:
            return jsonify({"error": "not_found"}), 404
        return jsonify({"task": _public_metadata(record)})

    @app.get("/v1/tasks/<task_id>/events")
    def get_task_events(task_id: str):
        try:
            events = coordinator.get_task_events(task_id)
        except Exception:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if events is None:
            return jsonify({"error": "not_found"}), 404
        safe_events = [
            {key: item.get(key) for key in SAFE_EVENT_FIELDS}
            for item in events
        ]
        return jsonify({"events": safe_events})

    @app.post("/v1/tasks/<task_id>/approve")
    def approve_task(task_id: str):
        try:
            record = coordinator.approve(task_id)
        except KeyError:
            return jsonify({"error": "not_found"}), 404
        except ValueError:
            return jsonify({"error": "approval_not_allowed"}), 409
        return jsonify({"task": _public_record(record), "approved": True})

    @app.post("/v1/tasks/<task_id>/run")
    def run_task(task_id: str):
        try:
            record = coordinator.run(task_id)
        except KeyError:
            return jsonify({"error": "not_found"}), 404
        except ValueError:
            return jsonify({"error": "task_not_queued"}), 409
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        # The specialist result is returned to this authenticated caller only.
        # It is intentionally not written to the durable D1 task ledger.
        return jsonify({"task": _public_record(record), "result": record.result})

    @app.post("/v1/tasks/<task_id>/cancel")
    def cancel_task(task_id: str):
        try:
            cancelled = coordinator.cancel(task_id)
        except LedgerPersistenceUnavailable:
            return jsonify({"error": "ledger_unavailable", "retryable": True}), 503
        if not cancelled:
            return jsonify({"error": "task_not_cancellable"}), 409
        return jsonify({"task_id": task_id, "status": TaskStatus.CANCELLED.value})

    return app


class _LazyWSGIApp:
    """Defer secret-dependent runtime construction until the WSGI app is used."""

    def __init__(self):
        self._app = None
        self._initialization_lock = threading.Lock()

    def __call__(self, environ, start_response):
        if self._app is None and environ.get("PATH_INFO") == "/":
            body = b'{"status":"ok","service":"ZEUS"}'
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ])
            return [body]
        if self._app is None:
            # Multiple Gunicorn threads can receive the first readiness probe
            # concurrently. Serialize initialization so recovery and any
            # opt-in startup smoke can never race each other.
            with self._initialization_lock:
                if self._app is None:
                    try:
                        self._app = create_app()
                    except (RuntimeError, ValueError) as exc:
                        # Log only the safe exception type/message; never log tokens
                        # or environment values.
                        logging.getLogger("zeus").error(
                            "ZEUS startup configuration error (%s): %s",
                            type(exc).__name__,
                            exc,
                        )
                        body = b'{"error":"service_not_configured"}'
                        start_response("503 Service Unavailable", [
                            ("Content-Type", "application/json"),
                            ("Content-Length", str(len(body))),
                            ("Cache-Control", "no-store"),
                        ])
                        return [body]
        return self._app(environ, start_response)


app = _LazyWSGIApp()
