import { useNavigate } from 'react-router-dom'
import { useStore } from '../lib/store'
import { api } from '../lib/api'
import { Pill } from '../components/ui'

const STEPS = [
  ['Detect', 'Telemetry, security signals and cost drift across every cloud', 'monitor'],
  ['Map', 'Blast radius from the Neo4j dependency graph', 'neo4j'],
  ['Triage', 'Fast severity model on Nebius GPUs via OpenRouter', 'nebius'],
  ['Research', 'Live CVE and hardening advisories from Brave Search', 'brave'],
  ['Diagnose', 'Root cause + ordered plan from Claude, structured output', 'claude'],
  ['Rehearse', 'Every fix simulated on the digital twin before prod', 'twin'],
  ['Execute', 'Governed DuploCloud ticket → Vultr / Nebius executors', 'duplocloud'],
  ['Verify & Prove', 'Recovery checked, SOC 2 / ISO / PCI evidence written to a hash chain', 'audit'],
]
const NOVEL = [
  ['Digital-twin rehearsal', 'Sentinel simulates each candidate fix on the dependency graph and scores the disruption the fix itself would cause. Restarting a datastore nine services depend on loses to a rollback. Least-disruptive step runs first; reckless ones are vetoed.', 'R'],
  ['Earned autonomy', 'A trust ledger tracks every action type\'s verified outcomes. Proven actions auto-execute. Unproven or high-risk ones wait for a human. Trust rises when a fix verifies and falls when it doesn\'t, so autonomy is earned, never granted.', 'T'],
  ['Tamper-evident audit ledger', 'Every compliance report commits to the SHA-256 of the one before it. Auditors verify the chain, not screenshots.', '⛓'],
]
const SPONSORS = ['DuploCloud', 'Neo4j', 'Nebius', 'Vultr', 'Brave Search', 'OpenRouter', 'Claude']

export default function Landing() {
  const nav = useNavigate(); const s = useStore()
  const svcs = Object.values(s.metrics).length
  const start = async () => { await api.inject('crash', 'payment-service'); nav('/overview') }
  return <div className="landing">
    <div className="landing-bg"><svg viewBox="0 0 1200 600" preserveAspectRatio="xMidYMid slice">{Array.from({ length: 28 }).map((_, i) => { const x = 80 + (i * 173) % 1100, y = 60 + (i * 97) % 520; const x2 = 80 + ((i + 5) * 173) % 1100, y2 = 60 + ((i + 5) * 97) % 520; return <g key={i}><line x1={x} y1={y} x2={x2} y2={y2} stroke="rgba(56,226,199,.12)" /><circle cx={x} cy={y} r="3" fill={i % 7 === 0 ? 'var(--crit)' : 'var(--accent)'} opacity=".7"><animate attributeName="r" values="2;5;2" dur={`${2 + (i % 5)}s`} repeatCount="indefinite" /></circle></g> })}</svg></div>
    <header className="landing-nav"><div className="brand"><div className="brand-mark" /><div><h1>Sentinel</h1><small>self-healing ops</small></div></div><div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Pill tone={s.connected ? 'ok' : 'crit'} pulse={s.connected}>{s.connected ? `live · ${svcs} services` : 'connecting'}</Pill><a className="btn" href="https://github.com/arminforoughi/sentinel" target="_blank">GitHub ↗</a><button className="btn primary" onClick={() => nav('/overview')}>Open console →</button></div></header>
    <section className="hero">
      <Pill tone="accent">AI Conference Hack Day 2026 · DuploCloud track</Pill>
      <h1>The AI operations engineer that <em>closes the loop.</em></h1>
      <p>Copilots suggest. Sentinel monitors your cloud, maps the blast radius, diagnoses root cause, rehearses the fix on a digital twin, executes it through DuploCloud, verifies recovery and writes the compliance evidence. Then it audits your security, governance and cost posture and fixes that too.</p>
      <div className="hero-cta"><button className="btn primary lg" onClick={start}>▶ Start guided demo</button><button className="btn lg" onClick={() => nav('/overview')}>Open console</button><span className="muted" style={{ fontSize: 12 }}>The guided demo crashes payment-service in the simulated estate and takes you to the console to watch it heal.</span></div>
      <div className="hero-stats">{[['3s', 'median MTTR in the demo estate'], ['18', 'services across Vultr + Nebius'], ['7', 'sponsor tools doing real work'], ['24', 'compliance controls evidenced']].map(([v, l]) => <div key={l}><b>{v}</b><span>{l}</span></div>)}</div>
    </section>
    <section className="landing-sec"><div className="section-title">The problem</div><div className="grid g3">{[['Alerts without answers', 'Hours of MTTR are diagnosis, not the fix. Someone has to work out what broke, what it took down and what to do.'], ['Waste nobody owns', '25–30% of cloud spend is idle. Cost and security findings pile up because remediation is manual and unaudited.'], ['Evidence by screenshot', 'SOC 2 and ISO audits become a quarterly scramble. Nothing in the incident loop produces proof.']].map(([t, d]) => <div key={t} className="panel" style={{ padding: 18 }}><b style={{ fontSize: 14 }}>{t}</b><p className="dim" style={{ margin: '6px 0 0', fontSize: 13 }}>{d}</p></div>)}</div></section>
    <section className="landing-sec"><div className="section-title">How it works · one incident, eight steps</div><div className="pipeline">{STEPS.map(([t, d, k], i) => <div key={t} className="step"><span className="n">{i + 1}</span><b>{t}</b><span className="dim">{d}</span><Pill tone="outline">{k}</Pill></div>)}</div></section>
    <section className="landing-sec"><div className="section-title">What's new here</div><div className="grid g3">{NOVEL.map(([t, d, ic]) => <div key={t} className="panel novel"><div className="ic">{ic}</div><b>{t}</b><p className="dim">{d}</p></div>)}</div></section>
    <section className="landing-sec"><div className="section-title">Sponsor tools wired together</div><div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{SPONSORS.map(x => <span key={x} className="pill outline" style={{ fontSize: 13, padding: '6px 12px' }}>{x}</span>)}</div><p className="muted" style={{ fontSize: 12.5, marginTop: 10 }}>Each one performs a step in the pipeline. Nothing is plugged in and idle. Without credentials every executor runs in simulation so the full loop always demos.</p></section>
    <footer className="landing-foot"><button className="btn primary lg" onClick={start}>▶ Start guided demo</button></footer>
  </div>
}
