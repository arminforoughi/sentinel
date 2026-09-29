# Sentinel — Self-Healing DevOps & Security Copilot

An AI operations engineer that **monitors** a multi-cloud microservice estate, **detects** uptime and security drops,
**diagnoses** root cause with the dependency graph, **provisions fixes** through DuploCloud, **verifies** recovery,
and **generates compliance evidence** (SOC 2 / ISO 27001 / PCI DSS / NIST CSF). It also runs a continuous
**security / governance / cost audit** and fixes findings with actions or generated Terraform.

```
detect → blast radius (Neo4j) → triage (Nebius via OpenRouter) → advisories (Brave)
→ diagnose + plan (Claude, structured) → approval gate → DuploCloud ticket + Vultr/Nebius executors
→ verify recovery → audit report
```

## What's different from other "AI ops" demos
- **Digital-twin rehearsal.** Before executing, Sentinel simulates every planned action on the dependency graph and scores the
  disruption *the fix itself* would cause (tier-weighted upstream services × duration). It re-orders the plan least-disruptive-first
  and vetoes steps above a policy threshold. Restarting a datastore that 9 services depend on loses to a rollback.
- **Earned autonomy.** A trust ledger tracks every action type's verified outcomes. Actions above the trust threshold auto-execute;
  unproven or high-risk ones wait for a human. Trust goes up when a fix verifies and down when it doesn't, so autonomy is earned, not granted.
- **Tamper-evident audit ledger.** Every compliance report commits to the SHA-256 of the previous one; `/api/audit/chain` verifies it.
- **Error budgets, not just thresholds.** Every service carries an SLO, remaining error budget and burn rate, all tunable live from the Policy page.

## Run (60 seconds, no keys needed)
```bash
./run.sh
```
Open http://localhost:5173 → **Start guided demo** on the landing page → watch the console heal a crashed payment-service.
Console lives at `/overview`; Chaos Lab lets you inject any of 11 fault types.
Every integration falls back to a simulated executor when its key is missing, so the full loop always runs.

## Wire the sponsors
Copy `.env.example` to `.env` and fill any of: `ANTHROPIC_API_KEY`, `NEO4J_URI`/`NEO4J_PASSWORD`, `DUPLO_TOKEN`/`DUPLO_WORKSPACE_ID`,
`OPENROUTER_API_KEY` (+ Nebius preset), `VULTR_API_KEY`, `NEBIUS_IAM_TOKEN`, `BRAVE_API_KEY`.
DuploCloud skills, persona, and MCP config live in [`duplocloud/`](duplocloud/README.md).

## Layout
- `backend/app/monitor.py` — telemetry simulator, chaos engine, detectors (faults propagate through the graph)
- `backend/app/agent.py` — the pipeline; Claude structured planning; IaC generation; copilot chat with tools
- `backend/app/graph.py` — Neo4j blast radius with in-memory fallback
- `backend/app/executor.py` — routes actions to DuploCloud / Vultr / Nebius
- `backend/app/audit.py` — posture auditor + compliance reports
- `backend/app/mcp_server.py` — MCP server so the DuploCloud agent can call Sentinel
- `frontend/` — React ops console (topology graph, incident timelines, posture, compliance, chaos lab, copilot)
