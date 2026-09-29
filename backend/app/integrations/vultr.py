"""Vultr executor — real API when VULTR_API_KEY is set, simulated otherwise."""
from __future__ import annotations
import asyncio
import httpx
from .. import config
from ..state import store

BASE = "https://api.vultr.com/v2"


class Vultr:
    def __init__(self):
        self.key = config.VULTR_API_KEY
        self.enabled = bool(self.key)
        self.instances: list[dict] = []

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.key}"}

    def _bump(self, **f):
        cur = store.integrations.get("vultr", {})
        store.set_integration("vultr", calls=cur.get("calls", 0) + 1, **f)

    async def probe(self):
        if not self.enabled:
            store.set_integration("vultr", status="fallback", detail="VULTR_API_KEY not set — actions simulated", calls=0)
            return
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{BASE}/instances", headers=self.headers)
                r.raise_for_status()
                self.instances = r.json().get("instances", [])
            store.set_integration("vultr", status="connected", detail=f"{len(self.instances)} instances visible", calls=1)
        except Exception as e:
            store.set_integration("vultr", status="error", detail=str(e)[:160], calls=0)

    async def list_instances(self) -> list[dict]:
        if not self.enabled:
            return []
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{BASE}/instances", headers=self.headers)
            self._bump()
            return r.json().get("instances", [])

    async def instance_action(self, action: str, instance_id: str | None) -> dict:
        """action: reboot | start | halt | reinstall"""
        if not self.enabled or not instance_id:
            await asyncio.sleep(0.8)
            self._bump()
            return {"simulated": True, "action": action, "instance": instance_id or "sim-instance", "result": "ok"}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{BASE}/instances/{instance_id}/{action}", headers=self.headers)
            self._bump()
            return {"simulated": False, "action": action, "instance": instance_id, "status": r.status_code}

    async def update_firewall(self, group_id: str | None, rule: dict) -> dict:
        if not self.enabled or not group_id:
            await asyncio.sleep(0.6)
            self._bump()
            return {"simulated": True, "firewall_group": group_id or "sim-fw", "rule": rule}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{BASE}/firewalls/{group_id}/rules", headers=self.headers, json=rule)
            self._bump()
            return {"simulated": False, "status": r.status_code, "body": r.json() if r.content else {}}


vultr = Vultr()
