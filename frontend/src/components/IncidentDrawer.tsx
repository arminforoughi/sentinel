import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Incident } from '../lib/types'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Pill, sevClass, statusClass, fmtT } from './ui'

const icons: Record<string, string> = { detected: '!', triage: 'T', diagnosis: 'D', plan: 'P', rehearsal: 'R', approval: 'A', action: '▶', verify: '✓', audit: '§', note: '·' }
export default function IncidentDrawer({ inc, onClose }: { inc: Incident; onClose: () => void }) {
  const { reports } = useStore()
  const [tab, setTab] = useState<'timeline' | 'report'>('timeline')
  const rep = reports.find(r => r.id === inc.report_id)
  return <><div className="backdrop" onClick={onClose} /><div className="drawer">
    <div className="drawer-h"><div style={{ flex: 1 }}><div style={{ display: 'flex', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}><Pill tone={sevClass(inc.severity)}>{inc.severity}</Pill><Pill tone={statusClass(inc.status)} pulse={!['resolved', 'failed'].includes(inc.status)}>{inc.status.replace('_', ' ')}</Pill><Pill tone="neutral">{inc.category}</Pill><span className="mono muted" style={{ fontSize: 11 }}>{inc.id}</span></div>
      <h3 style={{ margin: 0, fontSize: 16 }}>{inc.title}</h3><div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{inc.service} · detected {fmtT(inc.detected_at)}{inc.mttr_seconds != null && <> · MTTR <b className="mono" style={{ color: 'var(--ok)' }}>{inc.mttr_seconds}s</b></>}</div></div>
      <button className="btn ghost" onClick={onClose}>✕</button></div>
    <div className="tabs"><button className={tab === 'timeline' ? 'on' : ''} onClick={() => setTab('timeline')}>Agent timeline</button><button className={tab === 'report' ? 'on' : ''} onClick={() => setTab('report')} disabled={!rep}>Audit report {rep ? '' : '(pending)'}</button></div>
    <div className="drawer-b">
      {tab === 'timeline' ? <>
        {inc.status === 'awaiting_approval' && <div className="panel" style={{ padding: 14, borderColor: 'rgba(255,182,72,.4)', display: 'flex', alignItems: 'center', gap: 12 }}><div style={{ flex: 1 }}><b>Approval required</b><div className="muted" style={{ fontSize: 12 }}>Plan includes a high-risk action or approval mode is on.</div></div><button className="btn primary" onClick={() => api.approve(inc.id)}>Approve & execute</button></div>}
        {inc.root_cause && <div><div className="section-title">Root cause · {inc.reasoning_source} · {Math.round(inc.confidence * 100)}% confidence</div><div style={{ fontSize: 13, color: 'var(--text-2)' }}>{inc.root_cause}</div></div>}
        {inc.blast_radius.length > 0 && <div><div className="section-title">Blast radius · {inc.blast_radius_source}</div><div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>{inc.blast_radius.map(b => <Pill key={b} tone="warn">{b}</Pill>)}</div></div>}
        {inc.actions.length > 0 && <div><div className="section-title">Remediation plan</div><div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>{inc.actions.map((a, i) => <div key={a.id} className="action-card"><div className="steps">{i + 1}</div><div><div className="k">{a.kind} <span className="muted">→</span> {a.target}</div><div className="muted" style={{ fontSize: 11.5 }}>{String(a.evidence.rationale || a.evidence.note || '')} · via {a.executor} · risk {a.risk}</div></div><Pill tone={a.status === 'succeeded' ? 'ok' : a.status === 'failed' ? 'crit' : a.status === 'running' ? 'accent' : 'neutral'} pulse={a.status === 'running'}>{a.status.replace('_', ' ')}</Pill></div>)}</div></div>}
        {inc.rehearsal?.rows && <div><div className="section-title">Digital-twin rehearsal {inc.rehearsal.reordered && <Pill tone="accent">plan re-ordered</Pill>}</div>
          <div className="rehearsal">{inc.rehearsal.rows.map(r => <div key={r.action} className={`rh ${r.kind === inc.rehearsal.chosen ? 'chosen' : ''} ${r.veto ? 'veto' : ''}`}><span className="sc" style={{ color: r.score > 12 ? 'var(--crit)' : r.score > 5 ? 'var(--warn)' : 'var(--ok)' }}>{r.score}</span><div><div className="mono" style={{ fontWeight: 600 }}>{r.kind} → {r.target}</div><div className="muted" style={{ fontSize: 11 }}>{r.disrupts.length ? `disrupts ${r.disrupts.slice(0, 4).join(', ')}${r.disrupts.length > 4 ? ` +${r.disrupts.length - 4}` : ''} for ~${r.seconds}s` : 'no collateral disruption'}{!r.heals && ' · does not clear this fault'}</div></div><Pill tone={r.trust >= .8 ? 'ok' : 'warn'}>trust {Math.round(r.trust * 100)}%</Pill>{r.kind === inc.rehearsal.chosen ? <Pill tone="ok">chosen</Pill> : r.veto ? <Pill tone="crit">vetoed</Pill> : <span />}</div>)}</div>
          <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>Score = tier-weighted services the <i>fix itself</i> disrupts × duration. Sentinel simulates each step on the dependency graph and executes the least disruptive healing step first.</div></div>}
        {inc.ticket?.name && <div><div className="section-title">DuploCloud ticket</div><div className="action-card" style={{ gridTemplateColumns: '1fr auto' }}><div><div className="k">{inc.ticket.name}</div><div className="muted" style={{ fontSize: 11.5 }}>{inc.ticket.simulated ? 'simulated — set DUPLO_TOKEN to file real tickets' : 'filed in workspace'}</div></div>{inc.ticket.url && !inc.ticket.simulated ? <a className="btn sm" href={inc.ticket.url} target="_blank">Open ↗</a> : <Pill tone="neutral">sim</Pill>}</div></div>}
        {inc.references.length > 0 && <div><div className="section-title">Live references · Brave</div>{inc.references.map(r => <div key={r.url} style={{ fontSize: 12, marginBottom: 4 }}><a href={r.url} target="_blank">{r.title}</a> <span className="muted">· {r.source}</span></div>)}</div>}
        <div><div className="section-title">Timeline</div><div className="timeline">{inc.timeline.map((t, i) => <div className="tl" key={i}><div className="ic">{icons[t.phase] || '·'}</div><div><div className="t">{t.title}<time>{fmtT(t.ts)}</time></div>{t.body && <div className="b">{t.body}</div>}</div></div>)}</div></div>
      </> : rep && <><div style={{ display: 'flex', gap: 8 }}><a className="btn sm" href={`/api/reports/${rep.id}.md`} target="_blank">Download .md</a></div><div className="md"><ReactMarkdown>{rep.markdown}</ReactMarkdown></div></>}
    </div></div></>
}
