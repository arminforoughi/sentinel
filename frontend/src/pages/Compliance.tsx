import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import ReactMarkdown from 'react-markdown'
import { useStore } from '../lib/store'
import { Panel, Pill, fmtT } from '../components/ui'
export default function Compliance() {
  const { reports, findings, incidents } = useStore(); const [id, setId] = useState<string | null>(null)
  const rep = reports.find(r => r.id === id) || reports[0]
  const [chain, setChain] = useState<{ ok: boolean; length: number; head?: string } | null>(null)
  useEffect(() => { api.chain().then(setChain) }, [reports.length])
  const ctrls: Record<string, { sat: number; gap: number }> = {}
  for (const r of reports) for (const c of r.controls) { const k = ctrls[c.id] ||= { sat: 0, gap: 0 }; c.status === 'satisfied' ? k.sat++ : k.gap++ }
  for (const f of findings.filter(f => f.status === 'open')) for (const c of f.controls) { (ctrls[c] ||= { sat: 0, gap: 0 }).gap++ }
  const fw = (id: string) => id.split(' ')[0]
  const groups = Object.entries(ctrls).reduce((a, [k, v]) => { (a[fw(k)] ||= []).push([k, v]); return a }, {} as Record<string, [string, { sat: number; gap: number }][]>)
  return <div className="page">
    <Panel title="Control coverage" sub="evidence generated automatically from every incident and posture fix"><div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>{Object.entries(groups).map(([g, cs]) => <div key={g}><div className="section-title">{g} · {cs.filter(([, v]) => v.gap === 0).length}/{cs.length} satisfied</div><div className="ctrl-grid">{cs.map(([k, v]) => <div key={k} className={`ctrl ${v.gap ? 'gap' : 'satisfied'}`}><b>{k}</b><span className="muted">{v.gap ? `${v.gap} gap` : `${v.sat} evidence`}</span></div>)}</div></div>)}{Object.keys(groups).length === 0 && <div className="empty">Controls populate as incidents resolve and findings are fixed.</div>}</div></Panel>
    <div className="grid g-1-2">
      <Panel title="Audit reports" sub="tamper-evident ledger" right={chain && <Pill tone={chain.ok ? 'ok' : 'crit'}>⛓ chain {chain.ok ? 'verified' : 'BROKEN'} · {chain.length}</Pill>}><div className="feed">{reports.map(r => <div key={r.id} className="feed-item" onClick={() => setId(r.id)} style={rep?.id === r.id ? { background: 'rgba(56,226,199,.06)' } : undefined}><div className="sev" style={{ background: r.subject_type === 'incident' ? 'var(--violet)' : 'var(--accent)' }} /><div><div className="ttl">{r.title}</div><div className="meta"><Pill tone={r.subject_type === 'incident' ? 'violet' : 'accent'}>{r.subject_type}</Pill><span>{fmtT(r.created_at)}</span><span className="chain">⛓ {r.hash?.slice(0, 10)}</span></div></div></div>)}{reports.length === 0 && <div className="empty">No reports yet — {incidents.length ? 'reports appear when incidents resolve' : 'inject a fault to generate one'}.</div>}</div></Panel>
      <Panel title={rep?.title || 'Report'} right={rep && <a className="btn sm" href={`/api/reports/${rep.id}.md`} target="_blank">Export .md</a>}><div className="panel-b md">{rep ? <ReactMarkdown>{rep.markdown}</ReactMarkdown> : <div className="empty">Select a report.</div>}</div></Panel>
    </div></div>
}
