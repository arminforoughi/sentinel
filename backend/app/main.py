from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import config
from .state import store
from .graph import init_graph, graph, blast_radius
from .monitor import monitor, FAULT_CATALOG, FAULT_TARGETS
from .agent import approve, chat, approvals
from .audit import auditor, fix_finding, posture_report, verify_chain
from .state import DEFAULT_POLICY
from .integrations.duplo import duplo
from .integrations.vultr import vultr
from .integrations.nebius import nebius
from .integrations.openrouter import openrouter
from .integrations.brave import brave
from .mcp_server import router as mcp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.autonomy = config.AUTONOMY
    store.set_integration("claude", status="connected" if config.ANTHROPIC_API_KEY else "fallback",
                          detail=f"model {config.MODEL}" if config.ANTHROPIC_API_KEY else "ANTHROPIC_API_KEY not set — heuristic planner", calls=0)
    store.set_integration("mcp", status="ready", detail="POST /mcp — register in DuploCloud as an MCP server", calls=0)
    await init_graph()
    await asyncio.gather(duplo.probe(), vultr.probe(), nebius.probe(), openrouter.probe(), brave.probe())
    monitor.tick()
    tasks = [asyncio.create_task(monitor.run()), asyncio.create_task(auditor.loop())]
    store.log("info", "sentinel", "Sentinel online — monitoring 18 services")
    yield
    monitor.running = False
    for t in tasks:
        t.cancel()


app = FastAPI(title="Sentinel", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(mcp_router)


@app.get("/api/state")
def state():
    return store.snapshot()


@app.get("/api/graph")
def get_graph():
    data = graph.export()
    data["metrics"] = store.metrics
    return data


@app.get("/api/graph/blast/{service}")
def get_blast(service: str):
    b, src = blast_radius(service)
    return {"service": service, "source": src, "upstream": b, "downstream": graph.downstream(service)}


@app.get("/api/chaos/catalog")
def chaos_catalog():
    return [{"kind": k, "category": v[0], "severity": v[1], "title": v[2].format(svc="<service>"), "description": v[3], "targets": FAULT_TARGETS[k]} for k, v in FAULT_CATALOG.items()]


class InjectBody(BaseModel):
    kind: str
    service: str | None = None


@app.post("/api/chaos/inject")
def inject(body: InjectBody):
    try:
        f = monitor.inject(body.kind, body.service)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"fault_id": f.id, "service": f.service, "kind": f.kind}


@app.post("/api/incidents/{iid}/approve")
def approve_incident(iid: str):
    if iid not in approvals:
        raise HTTPException(404, "no pending approval")
    approve(iid)
    return {"ok": True}


@app.get("/api/incidents/{iid}")
def get_incident(iid: str):
    inc = store.incidents.get(iid)
    if not inc:
        raise HTTPException(404)
    return asdict(inc)


@app.post("/api/findings/{fid}/fix")
async def fix(fid: str):
    if fid not in store.findings:
        raise HTTPException(404)
    return asdict(await fix_finding(fid))


@app.post("/api/findings/{fid}/iac")
async def gen_iac(fid: str):
    from .agent import generate_iac
    f = store.findings.get(fid)
    if not f:
        raise HTTPException(404)
    f.references = await brave.search(f.title)
    f.iac = await generate_iac({k: getattr(f, k) for k in ("domain", "title", "resource", "cloud", "detail")}, f.references)
    store.upsert_finding(f)
    return asdict(f)


@app.post("/api/findings/{fid}/accept")
def accept(fid: str):
    f = store.findings.get(fid)
    if not f:
        raise HTTPException(404)
    f.status = "accepted"
    store.upsert_finding(f)
    return asdict(f)


@app.post("/api/audit/run")
async def run_audit():
    for f in auditor.run():
        if f.id not in store.findings:
            store.upsert_finding(f)
    return asdict(posture_report())


@app.get("/api/reports/{rid}.md", response_class=PlainTextResponse)
def report_md(rid: str):
    r = store.reports.get(rid)
    if not r:
        raise HTTPException(404)
    return r.markdown


@app.get("/api/policy")
def get_policy():
    return {"policy": store.policy, "defaults": DEFAULT_POLICY}


@app.post("/api/policy")
def set_policy(body: dict):
    for k, v in body.items():
        if k in DEFAULT_POLICY:
            store.policy[k] = type(DEFAULT_POLICY[k])(v) if not isinstance(DEFAULT_POLICY[k], bool) else bool(v)
    store.bus.publish("policy.updated", store.policy)
    store.log("info", "policy", "Policy updated: " + ", ".join(f"{k}={store.policy[k]}" for k in body if k in DEFAULT_POLICY))
    return store.policy


@app.post("/api/policy/reset")
def reset_policy():
    store.policy = dict(DEFAULT_POLICY)
    store.bus.publish("policy.updated", store.policy)
    return store.policy


@app.get("/api/trust")
def get_trust():
    return store.trust_table()


@app.get("/api/audit/chain")
def chain():
    return verify_chain()


class AutonomyBody(BaseModel):
    mode: str


@app.post("/api/autonomy")
def set_autonomy(body: AutonomyBody):
    if body.mode not in ("auto", "earned", "approval"):
        raise HTTPException(400)
    store.autonomy = body.mode
    store.bus.publish("autonomy", body.mode)
    store.log("info", "policy", f"Autonomy mode set to {body.mode}")
    return {"mode": body.mode}


class ChatBody(BaseModel):
    messages: list[dict]


@app.post("/api/chat")
async def chat_endpoint(body: ChatBody):
    return await chat(body.messages)


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    q = store.bus.subscribe()
    try:
        await sock.send_text(json.dumps({"type": "snapshot", "payload": store.snapshot()}, default=str))
        while True:
            msg = await q.get()
            await sock.send_text(json.dumps(msg, default=str))
    except WebSocketDisconnect:
        pass
    finally:
        store.bus.unsubscribe(q)
