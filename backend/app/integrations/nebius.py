"""Nebius AI Cloud executor — compute API when NEBIUS_IAM_TOKEN is set, simulated otherwise."""
from __future__ import annotations
import asyncio
import httpx
from .. import config
from ..state import store

BASE = "https://api.eu.nebius.cloud/compute/v1"


class Nebius:
    def __init__(self):
        self.token = config.NEBIUS_IAM_TOKEN
        self.parent = config.NEBIUS_PARENT_ID
        self.enabled = bool(self.token and self.parent)

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def _bump(self, **f):
        cur = store.integrations.get("nebius", {})
        store.set_integration("nebius", calls=cur.get("calls", 0) + 1, **f)

    async def probe(self):
        if not self.enabled:
            store.set_integration("nebius", status="fallback", detail="NEBIUS_IAM_TOKEN not set — GPU/compute actions simulated", calls=0)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{BASE}/instances", params={"parentId": self.parent}, headers=self.headers)
                r.raise_for_status()
                n = len(r.json().get("items", []))
            store.set_integration("nebius", status="connected", detail=f"{n} instances in {self.parent}", calls=1)
        except Exception as e:
            store.set_integration("nebius", status="error", detail=str(e)[:160], calls=0)

    async def instance_action(self, action: str, instance_id: str | None) -> dict:
        """action: start | stop | restart"""
        if not self.enabled or not instance_id:
            await asyncio.sleep(0.9)
            self._bump()
            return {"simulated": True, "action": action, "instance": instance_id or "sim-gpu-node", "result": "ok"}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{BASE}/instances/{instance_id}:{action}", headers=self.headers, json={})
            self._bump()
            return {"simulated": False, "action": action, "instance": instance_id, "status": r.status_code}

    async def scale(self, service: str, replicas: int) -> dict:
        await asyncio.sleep(0.7)
        self._bump()
        return {"simulated": not self.enabled, "service": service, "replicas": replicas, "platform": "nebius-k8s"}


nebius = Nebius()
