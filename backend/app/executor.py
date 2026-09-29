"""Remediation executor. Every action is routed to the right plane:
  DuploCloud ticket (governed record) + concrete cloud/k8s executor (Vultr / Nebius / simulated)
and, crucially, clears the underlying fault in the simulator so recovery is observable."""
from __future__ import annotations

import asyncio
from dataclasses import asdict

from .state import store, now, Action, Incident
from .integrations.vultr import vultr
from .integrations.nebius import nebius
from .topology import SERVICES, INVENTORY

SVC = {s["name"]: s for s in SERVICES}
INV_BY_SERVICE = {}
for _i in INVENTORY:
    if _i["service"]:
        INV_BY_SERVICE.setdefault(_i["service"], _i)

ACTION_RISK = {
    "restart": "low", "scale": "low", "rollback": "medium", "rotate_secret": "medium",
    "patch_firewall": "medium", "quarantine": "high", "revoke_sessions": "medium",
    "rate_limit": "low", "renew_cert": "low", "patch_image": "medium", "revoke_iam": "high",
    "clear_cache": "low", "failover": "high", "stop_instance": "medium", "resize_instance": "medium",
    "delete_volume": "high", "apply_tags": "low", "enable_encryption": "medium", "apply_iac": "medium",
}

# Which fault kinds each action heals
HEALS = {
    "crash": {"restart", "rollback", "failover"},
    "latency": {"rollback", "scale", "clear_cache"},
    "error_rate": {"rollback", "restart", "scale"},
    "memory_leak": {"restart", "rollback"},
    "cpu_saturation": {"scale", "restart"},
    "open_port": {"patch_firewall"},
    "cve": {"patch_image", "rollback"},
    "secret_leak": {"rotate_secret"},
    "brute_force": {"rate_limit", "quarantine"},
    "tls_expiry": {"renew_cert"},
    "iam_anomaly": {"revoke_iam", "revoke_sessions"},
}


def _executor_for(kind: str, service: str) -> str:
    cloud = SVC.get(service, {}).get("cloud", "vultr")
    if kind in ("patch_firewall", "stop_instance", "resize_instance", "delete_volume"):
        return cloud
    if kind in ("restart", "scale", "rollback", "failover", "patch_image", "clear_cache"):
        return f"{cloud}-k8s"
    if kind in ("rotate_secret", "revoke_iam", "revoke_sessions", "renew_cert", "rate_limit", "quarantine", "apply_tags", "enable_encryption", "apply_iac"):
        return "duplocloud"
    return "simulated"


async def _run_concrete(a: Action) -> dict:
    svc = a.target
    inst = INV_BY_SERVICE.get(svc, {})
    cloud = SVC.get(svc, {}).get("cloud", "vultr")
    k = a.kind
    if k == "restart":
        if cloud == "nebius":
            return await nebius.instance_action("restart", inst.get("id"))
        return await vultr.instance_action("reboot", inst.get("id"))
    if k == "scale":
        replicas = int(a.params.get("replicas", 4))
        if cloud == "nebius":
            return await nebius.scale(svc, replicas)
        await asyncio.sleep(0.8)
        return {"simulated": not vultr.enabled, "service": svc, "replicas": replicas, "platform": "vultr-vke"}
    if k == "rollback":
        await asyncio.sleep(1.2)
        return {"simulated": True, "service": svc, "from": SVC.get(svc, {}).get("image"), "to": a.params.get("to_version", "previous"), "strategy": "kubectl rollout undo"}
    if k == "patch_firewall":
        rule = {"ip_type": "v4", "protocol": "tcp", "port": str(a.params.get("port", 6379)), "subnet": "10.0.0.0", "subnet_size": 8, "action": "accept", "notes": "sentinel: restrict to VPC"}
        if cloud == "nebius":
            await asyncio.sleep(0.7)
            return {"simulated": not nebius.enabled, "security_group": "sg-internal", "rule": rule}
        return await vultr.update_firewall(a.params.get("firewall_group"), rule)
    if k == "stop_instance":
        if cloud == "nebius":
            return await nebius.instance_action("stop", a.params.get("instance_id"))
        return await vultr.instance_action("halt", a.params.get("instance_id"))
    if k == "resize_instance":
        await asyncio.sleep(0.9)
        return {"simulated": True, "instance": a.params.get("instance_id"), "to": a.params.get("to_type")}
    if k == "delete_volume":
        await asyncio.sleep(0.6)
        return {"simulated": True, "volume": a.params.get("volume_id"), "snapshot_taken": True}
    # governed / control-plane actions
    await asyncio.sleep(1.0)
    return {"simulated": True, "kind": k, "params": a.params, "via": "duplocloud-agent"}


async def execute(inc: Incident, a: Action, duplo_ticket: dict | None = None) -> Action:
    from .monitor import monitor
    a.status = "running"
    a.started_at = now()
    a.executor = _executor_for(a.kind, a.target)
    store.touch_incident(inc)
    store.log("info", "executor", f"{a.kind} → {a.target} via {a.executor}", incident=inc.id, action=a.id)
    try:
        result = await _run_concrete(a)
        a.evidence = {**a.evidence, "result": result, "ticket": (duplo_ticket or {}).get("name")}
        a.status = "succeeded"
        store.stats["actions_executed"] += 1
        if inc.fault_id and a.kind in HEALS.get(inc.kind, set()):
            monitor.heal(inc.fault_id, reason=f"{a.kind} by {a.executor}")
    except Exception as e:
        a.status = "failed"
        a.evidence = {**a.evidence, "error": str(e)}
        store.log("error", "executor", f"{a.kind} on {a.target} failed: {e}", incident=inc.id)
    a.finished_at = now()
    store.add_timeline(inc, "action", f"{a.kind} on {a.target} {a.status}", executor=a.executor, action=asdict(a))
    return a
