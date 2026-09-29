import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { Panel, Pill } from '../components/ui'
import TrustLedger from '../components/TrustLedger'

const GROUPS: { title: string; sub: string; keys: [string, string, string?][] }[] = [
  { title: 'Detection', sub: 'when a service counts as degraded', keys: [['error_rate_threshold', 'Error-rate threshold', 'fraction of requests'], ['latency_multiplier', 'Latency multiplier', '× baseline p95'], ['cpu_threshold', 'CPU threshold', '%'], ['mem_threshold', 'Memory threshold', '%'], ['detect_min_age_s', 'Samples before alerting', 'seconds']] },
  { title: 'SLOs', sub: 'error budgets and burn rate derive from these', keys: [['slo_core', 'Core / edge / data SLO', '% availability'], ['slo_async', 'Async / ML SLO', '% availability']] },
  { title: 'Autonomy', sub: 'earned-autonomy thresholds', keys: [['trust_threshold', 'Trust to auto-execute', '0–1'], ['high_risk_trust_threshold', 'Trust for high-risk actions', '0–1']] },
  { title: 'Rehearsal', sub: 'digital-twin simulation before execution', keys: [['rehearsal_enabled', 'Rehearse plans on the twin'], ['max_fix_disruption', 'Max fix-disruption score', 'veto above'], ['blast_depth', 'Blast-radius depth', 'graph hops'], ['verify_window_s', 'Verification window', 'seconds']] },
  { title: 'Simulation', sub: 'demo telemetry engine', keys: [['tick_s', 'Tick interval', 'seconds'], ['auto_chaos', 'Random chaos'], ['chaos_interval_s', 'Chaos interval', 'seconds']] },
]
export default function Policy() {
  const { policy, autonomy } = useStore(); const [draft, setDraft] = useState<Record<string, number | boolean>>({}); const [saved, setSaved] = useState(false)
  useEffect(() => { setDraft(policy) }, [policy])
  const dirty = Object.keys(draft).some(k => draft[k] !== policy[k])
  const save = async () => { await api.setPolicy(draft); setSaved(true); setTimeout(() => setSaved(false), 1800) }
  return <div className="page">
    <div className="grid g-2-1">
      <Panel title="Operating policy" sub="live · applied on the next tick" right={<>{saved && <Pill tone="ok">saved</Pill>}<button className="btn ghost sm" onClick={() => api.resetPolicy()}>Reset</button><button className="btn primary sm" disabled={!dirty} onClick={save}>Apply</button></>}>
        <div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>{GROUPS.map(g => <div key={g.title}><div className="section-title">{g.title} <span className="muted" style={{ textTransform: 'none', letterSpacing: 0, fontWeight: 500 }}>· {g.sub}</span></div>
          <div className="grid g2" style={{ gap: 8 }}>{g.keys.map(([k, label, unit]) => { const v = draft[k]; const changed = v !== policy[k]; return <label key={k} className="field" style={changed ? { borderColor: 'var(--accent)' } : undefined}><span>{label}{unit && <em>{unit}</em>}</span>{typeof v === 'boolean' ? <button type="button" className={`switch ${v ? 'on' : ''}`} onClick={() => setDraft({ ...draft, [k]: !v })}><i /></button> : <input type="number" step={k.includes('threshold') && (v as number) < 1 ? 0.01 : k.startsWith('slo') ? 0.1 : 1} value={v as number ?? ''} onChange={e => setDraft({ ...draft, [k]: Number(e.target.value) })} />}</label> })}</div></div>)}</div>
      </Panel>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Panel title="Autonomy mode" sub={autonomy}><div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{[['auto', 'Auto-heal', 'Execute every plan immediately. Fastest MTTR, least oversight.'], ['earned', 'Earned autonomy', 'Actions with a proven track record run on their own; unproven or high-risk ones wait for a human. Trust is updated by every verified outcome.'], ['approval', 'Approval', 'Every plan waits for a human. Sentinel still diagnoses, rehearses and drafts the ticket.']].map(([m, t, d]) => <button key={m} className={`mode ${autonomy === m ? 'on' : ''}`} onClick={() => api.autonomy(m)}><b>{t}</b><span>{d}</span></button>)}</div></Panel>
        <TrustLedger />
      </div>
    </div>
  </div>
}
