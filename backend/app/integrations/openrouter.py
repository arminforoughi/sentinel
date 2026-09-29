"""OpenRouter — routes the fast triage model to Nebius / Crusoe GPUs via a pinned preset.
Used for the cheap, high-volume step (severity triage) so the expensive reasoning model only runs on real incidents."""
from __future__ import annotations
import json
import httpx
from .. import config
from ..state import store

URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouter:
    def __init__(self):
        self.key = config.OPENROUTER_API_KEY
        self.model = config.OPENROUTER_MODEL
        self.enabled = bool(self.key)

    async def probe(self):
        if not self.enabled:
            store.set_integration("openrouter", status="fallback", detail="OPENROUTER_API_KEY not set — triage uses heuristics", calls=0)
        else:
            store.set_integration("openrouter", status="connected", detail=f"model {self.model}", calls=0)

    async def triage(self, incident: dict, metrics: dict, blast: list[dict]) -> dict:
        """Returns {severity, priority_reason, source}"""
        if not self.enabled:
            return self._heuristic(incident, blast)
        prompt = (
            "You are an SRE triage model. Given an incident, current metrics and the blast radius, "
            "return JSON {\"severity\": critical|high|medium|low, \"priority_reason\": string}.\n"
            f"Incident: {json.dumps(incident)}\nMetrics: {json.dumps(metrics)}\nBlast radius: {json.dumps(blast)}"
        )
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.post(URL, headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                                               "HTTP-Referer": "https://sentinel.local", "X-Title": "Sentinel"},
                                 json={"model": self.model, "messages": [{"role": "user", "content": prompt}],
                                       "response_format": {"type": "json_object"}, "max_tokens": 300})
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
                data = json.loads(text[text.find("{"): text.rfind("}") + 1])
            cur = store.integrations.get("openrouter", {})
            store.set_integration("openrouter", calls=cur.get("calls", 0) + 1)
            data["source"] = f"openrouter/{self.model}"
            return data
        except Exception as e:
            store.log("warn", "openrouter", f"triage failed, heuristic fallback: {e}")
            return self._heuristic(incident, blast)

    def _heuristic(self, incident: dict, blast: list[dict]) -> dict:
        sev = incident["severity"]
        if len(blast) >= 6 and sev in ("high", "medium"):
            sev = "critical" if sev == "high" else "high"
        return {"severity": sev, "priority_reason": f"{len(blast)} dependent services in blast radius", "source": "heuristic"}


openrouter = OpenRouter()
