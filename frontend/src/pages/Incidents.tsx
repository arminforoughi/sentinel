import { useState } from 'react'
import { useStore } from '../lib/store'
import { Panel, Pill, sevClass, statusClass, fmtT } from '../components/ui'
import IncidentDrawer from '../components/IncidentDrawer'
export default function Incidents() {
  const { incidents } = useStore(); const [id, setId] = useState<string | null>(null)
  const sel = incidents.find(i => i.id === id)
  return <div className="page"><Panel title="Incidents" sub={`${incidents.length} total · ${incidents.filter(i => i.status === 'resolved').length} resolved`}>
    {incidents.length === 0 ? <div className="empty">No incidents yet.</div> : <table className="t"><thead><tr><th>ID</th><th>Severity</th><th>Incident</th><th>Service</th><th>Status</th><th>Blast</th><th>Reasoning</th><th>MTTR</th><th>Detected</th></tr></thead><tbody>
      {incidents.map(i => <tr key={i.id} className="clickable" onClick={() => setId(i.id)}><td className="mono muted">{i.id}</td><td><Pill tone={sevClass(i.severity)}>{i.severity}</Pill></td><td style={{ fontWeight: 600 }}>{i.title}</td><td className="mono">{i.service}</td><td><Pill tone={statusClass(i.status)} pulse={!['resolved', 'failed'].includes(i.status)}>{i.status.replace('_', ' ')}</Pill></td><td className="mono">{i.blast_radius.length}</td><td className="muted">{i.reasoning_source || '—'}</td><td className="mono" style={{ color: 'var(--ok)' }}>{i.mttr_seconds != null ? `${i.mttr_seconds}s` : '—'}</td><td className="mono muted">{fmtT(i.detected_at)}</td></tr>)}
    </tbody></table>}</Panel>{sel && <IncidentDrawer inc={sel} onClose={() => setId(null)} />}</div>
}
