# Wiring Sentinel into DuploCloud DevKit

Sentinel is both a **consumer** of DuploCloud (every remediation is filed as a governed ticket) and a **tool provider**
for the DuploCloud agent (via MCP). Ten minutes, in order:

| Step | Where | What |
|---|---|---|
| 1 | AI Admin → MCP Servers → Add | Name `sentinel-mcp`, Provider Type `Other`/`other`, Config Type `Raw`, paste [`mcp-server.json`](mcp-server.json) |
| 2 | AI Admin → Skills → Add (Custom) | Paste [`skills/sentinel-self-heal/SKILL.md`](skills/sentinel-self-heal/SKILL.md) and [`skills/sentinel-compliance-audit/SKILL.md`](skills/sentinel-compliance-audit/SKILL.md) |
| 3 | AI Admin → Personas → Add | Name + system prompt from [`persona.json`](persona.json); attach both skills |
| 4 | Providers → IT → Other | Provider `sentinel`, Account ID `http://host.docker.internal:8000`, Scope `sentinel-scope` with MCP Server `sentinel-mcp` |
| 5 | Workspaces | Attach `sentinel-scope`, plus your Neo4j / Vultr / Kubernetes scopes; set persona |
| 6 | `.env` (Sentinel) | `DUPLO_TOKEN` (= `DUPLO_ADMIN_TOKEN` from devkit `.env`), `DUPLO_WORKSPACE_ID`, `DUPLO_SCOPE_IDS` (comma-separated scope ids) |

Verify: in AI DevOps create a ticket → *"What incidents is Sentinel tracking and what's the blast radius of payment-service?"*
The agent should call `get_incidents` and `get_blast_radius` on the Sentinel MCP server.

Then inject a fault from Sentinel's Chaos Lab: a `[Sentinel] …` ticket appears in the workspace with the plan, and the
agent executes it with the `sentinel-self-heal` skill.

## Sponsor tools wired (and what each one *does*)
| Tool | Role in Sentinel |
|---|---|
| **DuploCloud** | Governed execution plane: tickets, scopes, skills, persona; agent calls Sentinel over MCP |
| **Neo4j** | Service dependency graph; blast-radius Cypher queries drive triage + impact analysis |
| **Nebius** (via OpenRouter preset) | Fast triage model on Nebius GPUs; Nebius compute API for GPU/instance actions |
| **Vultr** | Instance reboot / halt, firewall rule patching for exposed ports |
| **Brave Search** | Live advisory lookups (CVE, hardening guides) cited in plans and IaC |
| **Claude (Anthropic)** | Root-cause diagnosis, structured remediation plans, Terraform generation, copilot chat |
