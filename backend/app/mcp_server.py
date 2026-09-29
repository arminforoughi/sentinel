"""Minimal MCP (Streamable HTTP, JSON-RPC 2.0) server exposing Sentinel's tools to the DuploCloud agent.
Register in DuploCloud → AI Admin → MCP Servers as an HTTP server pointing at http://<host>:8000/mcp ."""
from __future__ import annotations

import json
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .agent import CHAT_TOOLS, run_tool
from .state import store

router = APIRouter()

EXTRA_TOOLS = [
    {"name": "get_audit_reports", "description": "List generated compliance audit reports (incident + posture) with control mappings.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "fix_finding", "description": "Remediate a posture finding by id (executes action or applies generated IaC via a DuploCloud ticket).",
     "input_schema": {"type": "object", "properties": {"finding_id": {"type": "string"}}, "required": ["finding_id"], "additionalProperties": False}},
]


def _tools():
    return [{"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]} for t in CHAT_TOOLS + EXTRA_TOOLS]


async def _call(name: str, args: dict):
    if name == "get_audit_reports":
        return [{"id": r.id, "title": r.title, "summary": r.summary, "controls": [c["id"] for c in r.controls]} for r in store.reports.values()]
    if name == "fix_finding":
        from .audit import fix_finding
        f = await fix_finding(args["finding_id"])
        return {"id": f.id, "status": f.status, "ticket": f.fix_action.get("ticket")}
    return run_tool(name, args)


@router.post("/mcp")
async def mcp(request: Request):
    body = await request.json()
    reqs = body if isinstance(body, list) else [body]
    out = []
    for r in reqs:
        mid, method, params = r.get("id"), r.get("method"), r.get("params") or {}
        cur = store.integrations.get("mcp", {})
        store.set_integration("mcp", calls=cur.get("calls", 0) + 1, status="connected", detail="DuploCloud agent ↔ Sentinel tools")
        if method == "initialize":
            res = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "sentinel", "version": "0.1.0"}}
        elif method == "tools/list":
            res = {"tools": _tools()}
        elif method == "tools/call":
            try:
                data = await _call(params.get("name"), params.get("arguments") or {})
                res = {"content": [{"type": "text", "text": json.dumps(data, default=str)}], "isError": False}
            except Exception as e:
                res = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        elif method in ("notifications/initialized", "ping"):
            res = {}
        else:
            out.append({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})
            continue
        if mid is not None:
            out.append({"jsonrpc": "2.0", "id": mid, "result": res})
    if not out:
        return JSONResponse(status_code=202, content=None)
    return JSONResponse(out[0] if not isinstance(body, list) else out)


@router.get("/mcp")
async def mcp_info():
    return {"server": "sentinel", "transport": "streamable-http", "tools": [t["name"] for t in _tools()]}
