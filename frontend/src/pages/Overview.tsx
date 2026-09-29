import { useState } from 'react'
import { useStore } from '../lib/store'
import { Stat, Panel, Pill, Ring, Spark, sevClass, statusClass, ago, fmtT } from '../components/ui'
import Topology from '../components/Topology'
import IncidentDrawer from '../components/IncidentDrawer'
import TrustLedger from '../components/TrustLedger'
import type { Incident } from '../lib/types'

export default function Overview() {
  const s = useStore()
  const [sel, setSel] = useState<Incident | null>(null)
  const svcs = Object.values(s.metrics)
  const healthy = svcs.filter(m => m.status === 'healthy').length
  const health = svcs.length ? (healthy / svcs.length) * 100 : 100
  const open = s.incidents.filter(i => !['resolved', 'failed'].includes(i.status))
  const resolved = s.incidents.filter(i => i.status === 'resolved')
  const mttr = resolved.length ? resolved.reduce((a, i) => a + (i.mttr_seconds || 0), 0) / resolved.length : 0
  const openF = s.findings.filter(f => f.status === 'open')
  const posture = Math.max(0, 100 - openF.reduce((a, f) => a + ({ critical: 12, high: 8, medium: 4, low: 1 } as any)[f.severity], 0))
  const live = s.incidents.find(i => !['resolved', 'failed'].includes(i.status))
  return <div className="page">
    <div className="grid g4">
      <Stat label="Platform health" value={<span style={{ color: health > 90 ? 'var(--ok)' : health > 70 ? 'var(--warn)' : 'var(--crit)' }}>{health.toFixed(0)}%</span>} delta={`${healthy}/${svcs.length} services healthy`} color={health > 90 ? 'var(--ok)' : 'var(--warn)'} />
      <Stat label="Open incidents" value={open.length} delta={<>{s.stats.auto_resolved} auto-resolved · {s.stats.incidents_total} total</>} color={open.length ? 'var(--crit)' : 'var(--accent)'} />
      <Stat label="Mean time to repair" value={mttr ? mttr.toFixed(1) : '—'} unit="s" delta="detect → diagnose → fix → verify" color="var(--violet)" />
      <Stat label="Savings identified" value={`$${Math.round(s.stats.savings_identified).toLocaleString()}`} unit="/mo" delta={`${openF.length} open posture findings`} color="var(--warn)" />
    </div>
    <div className="grid g-2-1">
      <Panel title="Service topology" sub="live · click a node for blast radius" right={live && <Pill tone="crit" pulse>healing {live.service}</Pill>}><Topology compact focus={live?.service} /></Panel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Panel title="Security posture" sub="continuous audit"><div className="panel-b ring-wrap"><Ring value={posture} color={posture > 80 ? 'var(--ok)' : posture > 60 ? 'var(--warn)' : 'var(--crit)'} label="SCORE" /><div style={{ fontSize: 12.5, display: 'flex', flexDirection: 'column', gap: 6 }}>{(['security', 'governance', 'cost'] as const).map(d => { const n = openF.filter(f => f.domain === d).length; return <div key={d} style={{ display: 'flex', gap: 8, alignItems: 'center' }}><span style={{ width: 84, textTransform: 'capitalize' }} className="dim">{d}</span><Pill tone={n ? 'warn' : 'ok'}>{n} open</Pill></div> })}</div></div></Panel>
        <Panel title="Incident feed" sub={`${s.incidents.length} total`}><div className="feed" style={{ maxHeight: 250, overflow: 'auto' }}>{s.incidents.length === 0 && <div className="empty">All quiet. Inject a fault from Chaos Lab to watch Sentinel heal it.</div>}{s.incidents.slice(0, 8).map(i => <div key={i.id} className="feed-item" onClick={() => setSel(i)}><div className="sev" style={{ background: `var(--${sevClass(i.severity)})` }} /><div><div className="ttl">{i.title}</div><div className="meta"><Pill tone={statusClass(i.status)} pulse={!['resolved', 'failed'].includes(i.status)}>{i.status.replace('_', ' ')}</Pill>{i.mttr_seconds != null && <span className="mono">MTTR {i.mttr_seconds}s</span>}<span>{ago(i.detected_at)}</span></div></div></div>)}</div></Panel>
      </div>
    </div>
    <div className="grid g-3-2">
      <Panel title="Services" sub="p95 · errors · error budget · cpu" right={<span className="muted" style={{ fontSize: 11 }}>SLO {String(s.policy.slo_core ?? '99.9')}% core</span>}><div>{svcs.sort((a, b) => (a.status === 'healthy' ? 1 : 0) - (b.status === 'healthy' ? 1 : 0) || a.service.localeCompare(b.service)).map(m => { const h = s.history[m.service] || []; return <div className="svc-row" key={m.service}><div><span className="mono" style={{ fontWeight: 600 }}>{m.service}</span> <span className="muted" style={{ fontSize: 11 }}>{m.cloud} · {m.tier}</span></div><Pill tone={m.status === 'healthy' ? 'ok' : m.status === 'down' ? 'crit' : 'warn'}>{m.status}</Pill><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Spark data={h.map(x => x[1])} color={m.status === 'healthy' ? 'var(--accent)' : 'var(--crit)'} /><span className="mono" style={{ fontSize: 12 }}>{m.latency_p95}ms</span></div><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Spark data={h.map(x => x[2])} color="var(--warn)" /><span className="mono" style={{ fontSize: 12 }}>{(m.error_rate * 100).toFixed(1)}%</span></div><div className="budget" title={`error budget ${m.budget_remaining}% · burn ${m.burn_rate}x`}><div className="bar" style={{ flex: 1 }}><i style={{ width: `${m.budget_remaining ?? 100}%`, background: (m.budget_remaining ?? 100) > 50 ? 'var(--ok)' : (m.budget_remaining ?? 100) > 20 ? 'var(--warn)' : 'var(--crit)' }} /></div>{(m.burn_rate ?? 0) > 2 && <span className="mono" style={{ fontSize: 10, color: 'var(--crit)' }}>{m.burn_rate}x</span>}</div><div className="bar"><i style={{ width: `${m.cpu}%`, background: m.cpu > 85 ? 'var(--crit)' : 'var(--violet)' }} /></div></div> })}</div></Panel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}><TrustLedger compact /><Panel title="Agent activity" sub="live log"><div className="logs">{s.logs.slice(-40).reverse().map((l, i) => <div key={i} className={`l ${l.level}`}><span className="muted">{fmtT(l.ts)}</span><span className="src">{l.source}</span><span className="msg">{l.message}</span></div>)}</div></Panel></div>
    </div>
    {sel && <IncidentDrawer inc={s.incidents.find(i => i.id === sel.id) || sel} onClose={() => setSel(null)} />}
  </div>
}
