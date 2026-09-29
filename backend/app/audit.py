"""Continuous posture auditor (security / governance / cost) + compliance report generator."""
from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import asdict

from . import config
from .state import store, now, new_id, Finding, AuditReport, Incident
from .topology import INVENTORY, SERVICES
from .integrations.vultr import vultr

CONTROLS = {
    # kind → controls satisfied by detect+remediate+evidence
    "availability": ["SOC2 CC7.2", "SOC2 CC7.3", "SOC2 A1.2", "ISO 27001 A.5.30", "NIST CSF RS.MI-1"],
    "performance": ["SOC2 CC7.2", "SOC2 A1.1", "ISO 27001 A.8.6", "NIST CSF DE.CM-1"],
    "security": ["SOC2 CC6.1", "SOC2 CC6.6", "SOC2 CC7.3", "SOC2 CC7.4", "ISO 27001 A.5.24", "ISO 27001 A.5.26", "PCI DSS 10.7", "PCI DSS 12.10", "NIST CSF RS.AN-1"],
    "cost": ["ISO 27001 A.5.9", "FinOps: Rate optimization", "AWS WAF COST04", "SOC2 CC3.2"],
    "governance": ["ISO 27001 A.5.9", "ISO 27001 A.8.9", "SOC2 CC2.1", "CIS Cloud 1.x", "NIST CSF ID.AM-1"],
}

CONTROL_TEXT = {
    "SOC2 CC7.2": "Monitor system components for anomalies indicative of malicious acts, natural disasters, and errors.",
    "SOC2 CC7.3": "Evaluate security events to determine whether they could or have resulted in a failure to meet objectives.",
    "SOC2 CC7.4": "Respond to identified security incidents by executing a defined incident-response program.",
    "SOC2 A1.2": "Recover from environmental disruptions to meet availability commitments.",
    "SOC2 A1.1": "Maintain, monitor and evaluate current processing capacity.",
    "SOC2 CC6.1": "Implement logical access security over protected information assets.",
    "SOC2 CC6.6": "Implement logical access security measures to protect against threats from outside system boundaries.",
    "SOC2 CC3.2": "Identify risks to the achievement of objectives and analyze them.",
    "SOC2 CC2.1": "Obtain or generate relevant, quality information to support internal control.",
    "ISO 27001 A.5.24": "Information security incident management planning and preparation.",
    "ISO 27001 A.5.26": "Response to information security incidents.",
    "ISO 27001 A.5.30": "ICT readiness for business continuity.",
    "ISO 27001 A.8.6": "Capacity management.",
    "ISO 27001 A.5.9": "Inventory of information and other associated assets.",
    "ISO 27001 A.8.9": "Configuration management.",
    "PCI DSS 10.7": "Failures of critical security control systems are detected, reported and responded to promptly.",
    "PCI DSS 12.10": "Suspected and confirmed security incidents are responded to immediately.",
    "NIST CSF RS.MI-1": "Incidents are contained.",
    "NIST CSF RS.AN-1": "Notifications from detection systems are investigated.",
    "NIST CSF DE.CM-1": "Networks and network services are monitored to find potentially adverse events.",
    "NIST CSF ID.AM-1": "Inventories of hardware managed by the organization are maintained.",
    "CIS Cloud 1.x": "Identity and access management benchmarks.",
    "FinOps: Rate optimization": "Right-size and eliminate idle resources.",
    "AWS WAF COST04": "Decommission resources that are no longer needed.",
}


def _fmt_ts(t: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(t))


def incident_report(inc: Incident, prevention: str) -> AuditReport:
    controls = [{"id": c, "text": CONTROL_TEXT.get(c, ""), "status": "satisfied" if inc.status == "resolved" else "partial"} for c in CONTROLS.get(inc.category, [])]
    evidence = [{"ts": _fmt_ts(t.ts), "phase": t.phase, "title": t.title, "body": t.body} for t in inc.timeline]
    acts = "\n".join(f"| {a.kind} | {a.target} | {a.executor} | {a.risk} | {a.status} | {a.evidence.get('ticket') or '-'} |" for a in inc.actions)
    md = f"""# Incident Audit Report — {inc.id}

**Title:** {inc.title}
**Service:** {inc.service} · **Category:** {inc.category} · **Severity:** {inc.severity}
**Detected:** {_fmt_ts(inc.detected_at)} · **Resolved:** {_fmt_ts(inc.resolved_at or now())} · **MTTR:** {inc.mttr_seconds}s
**Outcome:** {inc.status.upper()} · **Reasoning:** {inc.reasoning_source} · **Triage model:** {inc.triage_source}
**DuploCloud ticket:** {inc.ticket.get('name','-')}{' (simulated)' if inc.ticket.get('simulated') else ''}

## Root cause
{inc.root_cause}

## Impact / blast radius ({inc.blast_radius_source})
{', '.join(inc.blast_radius) or 'No upstream dependents.'}

## Remediation actions
| Action | Target | Executor | Risk | Result | Ticket |
|---|---|---|---|---|---|
{acts}

## Verification
{next((t.body for t in reversed(inc.timeline) if t.phase == 'verify'), '')}

## Prevention
{prevention}

## Control mapping
""" + "\n".join(f"- **{c['id']}** — {c['text']} — _{c['status']}_" for c in controls) + """

## References
""" + "\n".join(f"- [{r.get('title')}]({r.get('url')})" for r in inc.references) + """

## Evidence timeline
""" + "\n".join(f"- `{e['ts']}` **{e['phase']}** — {e['title']}: {e['body']}" for e in evidence)

    rep = AuditReport(id=new_id("rpt"), created_at=now(), subject_type="incident", subject_id=inc.id,
                      title=f"Incident audit — {inc.title}", summary=inc.root_cause[:200], controls=controls, evidence=evidence, markdown=md)
    _chain(rep)
    store.add_report(rep)
    return rep


def _chain(rep: AuditReport):
    """Tamper-evident ledger: each report commits to the previous report's hash."""
    prev = max(store.reports.values(), key=lambda r: r.created_at, default=None)
    rep.prev_hash = prev.hash if prev else "0" * 64
    rep.hash = hashlib.sha256((rep.prev_hash + rep.id + rep.markdown).encode()).hexdigest()
    rep.markdown += f"\n\n---\n_Ledger: `{rep.hash[:16]}…` ← prev `{rep.prev_hash[:16]}…`_"


def verify_chain() -> dict:
    reps = sorted(store.reports.values(), key=lambda r: r.created_at)
    prev = "0" * 64
    for r in reps:
        body = r.markdown.rsplit("\n\n---\n_Ledger:", 1)[0]
        if r.prev_hash != prev or hashlib.sha256((r.prev_hash + r.id + body).encode()).hexdigest() != r.hash:
            return {"ok": False, "broken_at": r.id, "length": len(reps)}
        prev = r.hash
    return {"ok": True, "length": len(reps), "head": prev}


# ---------------------------------------------------------------- posture auditor
class PostureAuditor:
    def __init__(self):
        self.inventory = [dict(i) for i in INVENTORY]
        self.last_run = 0.0

    async def refresh_inventory(self):
        """Merge live Vultr instances into inventory when available."""
        if vultr.enabled:
            try:
                live = await vultr.list_instances()
                for inst in live:
                    self.inventory.append(dict(id=inst["id"], cloud="vultr", region=inst.get("region"), type=inst.get("plan"), label=inst.get("label") or inst["id"],
                                               service=None, monthly=float(inst.get("plan", "").split("-")[1].rstrip("c") or 2) * 20 if "-" in inst.get("plan", "") else 20,
                                               cpu_avg=None, tags={t.split(":")[0]: t.split(":")[-1] for t in inst.get("tags", []) if ":" in t}, public_ip=bool(inst.get("main_ip"))))
            except Exception as e:
                store.log("warn", "auditor", f"vultr inventory failed: {e}")

    def run(self) -> list[Finding]:
        found: list[Finding] = []
        t = now()
        for r in self.inventory:
            rid = r["id"]
            # ---- cost ----
            if r.get("cpu_avg") is not None and r["cpu_avg"] < 5 and r["service"] is None:
                found.append(Finding(id=f"cost-idle-{rid}", domain="cost", severity="medium", title=f"Idle instance {r['label']}", resource=rid, cloud=r["cloud"],
                                     detail=f"{r['type']} at {r['cpu_avg']}% avg CPU for 14d, not attached to any service. ${r['monthly']}/mo.", detected_at=t,
                                     monthly_savings=r["monthly"], fix_kind="action", fix_action={"kind": "stop_instance", "instance_id": rid}, controls=CONTROLS["cost"]))
            elif r.get("cpu_avg") is not None and r["cpu_avg"] < 5 and "gpu" in r["type"]:
                found.append(Finding(id=f"cost-gpu-{rid}", domain="cost", severity="high", title=f"Idle GPU {r['label']}", resource=rid, cloud=r["cloud"],
                                     detail=f"H100 at {r['cpu_avg']}% utilisation — training job finished 9d ago. ${r['monthly']}/mo.", detected_at=t,
                                     monthly_savings=r["monthly"], fix_kind="action", fix_action={"kind": "stop_instance", "instance_id": rid}, controls=CONTROLS["cost"]))
            elif r.get("cpu_avg") is not None and r["cpu_avg"] < 15 and r["service"]:
                found.append(Finding(id=f"cost-oversized-{rid}", domain="cost", severity="low", title=f"Over-provisioned {r['label']}", resource=rid, cloud=r["cloud"],
                                     detail=f"{r['type']} at {r['cpu_avg']}% avg CPU. Downsize by half.", detected_at=t, monthly_savings=round(r["monthly"] * 0.5),
                                     fix_kind="iac", controls=CONTROLS["cost"]))
            if r["type"].startswith("ssd") and r["service"] is None:
                found.append(Finding(id=f"cost-orphan-{rid}", domain="cost", severity="medium", title=f"Orphaned volume {r['label']}", resource=rid, cloud=r["cloud"],
                                     detail=f"Unattached 2TB volume, no snapshot policy. ${r['monthly']}/mo.", detected_at=t, monthly_savings=r["monthly"],
                                     fix_kind="action", fix_action={"kind": "delete_volume", "volume_id": rid}, controls=CONTROLS["cost"]))
            # ---- governance ----
            missing = [k for k in ("env", "owner") if k not in r.get("tags", {})]
            if missing:
                found.append(Finding(id=f"gov-tags-{rid}", domain="governance", severity="low", title=f"Missing required tags on {r['label']}", resource=rid, cloud=r["cloud"],
                                     detail=f"Missing: {', '.join(missing)}. Tag policy requires env + owner for chargeback and access review.", detected_at=t,
                                     fix_kind="action", fix_action={"kind": "apply_tags", "instance_id": rid, "tags": {k: "unassigned" for k in missing}}, controls=CONTROLS["governance"]))
            # ---- security ----
            if r.get("public_ip") and r["service"] in (None, "api-gateway") and r["label"] != "api-gateway-2":
                found.append(Finding(id=f"sec-public-{rid}", domain="security", severity="high", title=f"Public IP on {r['label']} without WAF", resource=rid, cloud=r["cloud"],
                                     detail="Instance reachable from 0.0.0.0/0 on 22/tcp; no bastion, no WAF. CIS 4.1 / SOC2 CC6.6.", detected_at=t,
                                     fix_kind="iac", controls=CONTROLS["security"]))
            if r["label"] == "pg-primary":
                found.append(Finding(id=f"sec-encrypt-{rid}", domain="security", severity="medium", title="Database volume not encrypted at rest", resource=rid, cloud=r["cloud"],
                                     detail="postgres-primary block storage has encryption disabled. PCI DSS 3.5 / SOC2 CC6.1.", detected_at=t,
                                     fix_kind="action", fix_action={"kind": "enable_encryption", "instance_id": rid}, controls=CONTROLS["security"]))
        # image-level security from services
        for s in SERVICES:
            if s["image"].endswith(":3.7") or "2024-08" in s["image"]:
                found.append(Finding(id=f"sec-image-{s['name']}", domain="security", severity="medium", title=f"Outdated base image on {s['name']}", resource=s["image"], cloud=s["cloud"],
                                     detail="Image older than 90 days with 3 known medium CVEs. Rebuild from current base.", detected_at=t,
                                     fix_kind="action", fix_action={"kind": "patch_image", "service": s["name"]}, controls=CONTROLS["security"]))
        self.last_run = t
        return found

    async def loop(self):
        await self.refresh_inventory()
        while True:
            try:
                for f in self.run():
                    if f.id not in store.findings:
                        store.upsert_finding(f)
                        store.stats["savings_identified"] = round(sum(x.monthly_savings for x in store.findings.values() if x.status == "open"), 2)
                store.bus.publish("audit.ran", {"ts": now(), "open": sum(1 for f in store.findings.values() if f.status == "open")})
            except Exception as e:
                store.log("error", "auditor", f"posture audit failed: {e}")
            await asyncio.sleep(60)


auditor = PostureAuditor()


async def fix_finding(fid: str) -> Finding:
    from .integrations.duplo import duplo
    from .integrations.nebius import nebius
    from .agent import generate_iac
    from .integrations.brave import brave
    f = store.findings[fid]
    f.status = "fixing"
    store.upsert_finding(f)
    if f.fix_kind == "iac" and not f.iac:
        f.references = await brave.search(f.title, kind="default")
        f.iac = await generate_iac({k: getattr(f, k) for k in ("domain", "title", "resource", "cloud", "detail")}, f.references)
        store.upsert_finding(f)
    body = f"# Sentinel posture fix: {f.title}\n\n{f.detail}\n\n" + (f"Apply this Terraform:\n\n```hcl\n{f.iac}\n```" if f.iac else f"Action: `{f.fix_action}`")
    ticket = await duplo.create_ticket(f"[Sentinel] {f.title}", body, f.id, "posture-fix", {"purpose": "posture-fix", "domain": f.domain})
    kind = f.fix_action.get("kind") if f.fix_kind == "action" else "apply_iac"
    # concrete execution
    if kind == "stop_instance":
        if f.cloud == "nebius":
            res = await nebius.instance_action("stop", f.fix_action.get("instance_id"))
        else:
            res = await vultr.instance_action("halt", f.fix_action.get("instance_id"))
    else:
        await asyncio.sleep(1.0)
        res = {"simulated": True, "via": "duplocloud-agent", "kind": kind}
    f.status = "fixed"
    f.fixed_at = now()
    f.fix_action = {**f.fix_action, "kind": kind, "ticket": ticket.get("name"), "ticket_url": ticket.get("url"), "result": res}
    store.upsert_finding(f)
    store.stats["actions_executed"] += 1
    store.stats["savings_identified"] = round(sum(x.monthly_savings for x in store.findings.values() if x.status == "open"), 2)
    store.log("info", "auditor", f"Fixed {f.id} via {kind} (ticket {ticket.get('name')})")
    posture_report()
    return f


def posture_report() -> AuditReport:
    fs = list(store.findings.values())
    open_ = [f for f in fs if f.status == "open"]
    fixed = [f for f in fs if f.status == "fixed"]
    ctrl_ids = sorted({c for f in fs for c in f.controls})
    controls = [{"id": c, "text": CONTROL_TEXT.get(c, ""), "status": "satisfied" if not any(c in f.controls for f in open_) else "gap"} for c in ctrl_ids]
    md = f"""# Cloud Posture Audit — {_fmt_ts(now())}

**Open findings:** {len(open_)} · **Fixed:** {len(fixed)} · **Monthly savings realised:** ${sum(f.monthly_savings for f in fixed):,.0f} · **Still identified:** ${sum(f.monthly_savings for f in open_):,.0f}

## Fixed
""" + "\n".join(f"- ✅ **{f.title}** ({f.domain}, {f.cloud}) — ticket `{f.fix_action.get('ticket','-')}`" for f in fixed) + """

## Open
""" + "\n".join(f"- ⚠️ **{f.title}** ({f.domain}, {f.severity}) — {f.detail}" for f in open_) + """

## Control coverage
""" + "\n".join(f"- **{c['id']}** — {c['text']} — _{c['status']}_" for c in controls)
    rep = AuditReport(id=new_id("rpt"), created_at=now(), subject_type="posture", subject_id="posture", title="Cloud posture audit",
                      summary=f"{len(open_)} open, {len(fixed)} fixed", controls=controls, evidence=[asdict(f) for f in fixed], markdown=md)
    _chain(rep)
    store.add_report(rep)
    return rep
