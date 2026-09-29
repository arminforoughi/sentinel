import { useStore } from '../lib/store'
import { Panel, Pill, statusClass } from '../components/ui'
const META: Record<string, { label: string; role: string; prize?: string }> = {
  duplocloud: { label: 'DuploCloud', role: 'Governed execution plane: every remediation and posture fix is filed as a workspace ticket with the Sentinel persona + skills. The DuploCloud agent calls Sentinel back over MCP.', prize: 'Best Agent on DuploCloud' },
  mcp: { label: 'Sentinel MCP server', role: 'Exposes get_incidents, get_blast_radius, get_metrics, get_findings, get_audit_reports, fix_finding, inject_fault, approve_incident to the DuploCloud agent.' },
  neo4j: { label: 'Neo4j', role: 'Service dependency graph. Blast-radius Cypher queries (DEPENDS_ON*1..5) drive triage, impact analysis and fault propagation.' },
  openrouter: { label: 'Nebius / Crusoe via OpenRouter', role: 'Fast triage model pinned to Nebius GPUs by preset; runs on every incident before the expensive reasoning step.' },
  nebius: { label: 'Nebius AI Cloud', role: 'Compute executor for the EU estate: GPU node restart/stop, replica scaling, idle-H100 shutdown from cost audits.' },
  vultr: { label: 'Vultr', role: 'Compute executor for the US estate: instance reboot/halt and firewall rule patching for exposed ports.' },
  brave: { label: 'Brave Search', role: 'Live advisory and documentation lookups (CVE, hardening guides) cited in every plan and generated Terraform.' },
  claude: { label: 'Claude (Anthropic)', role: 'Root-cause diagnosis with structured remediation plans, Terraform generation, and the Copilot chat with tool use.' },
}
export default function Integrations() {
  const { integrations } = useStore(); const list = Object.keys(META).map(k => ({ ...(integrations[k] || { name: k, status: 'unknown' }), ...META[k] }))
  const wired = list.filter(i => ['connected', 'ready', 'fallback'].includes(i.status)).length
  return <div className="page"><Panel title="Sponsor tools wired together" sub={`${wired} tools active · each one does real work in the pipeline`}><div className="panel-b grid g4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>{list.map(i => <div key={i.name} className="panel integ"><div className="name">{i.label}<span style={{ marginLeft: 'auto' }} /><Pill tone={statusClass(i.status)} pulse={i.status === 'connected'}>{i.status}</Pill></div><div className="role">{i.role}</div>{i.prize && <Pill tone="accent">🏆 {i.prize}</Pill>}<div className="foot"><span className="mono">{i.calls ?? 0} calls</span>{i.tickets != null && <span className="mono">{i.tickets} tickets</span>}<span style={{ marginLeft: 'auto' }}>{i.detail}</span></div></div>)}</div></Panel>
    <Panel title="Wiring guide" sub="duplocloud/README.md"><div className="panel-b dim" style={{ fontSize: 12.5 }}>Register <span className="kbd">POST /mcp</span> as an MCP server in DuploCloud AI Admin, paste the two SKILL.md files, attach the persona to your workspace, then set <span className="kbd">DUPLO_TOKEN</span> / <span className="kbd">DUPLO_WORKSPACE_ID</span> in <span className="kbd">.env</span>. Tools show <b>fallback</b> when no credentials are configured and still run the full pipeline with simulated executors.</div></Panel></div>
}
