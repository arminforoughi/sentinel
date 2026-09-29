"""In-process store + event bus. Everything the UI sees flows through here."""
from __future__ import annotations

import asyncio
import itertools
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


def now() -> float:
    return time.time()


_ids = itertools.count(1)


def new_id(prefix: str) -> str:
    return f"{prefix}-{next(_ids):04d}"


@dataclass
class TimelineEntry:
    ts: float
    phase: str          # detected | triage | diagnosis | plan | approval | action | verify | audit | note
    title: str
    body: str = ""
    meta: dict = field(default_factory=dict)


@dataclass
class Action:
    id: str
    incident_id: str
    kind: str           # restart | scale | rollback | rotate_secret | patch_firewall | quarantine | ...
    target: str
    params: dict
    risk: str           # low | medium | high
    status: str = "pending"   # pending | awaiting_approval | running | succeeded | failed | skipped
    executor: str = "simulated"   # duplocloud | vultr | nebius | k8s | simulated
    evidence: dict = field(default_factory=dict)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class Incident:
    id: str
    service: str
    category: str       # availability | performance | security | cost | governance
    kind: str           # crash | latency | error_rate | memory_leak | open_port | cve | secret_leak | ...
    severity: str       # critical | high | medium | low
    title: str
    detected_at: float
    status: str = "detected"   # detected | triage | diagnosing | planning | awaiting_approval | remediating | verifying | resolved | failed
    summary: str = ""
    root_cause: str = ""
    confidence: float = 0.0
    blast_radius: list[str] = field(default_factory=list)
    blast_radius_source: str = "memory"
    reasoning_source: str = ""    # claude | heuristic
    triage_source: str = ""       # openrouter/nebius | heuristic
    actions: list[Action] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    resolved_at: Optional[float] = None
    mttr_seconds: Optional[float] = None
    ticket: dict = field(default_factory=dict)      # DuploCloud ticket ref
    references: list[dict] = field(default_factory=list)   # Brave search results
    report_id: Optional[str] = None
    fault_id: Optional[str] = None
    rehearsal: dict = field(default_factory=dict)


@dataclass
class Finding:
    """Posture finding from the continuous auditor (security / governance / cost)."""
    id: str
    domain: str         # security | governance | cost
    severity: str
    title: str
    resource: str
    cloud: str
    detail: str
    detected_at: float
    status: str = "open"    # open | fixing | fixed | accepted
    monthly_savings: float = 0.0
    fix_kind: str = ""      # action | iac
    fix_action: dict = field(default_factory=dict)
    iac: str = ""
    controls: list[str] = field(default_factory=list)
    fixed_at: Optional[float] = None
    references: list[dict] = field(default_factory=list)


@dataclass
class AuditReport:
    id: str
    created_at: float
    subject_type: str   # incident | posture
    subject_id: str
    title: str
    summary: str
    controls: list[dict]
    evidence: list[dict]
    markdown: str
    prev_hash: str = ""
    hash: str = ""


DEFAULT_POLICY = {
    "error_rate_threshold": 0.04,     # fraction; degraded above this
    "latency_multiplier": 2.5,        # x baseline p95 → degraded
    "cpu_threshold": 90, "mem_threshold": 90,
    "detect_min_age_s": 3,            # samples needed before an availability fault trips
    "blast_depth": 5,                 # graph hops for blast radius
    "verify_window_s": 20,            # how long to wait for recovery
    "trust_threshold": 0.8,           # earned-autonomy: min trust to auto-execute
    "high_risk_trust_threshold": 0.9, # earned-autonomy: min trust for high-risk actions
    "rehearsal_enabled": True,        # digital-twin rehearsal before execution
    "max_fix_disruption": 20,         # rehearsal: veto actions scoring above this
    "auto_chaos": True, "chaos_interval_s": 90, "tick_s": 2,
    "slo_core": 99.9, "slo_async": 99.5,
}

# Seeded trust priors: (successes, total) per action kind — the agent has "history"
DEFAULT_TRUST = {
    "restart": [14, 15], "scale": [11, 11], "rollback": [9, 10], "clear_cache": [6, 6], "rate_limit": [7, 7],
    "renew_cert": [5, 5], "patch_firewall": [6, 6], "patch_image": [4, 5], "rotate_secret": [4, 5],
    "revoke_sessions": [3, 4], "quarantine": [1, 3], "revoke_iam": [0, 1], "failover": [2, 4],
}


class EventBus:
    def __init__(self):
        self.subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.discard(q)

    def publish(self, type_: str, payload: Any):
        msg = {"type": type_, "ts": now(), "payload": payload}
        for q in list(self.subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass


class Store:
    def __init__(self):
        self.bus = EventBus()
        self.metrics: dict[str, dict] = {}                 # latest per service
        self.history: dict[str, deque] = {}                # per service deque of (ts, latency, err, cpu)
        self.incidents: dict[str, Incident] = {}
        self.findings: dict[str, Finding] = {}
        self.reports: dict[str, AuditReport] = {}
        self.logs: deque = deque(maxlen=400)
        self.integrations: dict[str, dict] = {}
        self.autonomy: str = "earned"
        self.policy: dict = dict(DEFAULT_POLICY)
        self.trust: dict[str, list[int]] = {k: list(v) for k, v in DEFAULT_TRUST.items()}
        self.started_at = now()
        self.stats = {"incidents_total": 0, "auto_resolved": 0, "actions_executed": 0, "savings_identified": 0.0}

    # ---- logging ----
    def log(self, level: str, source: str, message: str, **meta):
        entry = {"ts": now(), "level": level, "source": source, "message": message, "meta": meta}
        self.logs.append(entry)
        self.bus.publish("log", entry)

    # ---- incidents ----
    def add_incident(self, inc: Incident):
        self.incidents[inc.id] = inc
        self.stats["incidents_total"] += 1
        self.bus.publish("incident.created", asdict(inc))

    def touch_incident(self, inc: Incident):
        self.bus.publish("incident.updated", asdict(inc))

    def add_timeline(self, inc: Incident, phase: str, title: str, body: str = "", **meta):
        inc.timeline.append(TimelineEntry(ts=now(), phase=phase, title=title, body=body, meta=meta))
        self.touch_incident(inc)

    # ---- findings ----
    def upsert_finding(self, f: Finding):
        existing = self.findings.get(f.id)
        self.findings[f.id] = f
        self.bus.publish("finding.updated" if existing else "finding.created", asdict(f))

    def add_report(self, r: AuditReport):
        self.reports[r.id] = r
        self.bus.publish("report.created", asdict(r))

    def set_integration(self, name: str, **fields):
        cur = self.integrations.get(name, {})
        cur.update(fields)
        cur["name"] = name
        self.integrations[name] = cur
        self.bus.publish("integration.updated", cur)

    def trust_score(self, kind: str) -> float:
        s, t = self.trust.get(kind, [0, 0])
        return round((s + 1) / (t + 2), 3)

    def record_trust(self, kind: str, ok: bool):
        cur = self.trust.setdefault(kind, [0, 0])
        cur[0] += 1 if ok else 0
        cur[1] += 1
        self.bus.publish("trust.updated", {"kind": kind, "success": cur[0], "total": cur[1], "score": self.trust_score(kind)})

    def trust_table(self) -> list[dict]:
        return [{"kind": k, "success": v[0], "total": v[1], "score": self.trust_score(k)} for k, v in sorted(self.trust.items())]

    # ---- snapshot ----
    def snapshot(self) -> dict:
        return {
            "metrics": self.metrics,
            "incidents": [asdict(i) for i in sorted(self.incidents.values(), key=lambda i: -i.detected_at)],
            "findings": [asdict(f) for f in sorted(self.findings.values(), key=lambda f: -f.detected_at)],
            "reports": [asdict(r) for r in sorted(self.reports.values(), key=lambda r: -r.created_at)],
            "logs": list(self.logs)[-120:],
            "integrations": self.integrations,
            "autonomy": self.autonomy,
            "policy": self.policy,
            "trust": self.trust_table(),
            "stats": self.stats,
            "started_at": self.started_at,
            "history": {k: list(v) for k, v in self.history.items()},
        }


store = Store()
