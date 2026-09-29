import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import { Panel, Pill, sevClass } from '../components/ui'
type C = { kind: string; category: string; severity: string; title: string; description: string; targets: string[] }
export default function Chaos() {
  const [cat, setCat] = useState<C[]>([]); const [tgt, setTgt] = useState<Record<string, string>>({}); const [toast, setToast] = useState(''); const { faults, autonomy } = useStore()
  useEffect(() => { api.chaosCatalog().then(setCat) }, [])
  const fire = async (c: C) => { const r = await api.inject(c.kind, tgt[c.kind] || undefined); setToast(`Injected ${r.kind} on ${r.service} — watch Overview`); setTimeout(() => setToast(''), 3500) }
  return <div className="page">{toast && <div className="toast">⚡ {toast}</div>}
    <Panel title="Chaos Lab" sub="inject real faults into the estate and watch Sentinel detect, diagnose and heal them" right={<><Pill tone={autonomy === 'auto' ? 'accent' : 'warn'}>autonomy: {autonomy}</Pill>{faults.length > 0 && <Pill tone="crit" pulse>{faults.length} active fault{faults.length > 1 ? 's' : ''}</Pill>}</>}>
      <div className="panel-b grid g4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))' }}>{cat.map(c => <div key={c.kind} className="chaos-card"><div style={{ display: 'flex', gap: 6, alignItems: 'center' }}><span className="k">{c.kind}</span><span style={{ marginLeft: 'auto' }} /><Pill tone={c.category === 'security' ? 'crit' : c.category === 'availability' ? 'warn' : 'info'}>{c.category}</Pill><Pill tone={sevClass(c.severity)}>{c.severity}</Pill></div><div className="dim" style={{ fontSize: 12.5 }}>{c.description}</div><div style={{ display: 'flex', gap: 8, marginTop: 'auto' }}><select value={tgt[c.kind] || ''} onChange={e => setTgt({ ...tgt, [c.kind]: e.target.value })}><option value="">random target</option>{c.targets.map(t => <option key={t}>{t}</option>)}</select><button className="btn primary sm" onClick={() => fire(c)}>Inject</button></div></div>)}</div></Panel></div>
}
