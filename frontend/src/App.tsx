import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { StoreProvider, useStore } from './lib/store'
import { api } from './lib/api'
import { Pill } from './components/ui'
import Copilot from './components/Copilot'
import Overview from './pages/Overview'
import Incidents from './pages/Incidents'
import Posture from './pages/Posture'
import Compliance from './pages/Compliance'
import Chaos from './pages/Chaos'
import Integrations from './pages/Integrations'
import Policy from './pages/Policy'
import Landing from './pages/Landing'
import Topology from './components/Topology'

const NAV = [
  ['/overview', 'Overview', 'M3 12l9-8 9 8v9H3z'], ['/topology', 'Topology', 'M5 7a2 2 0 100-4 2 2 0 000 4zm14 0a2 2 0 100-4 2 2 0 000 4zm-7 14a2 2 0 100-4 2 2 0 000 4zM5 7l7 10M19 7l-7 10'],
  ['/incidents', 'Incidents', 'M12 3l10 18H2zM12 9v5M12 17h.01'], ['/posture', 'Posture & Cost', 'M12 2l8 4v6c0 5-3.5 9-8 10-4.5-1-8-5-8-10V6z'],
  ['/compliance', 'Compliance', 'M6 3h9l5 5v13H6zM9 12h6M9 16h6'], ['/chaos', 'Chaos Lab', 'M13 2L4 14h6l-1 8 9-12h-6z'], ['/policy', 'Policy & Trust', 'M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z'], ['/integrations', 'Integrations', 'M4 6h16M4 12h16M4 18h16'],
]
function Shell() {
  const s = useStore(); const loc = useLocation()
  const open = s.incidents.filter(i => !['resolved', 'failed'].includes(i.status)).length
  const title = NAV.find(n => n[0] === loc.pathname)?.[1] || 'Sentinel'
  const last = s.logs[s.logs.length - 1]
  return <div className="app">
    <aside className="sidebar"><NavLink to="/" className="brand" style={{ color: 'inherit' }}><div className="brand-mark" /><div><h1>Sentinel</h1><small>self-healing ops</small></div></NavLink>
      <nav className="nav">{NAV.map(([to, label, d]) => <NavLink key={to} to={to}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>{label}{to === '/incidents' && open > 0 && <span className="pill crit">{open}</span>}</NavLink>)}</nav>
      <div className="sidebar-foot"><div style={{ display: 'flex', gap: 6, alignItems: 'center' }}><i className={`dot ${s.connected ? 'pulse' : ''}`} style={{ color: s.connected ? 'var(--ok)' : 'var(--crit)' }} />{s.connected ? 'live stream' : 'reconnecting…'}</div><div style={{ marginTop: 4 }}>{Object.values(s.metrics).length} services · {Object.values(s.integrations).filter(i => i.status === 'connected').length} live integrations</div></div></aside>
    <div className="main"><header className="topbar"><h2>{title}</h2><span className="spacer" />
      <Pill tone={s.integrations.claude?.status === 'connected' ? 'accent' : 'neutral'}>brain: {s.integrations.claude?.status === 'connected' ? 'claude' : 'heuristic'}</Pill>
      <Pill tone={s.integrations.neo4j?.status === 'connected' ? 'accent' : 'neutral'}>graph: {s.integrations.neo4j?.status === 'connected' ? 'neo4j' : 'memory'}</Pill>
      <Pill tone={s.integrations.duplocloud?.status === 'connected' ? 'accent' : 'neutral'}>duplocloud: {s.integrations.duplocloud?.status}</Pill>
      <div className="toggle" title="Autonomy policy">{[['auto', 'Auto'], ['earned', 'Earned'], ['approval', 'Approval']].map(([m, l]) => <button key={m} className={s.autonomy === m ? 'on' : ''} onClick={() => api.autonomy(m)}>{l}</button>)}</div></header>
      <main className="content"><Routes><Route path="/overview" element={<Overview />} /><Route path="/topology" element={<div className="page"><Topology /></div>} /><Route path="/incidents" element={<Incidents />} /><Route path="/posture" element={<Posture />} /><Route path="/compliance" element={<Compliance />} /><Route path="/chaos" element={<Chaos />} /><Route path="/integrations" element={<Integrations />} /><Route path="/policy" element={<Policy />} /></Routes></main>
      {last && <div className="ticker"><i className={`dot ${last.level === 'error' ? 'pulse' : ''}`} style={{ color: last.level === 'error' ? 'var(--crit)' : last.level === 'warn' ? 'var(--warn)' : 'var(--ok)' }} /><span className="src">{last.source}</span><span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{last.message}</span><span className="muted" style={{ marginLeft: 'auto' }}>{new Date(last.ts * 1000).toLocaleTimeString([], { hour12: false })}</span></div>}</div>
    <Copilot />
  </div>
}
function Root() { const loc = useLocation(); return loc.pathname === '/' ? <Landing /> : <Shell /> }
export default function App() { return <StoreProvider><BrowserRouter><Root /></BrowserRouter></StoreProvider> }
