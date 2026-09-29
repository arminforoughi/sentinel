import { useState } from 'react'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Panel, Pill, Stat, sevClass, statusClass } from '../components/ui'
import type { Finding } from '../lib/types'
export default function Posture() {
  const { findings } = useStore(); const [dom, setDom] = useState<'all' | Finding['domain']>('all'); const [sel, setSel] = useState<Finding | null>(null); const [busy, setBusy] = useState<string | null>(null)
  const list = findings.filter(f => dom === 'all' || f.domain === dom)
  const open = findings.filter(f => f.status === 'open'); const fixed = findings.filter(f => f.status === 'fixed')
  const cur = sel ? findings.find(f => f.id === sel.id) || sel : null
  const run = async (fn: () => Promise<unknown>, id: string) => { setBusy(id); try { await fn() } finally { setBusy(null) } }
  return <div className="page">
    <div className="grid g4"><Stat label="Open findings" value={open.length} delta={`${open.filter(f => f.severity === 'high' || f.severity === 'critical').length} high+`} color="var(--warn)" /><Stat label="Fixed by Sentinel" value={fixed.length} delta="via DuploCloud tickets" color="var(--ok)" /><Stat label="Savings identified" value={`$${Math.round(open.reduce((a, f) => a + f.monthly_savings, 0)).toLocaleString()}`} unit="/mo" color="var(--warn)" /><Stat label="Savings realised" value={`$${Math.round(fixed.reduce((a, f) => a + f.monthly_savings, 0)).toLocaleString()}`} unit="/mo" color="var(--ok)" /></div>
    <div className="grid g-3-2">
      <Panel title="Cloud posture findings" sub="security · governance · cost" right={<><div className="toggle">{(['all', 'security', 'governance', 'cost'] as const).map(d => <button key={d} className={dom === d ? 'on' : ''} onClick={() => setDom(d)}>{d}</button>)}</div><button className="btn sm" onClick={() => api.runAudit()}>Re-audit</button></>}>
        <table className="t"><thead><tr><th>Sev</th><th>Finding</th><th>Resource</th><th>Domain</th><th>Savings</th><th>Status</th></tr></thead><tbody>{list.map(f => <tr key={f.id} className="clickable" onClick={() => setSel(f)} style={cur?.id === f.id ? { background: 'rgba(56,226,199,.06)' } : undefined}><td><Pill tone={sevClass(f.severity)}>{f.severity}</Pill></td><td style={{ fontWeight: 600 }}>{f.title}</td><td className="mono muted">{f.resource}</td><td><Pill tone={f.domain === 'security' ? 'crit' : f.domain === 'cost' ? 'warn' : 'info'}>{f.domain}</Pill></td><td className="mono">{f.monthly_savings ? `$${f.monthly_savings}/mo` : '—'}</td><td><Pill tone={statusClass(f.status)} pulse={f.status === 'fixing'}>{f.status}</Pill></td></tr>)}</tbody></table></Panel>
      <Panel title={cur ? cur.title : 'Select a finding'} sub={cur?.cloud}>{!cur ? <div className="empty">Pick a finding to see the fix, generate Terraform, or remediate through DuploCloud.</div> : <div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ color: 'var(--text-2)' }}>{cur.detail}</div>
        <div><div className="section-title">Controls</div><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{cur.controls.map(c => <Pill key={c} tone="outline">{c}</Pill>)}</div></div>
        <div><div className="section-title">Fix</div>{cur.fix_kind === 'action' ? <div className="action-card" style={{ gridTemplateColumns: '1fr auto' }}><div><div className="k">{String(cur.fix_action.kind)}</div><div className="muted" style={{ fontSize: 11.5 }}>{JSON.stringify(cur.fix_action).slice(0, 120)}</div></div><Pill tone="violet">action</Pill></div> : <Pill tone="violet">infrastructure-as-code</Pill>}</div>
        {cur.iac && <div><div className="section-title">Generated Terraform · Claude + Brave refs</div><pre className="code">{cur.iac}</pre></div>}
        {!!cur.fix_action.ticket && <div className="muted" style={{ fontSize: 12 }}>DuploCloud ticket <span className="mono">{String(cur.fix_action.ticket)}</span></div>}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {cur.fix_kind === 'iac' && cur.status === 'open' && <button className="btn" disabled={busy === cur.id} onClick={() => run(() => api.iac(cur.id), cur.id)}>{busy === cur.id ? 'Generating…' : 'Generate Terraform'}</button>}
          {cur.status === 'open' && <button className="btn primary" disabled={busy === cur.id} onClick={() => run(() => api.fix(cur.id), cur.id)}>{busy === cur.id ? 'Remediating…' : 'Remediate via DuploCloud'}</button>}
          {cur.status === 'open' && <button className="btn ghost" onClick={() => api.accept(cur.id)}>Accept risk</button>}
        </div></div>}</Panel>
    </div></div>
}
