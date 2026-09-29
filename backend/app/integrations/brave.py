"""Brave Search — live advisory / documentation lookups so fixes cite current guidance, not stale training data."""
from __future__ import annotations
import httpx
from .. import config
from ..state import store

URL = "https://api.search.brave.com/res/v1/web/search"

CANNED = {
    "cve": [{"title": "NVD - CVE-2025-31337 remote code execution", "url": "https://nvd.nist.gov/vuln/detail/CVE-2025-31337", "description": "Critical RCE in base image library; upgrade to patched release."}],
    "open_port": [{"title": "Redis security: never expose port 6379 publicly", "url": "https://redis.io/docs/latest/operate/oss_and_stack/management/security/", "description": "Bind to private interfaces, require AUTH, use firewall rules."}],
    "secret_leak": [{"title": "AWS: What to do if you inadvertently expose an access key", "url": "https://repost.aws/knowledge-center/potential-account-compromise", "description": "Rotate the key immediately, audit CloudTrail, revoke sessions."}],
    "tls_expiry": [{"title": "Let's Encrypt renewal and automation", "url": "https://letsencrypt.org/docs/integration-guide/", "description": "Automate renewal 30 days before expiry with ACME."}],
    "brute_force": [{"title": "OWASP Credential Stuffing Prevention Cheat Sheet", "url": "https://cheatsheetseries.owasp.org/cheatsheets/Credential_Stuffing_Prevention_Cheat_Sheet.html", "description": "Rate-limit by IP/ASN, require MFA, deploy device fingerprinting."}],
    "iam_anomaly": [{"title": "NIST SP 800-61 incident handling: contain compromised credentials", "url": "https://csrc.nist.gov/pubs/sp/800/61/r3/final", "description": "Contain, revoke sessions, rotate, then eradicate."}],
    "default": [{"title": "Google SRE Book — Effective Troubleshooting", "url": "https://sre.google/sre-book/effective-troubleshooting/", "description": "Triage, examine, diagnose, test/treat."}],
}


class Brave:
    def __init__(self):
        self.key = config.BRAVE_API_KEY
        self.enabled = bool(self.key)

    async def probe(self):
        store.set_integration("brave", status="connected" if self.enabled else "fallback",
                              detail="live web search" if self.enabled else "BRAVE_API_KEY not set — cached advisories", calls=0)

    async def search(self, query: str, kind: str = "default", count: int = 3) -> list[dict]:
        cur = store.integrations.get("brave", {})
        store.set_integration("brave", calls=cur.get("calls", 0) + 1)
        if not self.enabled:
            return [dict(r, source="cached") for r in CANNED.get(kind, CANNED["default"])]
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(URL, params={"q": query, "count": count}, headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
                r.raise_for_status()
                res = r.json().get("web", {}).get("results", [])[:count]
            return [{"title": x.get("title"), "url": x.get("url"), "description": x.get("description"), "source": "brave"} for x in res]
        except Exception as e:
            store.log("warn", "brave", f"search failed: {e}")
            return [dict(r, source="cached") for r in CANNED.get(kind, CANNED["default"])]


brave = Brave()
