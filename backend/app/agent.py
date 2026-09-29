"""The agent brain. Pipeline per incident:
  detect → triage (OpenRouter/Nebius) → context (Neo4j blast radius, metrics, Brave advisories)
  → diagnose + plan (Claude, structured output) → approval gate → execute (DuploCloud ticket + cloud executor)
  → verify (metrics recover) → audit report (compliance controls)."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, Field

from . import config
from .state import store, now, new_id, Incident, Action
from .graph import blast_radius, graph
from .integrations.duplo import duplo
from .integrations.openrouter import openrouter
from .integrations.brave import brave
from .executor import execute, ACTION_RISK, HEALS
from .topology import SERVICES

SVC = {s["name"]: s for s in SERVICES}

# ---------------------------------------------------------------- structured plan schema
ActionKind = Literal[
    "restart", "scale", "rollback", "rotate_secret", "patch_firewall", "quarantine", "revoke_sessions",
    "rate_limit", "renew_cert", "patch_image", "revoke_iam", "clear_cache", "failover",
]


class PlannedAction(BaseModel):
    kind: ActionKind
    target: str = Field(description="service name the action applies to")
    params: dict = Field(default_factory=dict)
    rationale: str


class RemediationPlan(BaseModel):
    root_cause: str = Field(description="One-paragraph root cause in plain English")
    confidence: float = Field(ge=0, le=1)
    impact_summary: str = Field(description="Who/what is affected, referencing the blast radius")
    actions: list[PlannedAction] = Field(description="Ordered remediation steps, minimal and reversible first")
    verification: str = Field(description="What metric change proves the fix worked")
    prevention: str = Field(description="One follow-up to prevent recurrence")


SYSTEM = """You are Sentinel, an autonomous SRE + security operations engineer for a production e-commerce platform.
You receive an incident, live metrics, the dependency-graph blast radius (from Neo4j), and current external advisories.
Produce a precise root-cause diagnosis and a minimal, ordered remediation plan using ONLY the allowed action kinds.
Prefer reversible, low-risk actions first. Reference blast-radius services by name. Be concrete and terse."""

_client = None


def client():
    global _client
    if _client is None and config.ANTHROPIC_API_KEY:
        import anthropic
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# ---------------------------------------------------------------- heuristic planner (no API key / fallback)
HEURISTIC = {
    "crash": [("restart", {}), ("rollback", {"to_version": "previous"})],
    "latency": [("rollback", {"to_version": "previous"}), ("scale", {"replicas": 6})],
    "error_rate": [("rollback", {"to_version": "previous"})],
    "memory_leak": [("restart", {}), ("rollback", {"to_version": "previous"})],
    "cpu_saturation": [("scale", {"replicas": 6})],
    "open_port": [("patch_firewall", {"port": 6379})],
    "cve": [("patch_image", {"cve": "CVE-2025-31337"})],
    "secret_leak": [("rotate_secret", {"secret": "AWS_ACCESS_KEY_ID"}), ("revoke_sessions", {})],
    "brute_force": [("rate_limit", {"rps_per_ip": 20}), ("quarantine", {"asn": ["AS14061", "AS16276", "AS9009"]})],
    "tls_expiry": [("renew_cert", {"issuer": "letsencrypt"})],
    "iam_anomaly": [("revoke_iam", {"policy": "attached-unknown"}), ("revoke_sessions", {}), ("rotate_secret", {"secret": "service-role-key"})],
}

ROOT_CAUSES = {
    "crash": "Deploy of a new image introduced a startup panic; readiness probe never passes so the pod crash-loops and drains capacity for every caller.",
    "latency": "A recent deploy regressed a hot query path; p95 latency is 6x baseline and back-pressure is propagating to upstream callers.",
    "error_rate": "New release returns 5xx on a subset of requests (schema mismatch); errors surface at the gateway for dependent flows.",
    "memory_leak": "Unbounded in-process cache introduced in the latest release; RSS grows ~4%/min and will OOMKill within minutes.",
    "cpu_saturation": "Traffic exceeds provisioned capacity; CPU is pinned, request queues are growing and latency doubles for callers.",
    "open_port": "A security group change exposed the datastore port publicly; anyone on the internet can reach it.",
    "cve": "Container image ships a library with a critical remote-code-execution CVE; exploitation risk is immediate.",
    "secret_leak": "A long-lived cloud credential was injected as a plain env var and is visible in logs; treat as compromised.",
    "brute_force": "Credential-stuffing campaign from three ASNs is hammering the login endpoint at 14k attempts/min.",
    "tls_expiry": "Edge TLS certificate renewal automation silently failed; cert expires in 36h and will hard-fail all HTTPS traffic.",
    "iam_anomaly": "Service role was assumed from an unknown IP and a new inline policy was attached — consistent with credential theft.",
}


def heuristic_plan(inc: Incident, blast: list[dict]) -> RemediationPlan:
    acts = [PlannedAction(kind=k, target=inc.service, params=p, rationale=f"Standard runbook step for {inc.kind}") for k, p in HEURISTIC.get(inc.kind, [("restart", {})])]
    names = ", ".join(b["name"] for b in blast[:5]) or "no upstream services"
    return RemediationPlan(
        root_cause=ROOT_CAUSES.get(inc.kind, "Unknown"), confidence=0.72,
        impact_summary=f"{len(blast)} dependent services affected ({names}).",
        actions=acts, verification="Error rate < 1% and p95 latency within 1.5x baseline for 3 consecutive samples.",
        prevention="Add a canary stage with automatic rollback on SLO burn.",
    )


async def claude_plan(inc: Incident, blast: list[dict], metrics: dict, refs: list[dict], triage: dict) -> RemediationPlan | None:
    c = client()
    if not c:
        return None
    ctx = {
        "incident": {k: getattr(inc, k) for k in ("id", "service", "category", "kind", "severity", "title", "summary")},
        "service": SVC.get(inc.service),
        "metrics_now": metrics,
        "downstream_dependencies": graph.downstream(inc.service),
        "blast_radius_upstream": blast,
        "triage": triage,
        "advisories": refs,
    }
    try:
        resp = await asyncio.to_thread(
            lambda: c.messages.parse(
                model=config.MODEL, max_tokens=4000,
                thinking={"type": "adaptive"},
                output_config={"effort": "medium"},
                system=SYSTEM,
                messages=[{"role": "user", "content": f"Diagnose and plan remediation.\n\n{json.dumps(ctx, indent=1)}"}],
                output_format=RemediationPlan,
            )
        )
        cur = store.integrations.get("claude", {})
        store.set_integration("claude", calls=cur.get("calls", 0) + 1, status="connected")
        return resp.parsed_output
    except Exception as e:
        store.log("error", "claude", f"plan failed, heuristic fallback: {e}", incident=inc.id)
        store.set_integration("claude", status="error", detail=str(e)[:160])
        return None


# ---------------------------------------------------------------- digital-twin rehearsal
# How far an action's *own* disruption ripples upstream while it runs, and for how long.
FIX_PROFILE = {   # kind: (upstream hops disrupted, seconds of disruption)
    "restart": (2, 12), "rollback": (1, 8), "scale": (0, 0), "clear_cache": (1, 3), "failover": (3, 25),
    "patch_firewall": (0, 0), "patch_image": (1, 10), "rotate_secret": (1, 5), "revoke_sessions": (1, 2),
    "quarantine": (1, 0), "rate_limit": (0, 0), "renew_cert": (0, 0), "revoke_iam": (2, 4),
}
TIER_WEIGHT = {"data": 3.0, "edge": 2.5, "core": 1.5, "ml": 1.0, "async": 0.6}


def rehearse(inc: Incident) -> dict:
    """Simulate each planned action on the dependency graph *before* touching prod.
    Score = sum(tier weight of every service disrupted by the fix itself) × duration factor.
    Healing actions are re-ordered least-disruptive-first; actions above the veto threshold are demoted."""
    pol = store.policy
    rows = []
    for a in inc.actions:
        hops, secs = FIX_PROFILE.get(a.kind, (1, 5))
        affected = [u["name"] for u in graph.upstream(a.target, depth=hops)] if hops else []
        target_w = TIER_WEIGHT.get(SVC.get(a.target, {}).get("tier", "core"), 1)
        score = round((target_w + sum(TIER_WEIGHT.get(SVC.get(n, {}).get("tier", "core"), 1) for n in affected)) * (1 + secs / 20), 1) if secs or hops else round(target_w * 0.3, 1)
        heals = a.kind in HEALS.get(inc.kind, set())
        rows.append({"action": a.id, "kind": a.kind, "target": a.target, "disrupts": affected, "seconds": secs, "score": score,
                     "heals": heals, "veto": score > pol["max_fix_disruption"], "trust": store.trust_score(a.kind)})
    by_id = {r["action"]: r for r in rows}
    original = [a.kind for a in inc.actions]
    if pol["rehearsal_enabled"]:
        # healing, non-vetoed, cheapest first; then healing vetoed; then the rest in original order
        inc.actions.sort(key=lambda a: (not by_id[a.id]["heals"], by_id[a.id]["veto"], by_id[a.id]["score"]))
    reordered = [a.kind for a in inc.actions] != original
    best = min((r for r in rows if r["heals"]), key=lambda r: (r["veto"], r["score"]), default=None)
    return {"rows": rows, "reordered": reordered, "chosen": best["kind"] if best else None,
            "expected_downtime_s": best["seconds"] if best else None,
            "avoided": [r["kind"] for r in rows if r["heals"] and best and r["score"] > best["score"]]}


def needs_approval(inc: Incident) -> tuple[bool, str]:
    pol = store.policy
    mode = store.autonomy
    if mode == "approval":
        return True, "approval-mode policy"
    if mode == "auto":
        return False, "auto mode"
    # earned autonomy: every action must have enough track record for its risk class
    for a in inc.actions:
        if a.status == "skipped":
            continue
        t = store.trust_score(a.kind)
        need = pol["high_risk_trust_threshold"] if a.risk == "high" else pol["trust_threshold"]
        if t < need:
            return True, f"{a.kind} trust {int(t*100)}% < required {int(need*100)}% ({a.risk} risk)"
    return False, "all actions above trust threshold"


# ---------------------------------------------------------------- pending approvals
approvals: dict[str, asyncio.Event] = {}


def approve(incident_id: str):
    ev = approvals.get(incident_id)
    if ev:
        ev.set()


# ---------------------------------------------------------------- pipeline
async def handle_incident(inc: Incident):
    try:
        await _pipeline(inc)
    except Exception as e:
        inc.status = "failed"
        store.add_timeline(inc, "note", "Pipeline error", str(e))
        store.log("error", "agent", f"pipeline failed for {inc.id}: {e}")


async def _pipeline(inc: Incident):
    # 1. blast radius (Neo4j)
    blast, src = blast_radius(inc.service)
    inc.blast_radius = [b["name"] for b in blast]
    inc.blast_radius_source = src
    inc.status = "triage"
    store.add_timeline(inc, "triage", f"Blast radius mapped via {src}",
                       f"{len(blast)} upstream services affected: " + (", ".join(inc.blast_radius[:8]) or "none"), blast=blast)

    # 2. triage (OpenRouter → Nebius/Crusoe)
    metrics = store.metrics.get(inc.service, {})
    triage = await openrouter.triage({k: getattr(inc, k) for k in ("service", "kind", "severity", "title")}, metrics, blast)
    inc.triage_source = triage.get("source", "heuristic")
    if triage.get("severity") in ("critical", "high", "medium", "low"):
        inc.severity = triage["severity"]
    store.add_timeline(inc, "triage", f"Triage: {inc.severity.upper()} ({inc.triage_source})", triage.get("priority_reason", ""))

    # 3. advisories (Brave)
    q = {
        "cve": "CVE-2025-31337 remediation", "open_port": f"{inc.service} exposed port hardening",
        "secret_leak": "rotate leaked cloud access key incident response", "brute_force": "credential stuffing mitigation rate limiting",
        "tls_expiry": "automate TLS certificate renewal", "iam_anomaly": "compromised IAM role response",
    }.get(inc.kind, f"{inc.kind} kubernetes remediation runbook")
    inc.references = await brave.search(q, kind=inc.kind)
    store.add_timeline(inc, "triage", "Live advisories fetched", "; ".join(r["title"] for r in inc.references[:2]), refs=inc.references)

    # 4. diagnose + plan (Claude)
    inc.status = "diagnosing"
    store.touch_incident(inc)
    plan = await claude_plan(inc, blast, metrics, inc.references, triage)
    inc.reasoning_source = "claude" if plan else "heuristic"
    if not plan:
        plan = heuristic_plan(inc, blast)
    inc.root_cause = plan.root_cause
    inc.confidence = plan.confidence
    inc.summary = plan.impact_summary
    store.add_timeline(inc, "diagnosis", f"Root cause identified ({inc.reasoning_source}, {int(plan.confidence*100)}% confidence)", plan.root_cause)
    inc.status = "planning"
    for pa in plan.actions:
        inc.actions.append(Action(id=new_id("act"), incident_id=inc.id, kind=pa.kind, target=pa.target or inc.service,
                                  params=pa.params, risk=ACTION_RISK.get(pa.kind, "medium"), evidence={"rationale": pa.rationale}))
    store.add_timeline(inc, "plan", f"Remediation plan: {len(inc.actions)} step(s)",
                       " → ".join(f"{a.kind}({a.target})" for a in inc.actions),
                       verification=plan.verification, prevention=plan.prevention)

    # 5. rehearse on the digital twin
    inc.rehearsal = rehearse(inc)
    r = inc.rehearsal
    note = (f"Chosen first step: {r['chosen']} (~{r['expected_downtime_s']}s disruption)" if r["chosen"] else "No healing action available") + \
           (f" · avoided {', '.join(r['avoided'])}" if r["avoided"] else "") + (" · plan re-ordered" if r["reordered"] else "")
    store.add_timeline(inc, "rehearsal", "Rehearsed plan on digital twin", note, rehearsal=r)

    # 6. approval gate — earned autonomy
    gate, why = needs_approval(inc)
    if gate:
        inc.status = "awaiting_approval"
        for a in inc.actions:
            a.status = "awaiting_approval"
        ev = approvals[inc.id] = asyncio.Event()
        store.add_timeline(inc, "approval", "Awaiting human approval", why)
        await ev.wait()
        approvals.pop(inc.id, None)
        store.add_timeline(inc, "approval", "Approved by operator")
    else:
        store.add_timeline(inc, "approval", f"Auto-approved ({store.autonomy})", why)

    # 6. governed execution: DuploCloud ticket + concrete executors
    inc.status = "remediating"
    store.touch_incident(inc)
    body = (f"# Sentinel self-heal: {inc.title}\n\n**Root cause:** {plan.root_cause}\n\n**Blast radius:** {', '.join(inc.blast_radius) or 'none'}\n\n"
            "## Plan\n" + "\n".join(f"{i+1}. `{a.kind}` on `{a.target}` — {a.evidence.get('rationale','')}" for i, a in enumerate(inc.actions))
            + f"\n\n**Verification:** {plan.verification}\n\nUse the `sentinel-self-heal` skill. Report each step's result.")
    inc.ticket = await duplo.create_ticket(f"[Sentinel] {inc.title}", body, inc.id, "self-heal",
                                           {"purpose": "self-heal", "severity": inc.severity, "kind": inc.kind, "service": inc.service})
    store.add_timeline(inc, "action", "DuploCloud ticket opened" + (" (simulated)" if inc.ticket.get("simulated") else ""),
                       inc.ticket.get("name", ""), ticket=inc.ticket)
    for a in inc.actions:
        a.status = "pending"
        await execute(inc, a, inc.ticket)
        if a.status in ("succeeded", "failed"):
            store.record_trust(a.kind, a.status == "succeeded")
        if a.status == "succeeded" and a.kind in HEALS.get(inc.kind, set()):
            # remaining lower-priority steps are unnecessary once the fault is cleared
            for rest in inc.actions[inc.actions.index(a) + 1:]:
                rest.status = "skipped"
                rest.evidence["note"] = "not needed — fault cleared by earlier step"
            break

    # 7. verify
    inc.status = "verifying"
    store.add_timeline(inc, "verify", "Verifying recovery", plan.verification)
    ok = False
    for _ in range(max(1, int(store.policy["verify_window_s"] / store.policy["tick_s"]))):
        await asyncio.sleep(store.policy["tick_s"])
        m = store.metrics.get(inc.service, {})
        base = SVC.get(inc.service, {}).get("lat", 50)
        if inc.category == "security":
            ok = inc.kind not in m.get("findings", [])
        else:
            ok = m.get("status") == "healthy" and m.get("error_rate", 1) < 0.02 and m.get("latency_p95", 1e9) < base * 1.8
        if ok:
            break
    inc.status = "resolved" if ok else "failed"
    inc.resolved_at = now()
    inc.mttr_seconds = round(inc.resolved_at - inc.detected_at, 1)
    if ok:
        store.stats["auto_resolved"] += 1
    else:
        for a in inc.actions:
            if a.status == "succeeded" and a.kind in HEALS.get(inc.kind, set()):
                store.record_trust(a.kind, False)   # "succeeded" but didn't heal → costs trust
    store.add_timeline(inc, "verify", "Recovery verified" if ok else "Recovery NOT verified",
                       f"MTTR {inc.mttr_seconds}s · " + json.dumps({k: store.metrics.get(inc.service, {}).get(k) for k in ("status", "latency_p95", "error_rate")}))
    await duplo.close_ticket(inc.ticket.get("name", ""), resolved=ok)

    # 8. audit report
    from .audit import incident_report
    rep = incident_report(inc, plan.prevention)
    inc.report_id = rep.id
    store.add_timeline(inc, "audit", "Compliance audit report generated", rep.id, report=rep.id)
    store.log("info", "agent", f"{inc.id} {inc.status} in {inc.mttr_seconds}s", incident=inc.id)


# ---------------------------------------------------------------- IaC generation for posture findings
async def generate_iac(finding: dict, refs: list[dict]) -> str:
    c = client()
    fallback = _iac_fallback(finding)
    if not c:
        return fallback
    try:
        resp = await asyncio.to_thread(lambda: c.messages.create(
            model=config.MODEL, max_tokens=3000, thinking={"type": "adaptive"}, output_config={"effort": "low"},
            system="You are a cloud platform engineer. Output ONLY a Terraform (HCL) snippet that remediates the finding, with a 1-line comment header. No prose.",
            messages=[{"role": "user", "content": json.dumps({"finding": finding, "advisories": refs}, indent=1)}],
        ))
        cur = store.integrations.get("claude", {})
        store.set_integration("claude", calls=cur.get("calls", 0) + 1)
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[1].rsplit("```", 1)[0]
        return text or fallback
    except Exception as e:
        store.log("warn", "claude", f"iac generation failed: {e}")
        return fallback


def _iac_fallback(f: dict) -> str:
    r = f.get("resource", "resource")
    if f.get("cloud") == "vultr":
        if "public" in f.get("title", "").lower() or "port" in f.get("title", "").lower():
            return f'''# Sentinel: restrict {r} to VPC-only ingress
resource "vultr_firewall_group" "internal" {{
  description = "sentinel-internal"
}}
resource "vultr_firewall_rule" "allow_vpc" {{
  firewall_group_id = vultr_firewall_group.internal.id
  protocol          = "tcp"
  ip_type           = "v4"
  subnet            = "10.0.0.0"
  subnet_size       = 8
  port              = "6379"
  notes             = "sentinel: VPC only"
}}'''
        return f'''# Sentinel: enforce tags + backups on {r}
resource "vultr_instance" "{r.replace('-', '_')}" {{
  plan   = "vc2-2c-4gb"
  region = "ewr"
  os_id  = 2136
  label  = "{r}"
  tags   = ["env:prod", "owner:platform", "managed-by:sentinel"]
  backups = "enabled"
}}'''
    return f'''# Sentinel: right-size / tag {r} on Nebius
resource "nebius_compute_v1_instance" "{r.replace('-', '_')}" {{
  parent_id = var.nebius_parent_id
  name      = "{r}"
  labels    = {{ env = "prod", owner = "platform", managed-by = "sentinel" }}
  resources {{ platform = "cpu-e2", preset = "4vcpu-16gb" }}
}}'''


# ---------------------------------------------------------------- copilot chat with tools
CHAT_TOOLS = [
    {"name": "get_incidents", "description": "List incidents with status, severity, service, root cause and MTTR.",
     "input_schema": {"type": "object", "properties": {"status": {"type": "string"}}, "additionalProperties": False}},
    {"name": "get_blast_radius", "description": "Return services that transitively depend on a service (from the Neo4j dependency graph).",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "required": ["service"], "additionalProperties": False}},
    {"name": "get_metrics", "description": "Current metrics for one or all services.",
     "input_schema": {"type": "object", "properties": {"service": {"type": "string"}}, "additionalProperties": False}},
    {"name": "get_findings", "description": "Open posture findings (security / governance / cost) with monthly savings.",
     "input_schema": {"type": "object", "properties": {"domain": {"type": "string"}}, "additionalProperties": False}},
    {"name": "inject_fault", "description": "Inject a chaos fault to test self-healing. kinds: crash, latency, error_rate, memory_leak, cpu_saturation, open_port, cve, secret_leak, brute_force, tls_expiry, iam_anomaly",
     "input_schema": {"type": "object", "properties": {"kind": {"type": "string"}, "service": {"type": "string"}}, "required": ["kind"], "additionalProperties": False}},
    {"name": "approve_incident", "description": "Approve a pending remediation plan.",
     "input_schema": {"type": "object", "properties": {"incident_id": {"type": "string"}}, "required": ["incident_id"], "additionalProperties": False}},
]


def run_tool(name: str, inp: dict):
    from .monitor import monitor
    if name == "get_incidents":
        return [{k: getattr(i, k) for k in ("id", "title", "service", "severity", "status", "root_cause", "mttr_seconds", "blast_radius")}
                for i in store.incidents.values() if not inp.get("status") or i.status == inp["status"]][:20]
    if name == "get_blast_radius":
        b, src = blast_radius(inp["service"])
        return {"source": src, "upstream": b, "downstream": graph.downstream(inp["service"])}
    if name == "get_metrics":
        return store.metrics.get(inp["service"]) if inp.get("service") else {k: {kk: v[kk] for kk in ("status", "latency_p95", "error_rate", "cpu", "mem")} for k, v in store.metrics.items()}
    if name == "get_findings":
        return [{k: getattr(f, k) for k in ("id", "domain", "severity", "title", "resource", "status", "monthly_savings")}
                for f in store.findings.values() if not inp.get("domain") or f.domain == inp["domain"]]
    if name == "inject_fault":
        f = monitor.inject(inp["kind"], inp.get("service"))
        return {"fault_id": f.id, "service": f.service}
    if name == "approve_incident":
        approve(inp["incident_id"])
        return {"approved": inp["incident_id"]}
    return {"error": "unknown tool"}


async def chat(messages: list[dict]) -> dict:
    c = client()
    if not c:
        return {"reply": "Claude is not configured (set ANTHROPIC_API_KEY). Tools are still available from the UI.", "tool_calls": []}
    system = ("You are Sentinel Copilot, an SRE/security assistant embedded in an ops console. Use tools to answer with live data. "
              "Be concise; use short bullet lists. The dependency graph is in Neo4j; execution runs through DuploCloud.")
    msgs = list(messages)
    calls = []
    for _ in range(6):
        resp = await asyncio.to_thread(lambda: c.messages.create(
            model=config.MODEL, max_tokens=2000, thinking={"type": "adaptive"}, output_config={"effort": "low"},
            system=system, tools=CHAT_TOOLS, messages=msgs))
        cur = store.integrations.get("claude", {})
        store.set_integration("claude", calls=cur.get("calls", 0) + 1)
        msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            return {"reply": text, "tool_calls": calls}
        results = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                out = run_tool(b.name, b.input)
                calls.append({"tool": b.name, "input": b.input})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, default=str)[:6000]})
        msgs.append({"role": "user", "content": results})
    return {"reply": "Stopped after too many tool iterations.", "tool_calls": calls}
