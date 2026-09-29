"""DuploCloud AI Studio client — the governed execution plane.

Every remediation Sentinel decides on is filed as a DuploCloud ticket in the workspace, with the
SRE persona / self-heal skill attached, so execution is audited, scoped, and approvable inside
DuploCloud. Falls back to a simulated ticket when the platform isn't reachable."""
from __future__ import annotations

import httpx

from .. import config
from ..state import store, now, new_id


class DuploClient:
    def __init__(self):
        self.base = config.DUPLO_BASE_URL
        self.token = config.DUPLO_TOKEN
        self.ws = config.DUPLO_WORKSPACE_ID
        self.agent_id = config.DUPLO_AGENT_ID
        self.scope_ids = config.DUPLO_SCOPE_IDS
        self.enabled = bool(self.token and self.ws)
        self._agent_resolved = False

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    async def probe(self):
        if not self.enabled:
            store.set_integration("duplocloud", status="fallback", detail="DUPLO_TOKEN / DUPLO_WORKSPACE_ID not set — tickets simulated", calls=0, tickets=0)
            return
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(f"{self.base}/v1/aiservicedesk/admin/data/workspaces/{self.ws}", headers=self.headers)
                r.raise_for_status()
                ws = r.json().get("data", r.json())
                if not self.agent_id:
                    await self._resolve_agent(c)
            store.set_integration("duplocloud", status="connected", detail=f"workspace {ws.get('name', self.ws)} · agent {self.agent_id or '?'}", calls=1, tickets=0)
        except Exception as e:
            store.set_integration("duplocloud", status="error", detail=str(e)[:160], calls=0, tickets=0)

    async def _resolve_agent(self, c: httpx.AsyncClient):
        r = await c.get(f"{self.base}/v1/aiservicedesk/user/data/models/allowed", params={"workspaceId": self.ws}, headers=self.headers)
        r.raise_for_status()
        items = r.json().get("data", {}).get("items", [])
        if items and items[0].get("agentIds"):
            self.agent_id = items[0]["agentIds"][0]

    def _bump(self, **f):
        cur = store.integrations.get("duplocloud", {})
        store.set_integration("duplocloud", calls=cur.get("calls", 0) + 1, tickets=cur.get("tickets", 0) + f.pop("tickets", 0), **f)

    async def create_ticket(self, title: str, body: str, origin_id: str, sub_type: str, metadata: dict) -> dict:
        """Create a ticket for the DuploCloud agent. Returns {name, url, simulated}."""
        payload = {
            "title": title,
            "aiAgentId": self.agent_id,
            "workspaceId": self.ws,
            "ticketContextForAgent": {"scopeIds": self.scope_ids, "memoryEnabled": True},
            "originContext": {"type": "SentinelIncident", "id": origin_id, "subType": sub_type, "metadata": metadata},
            "description": body,
        }
        if not self.enabled:
            name = f"sim-{new_id('tkt')}"
            self._bump(tickets=1)
            return {"name": name, "url": f"{config.DUPLO_UI_URL}/ai/service-desk/sim/tickets/chat/{name}", "simulated": True, "created_at": now(), "payload": payload}
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                if not self.agent_id:
                    await self._resolve_agent(c)
                    payload["aiAgentId"] = self.agent_id
                r = await c.post(f"{self.base}/v1/aiservicedesk/tickets/{self.ws}", headers=self.headers, json=payload)
                r.raise_for_status()
                data = r.json()
                data = data.get("data", data)
                name = data.get("name") or data.get("id")
            self._bump(tickets=1)
            return {"name": name, "url": f"{config.DUPLO_UI_URL}/ai/service-desk/{self.ws}/tickets/chat/{name}", "simulated": False, "created_at": now(), "raw": data}
        except Exception as e:
            store.log("error", "duplocloud", f"ticket create failed, simulating: {e}")
            self._bump(status="error", detail=str(e)[:160])
            name = f"sim-{new_id('tkt')}"
            return {"name": name, "url": "", "simulated": True, "error": str(e)[:200], "created_at": now(), "payload": payload}

    async def close_ticket(self, name: str, resolved: bool = True):
        if not self.enabled or name.startswith("sim-"):
            return
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.put(f"{self.base}/v1/aiservicedesk/tickets/{self.ws}/{name}/status", headers=self.headers,
                            json={"status": "closed", "disposition": "resolved" if resolved else "unResolved"})
            self._bump()
        except Exception as e:
            store.log("warn", "duplocloud", f"ticket close failed: {e}")


duplo = DuploClient()
