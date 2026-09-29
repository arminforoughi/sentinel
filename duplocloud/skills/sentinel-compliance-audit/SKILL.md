---
name: sentinel-compliance-audit
description: Run or apply a Sentinel cloud posture audit (security, governance, cost) and produce compliance evidence mapped to SOC 2, ISO 27001, PCI DSS and NIST CSF. Use for tickets titled "[Sentinel] <finding>" with a posture-fix purpose, or when asked for an audit / compliance report / cost review.
---

# Sentinel compliance audit

## When asked for an audit
1. Call the Sentinel MCP tool `get_findings` (optionally filtered by `domain`: security | governance | cost).
2. Summarise findings by domain with severity counts and total `monthly_savings`.
3. Call `get_audit_reports` and cite the latest posture report id.

## When applying a posture fix
1. The ticket contains either an `Action` (e.g. `stop_instance`, `apply_tags`, `enable_encryption`, `patch_image`, `delete_volume`) or a Terraform snippet.
2. For an Action: execute it with the matching cloud scope (Vultr / Nebius). Take a snapshot before any `delete_volume` or `stop_instance`.
3. For Terraform: write the snippet to `sentinel/<finding-id>.tf`, run `terraform plan`, post the plan summary to the ticket, then `terraform apply` only if the plan touches exactly the resource named in the finding.
4. Call `fix_finding` with the finding id so Sentinel records the fix and regenerates the posture report.
5. Close the ticket as resolved, quoting the control ids satisfied (from the finding's `controls`).

## Evidence standard
Every closed ticket must contain: what was found, what changed, who/what executed it, when, and the controls it satisfies.
