import { useEffect, useMemo, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, forceX, forceY, type SimulationNodeDatum } from 'd3-force'
import { api } from '../lib/api'
import { useStore } from '../lib/store'
import type { GraphData } from '../lib/types'
import { Pill } from './ui'

type N = SimulationNodeDatum & { name: string; tier: string; cloud: string; runtime: string; owner: string }
type L = { source: N | string; target: N | string }
const tierX: Record<string, number> = { edge: 0.12, core: 0.45, async: 0.6, ml: 0.62, data: 0.86 }

export default function Topology({ focus, compact }: { focus?: string; compact?: boolean }) {
  const { metrics, incidents } = useStore()
  const [g, setG] = useState<GraphData | null>(null)
  const [nodes, setNodes] = useState<N[]>([])
  const [links, setLinks] = useState<L[]>([])
  const [sel, setSel] = useState<string | undefined>(focus)
  const [blast, setBlast] = useState<{ upstream: { name: string; hops: number }[]; downstream: string[]; source: string } | null>(null)
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => { api.graph().then(setG) }, [])
  useEffect(() => { setSel(focus) }, [focus])
  useEffect(() => { if (sel) api.blast(sel).then(setBlast); else setBlast(null) }, [sel])
  useEffect(() => {
    if (!g || !box.current) return
    const W = box.current.clientWidth, H = box.current.clientHeight
    const ns: N[] = g.nodes.map(n => ({ ...n, x: W * (tierX[n.tier] ?? .5) + Math.random() * 40, y: H / 2 + (Math.random() - .5) * H * .6 }))
    const ls: L[] = g.edges.map(e => ({ source: e.source, target: e.target }))
    const sim = forceSimulation(ns).force('link', forceLink<N, L>(ls).id(d => d.name).distance(90).strength(.5))
      .force('charge', forceManyBody().strength(-420)).force('center', forceCenter(W / 2, H / 2))
      .force('x', forceX<N>(d => W * (tierX[d.tier] ?? .5)).strength(.35)).force('y', forceY(H / 2).strength(.06)).force('col', forceCollide(38))
    sim.on('tick', () => { setNodes([...ns]); setLinks([...ls]) })
    return () => { sim.stop() }
  }, [g])
  const blastSet = useMemo(() => new Set(blast?.upstream.map(u => u.name) || []), [blast])
  const hot = useMemo(() => new Set(incidents.filter(i => !['resolved', 'failed'].includes(i.status)).map(i => i.service)), [incidents])
  const color = (n: string) => { const m = metrics[n]; if (!m) return 'var(--muted)'; return m.status === 'down' ? 'var(--crit)' : m.status === 'degraded' ? 'var(--warn)' : 'var(--ok)' }
  const selM = sel ? metrics[sel] : undefined
  return (
    <div className="topo" ref={box} style={compact ? { height: 380, minHeight: 380 } : undefined}>
      <svg onClick={() => setSel(undefined)}>
        <defs><filter id="glow"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
        {links.map((l, i) => { const s = l.source as N, t = l.target as N; if (typeof s === 'string' || s.x == null) return null
          const cls = hot.has(t.name) && (blastSet.has(s.name) || s.name === sel || hot.has(s.name)) ? 'edge hot' : (blastSet.has(s.name) && (blastSet.has(t.name) || t.name === sel)) ? 'edge blast' : 'edge'
          return <line key={i} className={cls} x1={s.x} y1={s.y} x2={t.x} y2={t.y} /> })}
        {nodes.map(n => { const m = metrics[n.name]; const c = color(n.name); const isSel = sel === n.name; const inBlast = blastSet.has(n.name); const r = n.tier === 'data' ? 15 : n.tier === 'edge' ? 14 : 12
          return <g key={n.name} transform={`translate(${n.x},${n.y})`} style={{ cursor: 'pointer' }} onClick={e => { e.stopPropagation(); setSel(n.name) }}>
            {(m?.status !== 'healthy' || isSel) && <circle r={r + 9} fill={c} opacity=".18" filter="url(#glow)"><animate attributeName="r" values={`${r + 6};${r + 14};${r + 6}`} dur="1.8s" repeatCount="indefinite" /></circle>}
            {inBlast && <circle r={r + 5} fill="none" stroke="var(--warn)" strokeWidth="1.2" strokeDasharray="3 3" opacity=".8" />}
            <circle r={r} fill="#0b0f17" stroke={c} strokeWidth={isSel ? 3 : 2} />
            <circle r={r - 5} fill={c} opacity={m?.status === 'healthy' ? .55 : 1} />
            <text className="node-label" y={r + 13} textAnchor="middle">{n.name}</text>
            <text y={-r - 6} textAnchor="middle" fontSize="8" fill="var(--muted)" fontFamily="var(--mono)">{n.cloud.toUpperCase()}</text>
          </g> })}
      </svg>
      <div className="legend"><Pill tone="ok"><i className="dot" />healthy</Pill><Pill tone="warn"><i className="dot" />degraded</Pill><Pill tone="crit"><i className="dot" />down</Pill><Pill tone="outline">dashed ring = blast radius</Pill><Pill tone="outline">graph: {g?.source ?? '…'}</Pill></div>
      {sel && <div className="panel inspector"><div className="panel-h"><h3 className="mono">{sel}</h3><div className="right"><Pill tone={selM?.status === 'healthy' ? 'ok' : selM?.status === 'down' ? 'crit' : 'warn'}>{selM?.status}</Pill></div></div>
        <div className="panel-b" style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12.5 }}>
          <div className="grid g2" style={{ gap: 8 }}>{[['p95', `${selM?.latency_p95} ms`], ['errors', `${((selM?.error_rate || 0) * 100).toFixed(2)}%`], ['cpu', `${selM?.cpu}%`], ['mem', `${selM?.mem}%`]].map(([k, v]) => <div key={k}><div className="muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: 1 }}>{k}</div><div className="mono" style={{ fontWeight: 600 }}>{v}</div></div>)}</div>
          <div><div className="section-title">Blast radius · {blast?.source}</div><div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{blast?.upstream.length ? blast.upstream.map(u => <Pill key={u.name} tone="warn">{u.name} <span className="muted">{u.hops}h</span></Pill>) : <span className="muted">no upstream dependents</span>}</div></div>
          <div><div className="section-title">Depends on</div><div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>{blast?.downstream.map(d => <Pill key={d} tone="neutral">{d}</Pill>)}</div></div>
        </div></div>}
    </div>
  )
}
