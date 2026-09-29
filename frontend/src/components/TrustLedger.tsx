import { useStore } from '../lib/store'
import { Panel, Pill } from './ui'
export default function TrustLedger({ compact }: { compact?: boolean }) {
  const { trust, policy } = useStore(); const th = Number(policy.trust_threshold ?? .8), hi = Number(policy.high_risk_trust_threshold ?? .9)
  const rows = [...trust].sort((a, b) => b.score - a.score)
  return <Panel title="Trust ledger" sub="earned autonomy · updated by every verified outcome"><div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
    {rows.slice(0, compact ? 7 : 99).map(t => { const ok = t.score >= th; const hiOk = t.score >= hi; return <div key={t.kind} style={{ display: 'grid', gridTemplateColumns: '112px 1fr 44px 70px', gap: 10, alignItems: 'center', fontSize: 12 }}><span className="mono" style={{ fontWeight: 600 }}>{t.kind}</span><div className="bar" style={{ position: 'relative' }}><i style={{ width: `${t.score * 100}%`, background: hiOk ? 'var(--ok)' : ok ? 'var(--accent)' : 'var(--warn)' }} /><span style={{ position: 'absolute', left: `${th * 100}%`, top: -2, bottom: -2, width: 1, background: 'rgba(255,255,255,.35)' }} /></div><span className="mono" style={{ textAlign: 'right' }}>{Math.round(t.score * 100)}%</span><Pill tone={hiOk ? 'ok' : ok ? 'accent' : 'warn'}>{hiOk ? 'trusted' : ok ? 'auto' : 'gated'}</Pill></div> })}
    <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>score = (successes + 1) / (attempts + 2) · line marks the auto-execute threshold ({Math.round(th * 100)}%)</div></div></Panel>
}
