"""Telemetry simulator + chaos engine + detectors.

Faults are real state: they distort metrics, propagate upstream through the dependency graph,
and only clear when a remediation action removes them — so 'self-healing' is observable, not staged."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Optional

from . import config
from .graph import graph
from .state import store, now, new_id, Incident
from .topology import SERVICES

SVC = {s["name"]: s for s in SERVICES}

FAULT_CATALOG = {
    # kind: (category, severity, title template, description)
    "crash":        ("availability", "critical", "{svc} is down (CrashLoopBackOff)", "Pods restarting; readiness probe failing"),
    "latency":      ("performance", "high", "p95 latency regression on {svc}", "Latency 6x baseline after deploy"),
    "error_rate":   ("availability", "high", "5xx error spike on {svc}", "Error rate > 12%"),
    "memory_leak":  ("performance", "medium", "Memory leak on {svc}", "RSS climbing 4%/min toward OOMKill"),
    "cpu_saturation": ("performance", "medium", "CPU saturation on {svc}", "CPU pinned at 97%"),
    "open_port":    ("security", "high", "Unexpected public port on {svc}", "0.0.0.0:6379 exposed to internet"),
    "cve":          ("security", "critical", "Critical CVE in {svc} image", "CVE-2025-31337 (RCE) in base image"),
    "secret_leak":  ("security", "critical", "Credential exposed in {svc} env", "AWS access key found in container env / logs"),
    "brute_force":  ("security", "high", "Credential stuffing against {svc}", "14k failed logins/min from 3 ASNs"),
    "tls_expiry":   ("security", "medium", "TLS certificate expiring on {svc}", "Cert expires in 36h"),
    "iam_anomaly":  ("security", "high", "Anomalous IAM activity from {svc}", "Service role assumed from unknown IP; new policy attached"),
}

# Which services make sense for each fault (for random chaos)
FAULT_TARGETS = {
    "crash": ["payment-service", "checkout-service", "catalog-service", "auth-service", "order-service"],
    "latency": ["search-service", "catalog-service", "payment-service", "fraud-ml", "postgres-primary"],
    "error_rate": ["checkout-service", "inventory-service", "user-service", "api-gateway"],
    "memory_leak": ["cart-service", "notification-service", "search-service"],
    "cpu_saturation": ["fraud-ml", "opensearch", "kafka"],
    "open_port": ["redis-cache", "postgres-primary", "opensearch"],
    "cve": ["payment-service", "user-service", "catalog-service"],
    "secret_leak": ["notification-service", "fraud-ml", "order-service"],
    "brute_force": ["auth-service"],
    "tls_expiry": ["api-gateway", "edge-cdn"],
    "iam_anomaly": ["fraud-ml", "object-store", "order-service"],
}


@dataclass
class Fault:
    id: str
    kind: str
    service: str
    started_at: float
    intensity: float = 1.0
    incident_id: Optional[str] = None
    detected: bool = False
    healing: bool = False       # remediation applied; metrics recovering


class Monitor:
    def __init__(self):
        self.faults: dict[str, Fault] = {}
        self.tick_no = 0
        self.mem_base: dict[str, float] = {n: random.uniform(38, 55) for n in SVC}
        self.running = False

    # ---------- chaos ----------
    def inject(self, kind: str, service: str | None = None, intensity: float = 1.0) -> Fault:
        if kind not in FAULT_CATALOG:
            raise ValueError(f"unknown fault kind {kind}")
        service = service or random.choice(FAULT_TARGETS.get(kind, list(SVC)))
        for f in self.faults.values():
            if f.kind == kind and f.service == service:
                return f
        f = Fault(id=new_id("fault"), kind=kind, service=service, started_at=now(), intensity=intensity)
        self.faults[f.id] = f
        store.log("warn", "chaos", f"Injected fault {kind} on {service}", fault=f.id)
        store.bus.publish("fault.injected", {"id": f.id, "kind": kind, "service": service})
        return f

    def heal(self, fault_id: str, reason: str = "remediated"):
        f = self.faults.get(fault_id)
        if not f:
            return
        f.healing = True
        store.log("info", "monitor", f"Fault {f.kind} on {f.service} cleared ({reason})", fault=f.id)
        store.bus.publish("fault.cleared", {"id": f.id, "kind": f.kind, "service": f.service})
        # keep briefly so recovery ramp is visible
        asyncio.get_event_loop().call_later(6, lambda: self.faults.pop(fault_id, None))

    def faults_for(self, service: str) -> list[Fault]:
        return [f for f in self.faults.values() if f.service == service and not f.healing]

    # ---------- telemetry ----------
    def _propagation(self) -> dict[str, float]:
        """Upstream pressure: a sick dependency degrades the services that call it, decaying per hop."""
        pressure: dict[str, float] = {}
        for f in self.faults.values():
            if f.healing or f.kind not in ("crash", "latency", "error_rate", "cpu_saturation"):
                continue
            for up in graph.upstream(f.service, depth=3):
                w = f.intensity * (0.55 ** up["hops"])
                pressure[up["name"]] = max(pressure.get(up["name"], 0), w)
        return pressure

    def tick(self):
        self.tick_no += 1
        pressure = self._propagation()
        t = now()
        for name, s in SVC.items():
            base_lat, base_rps = s["lat"], s["rps"]
            lat = base_lat * random.uniform(0.85, 1.2)
            err = random.uniform(0.001, 0.008)
            cpu = random.uniform(22, 48)
            self.mem_base[name] += random.uniform(-0.4, 0.4)
            self.mem_base[name] = min(max(self.mem_base[name], 30), 70)
            mem = self.mem_base[name]
            rps = base_rps * random.uniform(0.9, 1.1)
            status = "healthy"
            findings: list[str] = []

            for f in self.faults_for(name):
                k, i = f.kind, f.intensity
                if k == "crash":
                    status, err, lat, rps = "down", 1.0, base_lat * 25, rps * 0.05
                elif k == "latency":
                    lat *= 6 * i; err += 0.03
                elif k == "error_rate":
                    err += 0.14 * i; lat *= 1.6
                elif k == "memory_leak":
                    self.mem_base[name] = min(self.mem_base[name] + 1.6, 99); mem = self.mem_base[name]
                    if mem > 92: err += 0.05
                elif k == "cpu_saturation":
                    cpu = random.uniform(94, 99); lat *= 2.4
                elif k == "brute_force":
                    rps *= 3.2; err += 0.06; findings.append("auth_failures_spike")
                else:
                    findings.append(k)

            if (p := pressure.get(name)):
                lat *= 1 + 3.2 * p
                err += 0.09 * p
                if p > 0.45 and status == "healthy":
                    status = "degraded"

            pol = store.policy
            if status == "healthy" and (err > pol["error_rate_threshold"] or lat > base_lat * pol["latency_multiplier"] or cpu > pol["cpu_threshold"] or mem > pol["mem_threshold"]):
                status = "degraded"

            # SLO / error budget over the rolling window (last ~2 min of samples)
            slo = pol["slo_core"] if s["tier"] in ("edge", "core", "data") else pol["slo_async"]
            allowed = 1 - slo / 100
            hist = store.history.get(name, [])
            window_err = (sum(x[2] for x in hist) + err) / (len(hist) + 1)
            burn = round(window_err / allowed, 1) if allowed else 0
            budget = round(max(0.0, 1 - window_err / allowed) * 100, 1) if allowed else 100

            m = {
                "service": name, "ts": t, "status": status,
                "latency_p95": round(lat, 1), "error_rate": round(min(err, 1), 4),
                "cpu": round(cpu, 1), "mem": round(mem, 1), "rps": round(rps),
                "findings": findings, "cloud": s["cloud"], "tier": s["tier"],
                "pressure": round(pressure.get(name, 0), 2),
                "slo": slo, "burn_rate": burn, "budget_remaining": budget,
            }
            store.metrics[name] = m
            h = store.history.setdefault(name, __import__("collections").deque(maxlen=60))
            h.append([round(t), m["latency_p95"], m["error_rate"], m["cpu"], m["mem"]])

        store.bus.publish("metrics", {"ts": t, "services": store.metrics})
        self._detect()

    # ---------- detection ----------
    def _detect(self):
        for f in list(self.faults.values()):
            if f.detected or f.healing:
                continue
            # availability/perf faults need a couple of samples to trip thresholds; security faults trip immediately
            age = now() - f.started_at
            if f.kind in ("crash", "latency", "error_rate", "cpu_saturation") and age < store.policy["detect_min_age_s"]:
                continue
            if f.kind == "memory_leak" and store.metrics[f.service]["mem"] < 80:
                continue
            f.detected = True
            cat, sev, title, desc = FAULT_CATALOG[f.kind]
            m = store.metrics.get(f.service, {})
            inc = Incident(
                id=new_id("inc"), service=f.service, category=cat, kind=f.kind, severity=sev,
                title=title.format(svc=f.service), detected_at=now(), fault_id=f.id,
                summary=desc,
            )
            f.incident_id = inc.id
            store.add_incident(inc)
            store.add_timeline(inc, "detected", "Anomaly detected", desc, metrics={
                k: m.get(k) for k in ("latency_p95", "error_rate", "cpu", "mem", "status")})
            store.log("error", "detector", f"{inc.severity.upper()} {inc.title}", incident=inc.id)
            from .agent import handle_incident   # lazy to avoid cycle
            asyncio.create_task(handle_incident(inc))

    # ---------- loop ----------
    async def run(self):
        self.running = True
        last_chaos = now()
        while self.running:
            try:
                self.tick()
                iv = store.policy["chaos_interval_s"]
                if store.policy["auto_chaos"] and now() - last_chaos > random.uniform(iv * 0.8, iv * 1.3) and len(self.faults) < 2:
                    kind = random.choice(list(FAULT_CATALOG))
                    self.inject(kind)
                    last_chaos = now()
            except Exception as e:
                store.log("error", "monitor", f"tick failed: {e}")
            await asyncio.sleep(store.policy["tick_s"])


monitor = Monitor()
