---
name: sentinel-self-heal
description: Execute a Sentinel self-healing remediation plan for a production incident. Use when a ticket titled "[Sentinel]" arrives with a root cause, blast radius and an ordered plan of actions (restart, scale, rollback, rotate_secret, patch_firewall, quarantine, revoke_sessions, rate_limit, renew_cert, patch_image, revoke_iam, clear_cache, failover).
---

# Sentinel self-heal runbook

You are executing a remediation plan produced by Sentinel, the self-healing DevOps & security copilot.
The ticket body contains: root cause, blast radius (from Neo4j), an ordered action list, and a verification criterion.

## Procedure
1. Call the Sentinel MCP tool `get_incidents` to confirm the incident is still open and read its current status.
2. Call `get_blast_radius` for the affected service; if the blast radius includes `payment-service` or `checkout-service`, treat the incident as revenue-impacting and execute immediately.
3. Execute the actions **in order**. Stop as soon as `get_metrics` for the service shows `status: healthy` and `error_rate < 0.02`.
   - `restart` / `scale` / `rollback` → use the Kubernetes scope (kubectl rollout restart / scale / rollout undo).
   - `patch_firewall` → use the Vultr scope: add an ingress rule restricting the port to the VPC CIDR and remove the 0.0.0.0/0 rule.
   - `rotate_secret` / `revoke_iam` / `revoke_sessions` → use the cloud IAM scope; rotate, then invalidate active sessions.
   - `renew_cert` → trigger ACME renewal on the edge.
   - `rate_limit` / `quarantine` → apply the gateway policy for the listed ASNs / IP ranges.
4. After each step, post a one-line result to the ticket: `step N <action> <target> → ok|failed <evidence>`.
5. When the verification criterion is met, call `get_audit_reports` and attach the report id to the ticket, then close it as resolved.

## Guardrails
- Never execute `quarantine`, `revoke_iam` or `failover` without an explicit approval message on the ticket.
- Prefer the least invasive action that satisfies the verification criterion.
- If an action fails twice, stop and escalate with the failure evidence.
