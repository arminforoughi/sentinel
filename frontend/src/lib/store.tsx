import { createContext, useContext, useEffect, useReducer, useRef, type ReactNode } from 'react'
import type { Snapshot, Incident, Finding, Report, LogEntry, Integration, Metric, Trust } from './types'

interface State extends Snapshot { connected: boolean; faults: { id: string; kind: string; service: string; healing?: boolean }[] }
type Msg = { type: string; payload: any; ts?: number }

const empty: State = {
  metrics: {}, incidents: [], findings: [], reports: [], logs: [], integrations: {}, autonomy: 'auto',
  stats: { incidents_total: 0, auto_resolved: 0, actions_executed: 0, savings_identified: 0 }, started_at: Date.now() / 1000,
  history: {}, connected: false, faults: [], policy: {}, trust: [],
}

function upsert<T extends { id: string }>(list: T[], item: T, front = true): T[] {
  const i = list.findIndex(x => x.id === item.id)
  if (i === -1) return front ? [item, ...list] : [...list, item]
  const c = list.slice(); c[i] = item; return c
}

function reducer(s: State, m: Msg): State {
  switch (m.type) {
    case 'connected': return { ...s, connected: true }
    case 'disconnected': return { ...s, connected: false }
    case 'snapshot': { const p = m.payload as Snapshot; return { ...s, ...p, connected: true } }
    case 'metrics': {
      const services = m.payload.services as Record<string, Metric>
      const history = { ...s.history }
      for (const [k, v] of Object.entries(services)) {
        const h = (history[k] || []).slice(-59)
        h.push([Math.round(v.ts), v.latency_p95, v.error_rate, v.cpu, v.mem]); history[k] = h
      }
      return { ...s, metrics: services, history }
    }
    case 'incident.created': { const i = m.payload as Incident; return { ...s, incidents: upsert(s.incidents, i), stats: { ...s.stats, incidents_total: s.stats.incidents_total + 1 } } }
    case 'incident.updated': {
      const i = m.payload as Incident
      const stats = { ...s.stats }
      const prev = s.incidents.find(x => x.id === i.id)
      if (i.status === 'resolved' && prev?.status !== 'resolved') stats.auto_resolved += 1
      return { ...s, incidents: upsert(s.incidents, i), stats }
    }
    case 'finding.created': case 'finding.updated': {
      const f = m.payload as Finding; const findings = upsert(s.findings, f)
      return { ...s, findings, stats: { ...s.stats, savings_identified: findings.filter(x => x.status === 'open').reduce((a, x) => a + x.monthly_savings, 0) } }
    }
    case 'report.created': return { ...s, reports: upsert(s.reports, m.payload as Report) }
    case 'log': return { ...s, logs: [...s.logs.slice(-199), m.payload as LogEntry] }
    case 'integration.updated': { const i = m.payload as Integration; return { ...s, integrations: { ...s.integrations, [i.name]: i } } }
    case 'autonomy': return { ...s, autonomy: m.payload }
    case 'policy.updated': return { ...s, policy: m.payload }
    case 'trust.updated': { const t = m.payload as Trust; const i = s.trust.findIndex(x => x.kind === t.kind); const trust = s.trust.slice(); i === -1 ? trust.push(t) : (trust[i] = t); return { ...s, trust } }
    case 'fault.injected': return { ...s, faults: [...s.faults, m.payload] }
    case 'fault.cleared': return { ...s, faults: s.faults.filter(f => f.id !== m.payload.id) }
    default: return s
  }
}

const Ctx = createContext<State>(empty)
export const useStore = () => useContext(Ctx)

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, empty)
  const ref = useRef<WebSocket | null>(null)
  useEffect(() => {
    let dead = false
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws`)
      ref.current = ws
      ws.onopen = () => dispatch({ type: 'connected', payload: null })
      ws.onmessage = e => dispatch(JSON.parse(e.data))
      ws.onclose = () => { dispatch({ type: 'disconnected', payload: null }); if (!dead) setTimeout(connect, 1500) }
    }
    connect()
    return () => { dead = true; ref.current?.close() }
  }, [])
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>
}
