export interface Metric {
  service: string; ts: number; status: 'healthy' | 'degraded' | 'down'
  latency_p95: number; error_rate: number; cpu: number; mem: number; rps: number
  findings: string[]; cloud: string; tier: string; pressure: number; slo: number; burn_rate: number; budget_remaining: number
}
export interface TimelineEntry { ts: number; phase: string; title: string; body: string; meta: Record<string, unknown> }
export interface Action {
  id: string; incident_id: string; kind: string; target: string; params: Record<string, unknown>
  risk: 'low' | 'medium' | 'high'; status: string; executor: string; evidence: Record<string, unknown>
  started_at: number | null; finished_at: number | null
}
export interface Incident {
  id: string; service: string; category: string; kind: string; severity: string; title: string
  detected_at: number; status: string; summary: string; root_cause: string; confidence: number
  blast_radius: string[]; blast_radius_source: string; reasoning_source: string; triage_source: string
  actions: Action[]; timeline: TimelineEntry[]; resolved_at: number | null; mttr_seconds: number | null
  ticket: { name?: string; url?: string; simulated?: boolean }; references: { title: string; url: string; description?: string; source?: string }[]
  report_id: string | null; fault_id: string | null; rehearsal: Rehearsal
}
export interface Rehearsal { rows?: { action: string; kind: string; target: string; disrupts: string[]; seconds: number; score: number; heals: boolean; veto: boolean; trust: number }[]; reordered?: boolean; chosen?: string | null; expected_downtime_s?: number | null; avoided?: string[] }
export interface Finding {
  id: string; domain: 'security' | 'governance' | 'cost'; severity: string; title: string; resource: string
  cloud: string; detail: string; detected_at: number; status: string; monthly_savings: number
  fix_kind: string; fix_action: Record<string, unknown>; iac: string; controls: string[]; fixed_at: number | null
  references: { title: string; url: string }[]
}
export interface Report {
  id: string; created_at: number; subject_type: string; subject_id: string; title: string; summary: string
  controls: { id: string; text: string; status: string }[]; evidence: unknown[]; markdown: string; prev_hash: string; hash: string
}
export interface Trust { kind: string; success: number; total: number; score: number }
export type Policy = Record<string, number | boolean>
export interface LogEntry { ts: number; level: string; source: string; message: string; meta: Record<string, unknown> }
export interface Integration { name: string; status: string; detail?: string; calls?: number; tickets?: number }
export interface Snapshot {
  metrics: Record<string, Metric>; incidents: Incident[]; findings: Finding[]; reports: Report[]; logs: LogEntry[]
  integrations: Record<string, Integration>; autonomy: string; policy: Policy; trust: Trust[]
  stats: { incidents_total: number; auto_resolved: number; actions_executed: number; savings_identified: number }
  started_at: number; history: Record<string, number[][]>
}
export interface GraphData { source: string; nodes: { name: string; tier: string; cloud: string; runtime: string; owner: string; image: string }[]; edges: { source: string; target: string }[] }
