import { useState } from 'react'
import { api } from '../lib/api'
import { Pill } from './ui'
type M = { role: 'user' | 'assistant'; content: string; tools?: string[] }
export default function Copilot() {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<M[]>([{ role: 'assistant', content: 'I have live access to incidents, the Neo4j graph, metrics, posture findings and chaos tools. Ask me anything.' }])
  const [q, setQ] = useState(''); const [busy, setBusy] = useState(false)
  const send = async (text: string) => {
    if (!text.trim() || busy) return
    const next = [...msgs, { role: 'user' as const, content: text }]; setMsgs(next); setQ(''); setBusy(true)
    try { const r = await api.chat(next.filter(m => !m.tools || true).map(m => ({ role: m.role, content: m.content }))); setMsgs([...next, { role: 'assistant', content: r.reply, tools: r.tool_calls?.map((c: any) => c.tool) }]) }
    catch (e) { setMsgs([...next, { role: 'assistant', content: `Error: ${e}` }]) } finally { setBusy(false) }
  }
  return <>
    <button className="copilot-fab" onClick={() => setOpen(o => !o)} title="Sentinel Copilot"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 3l1.8 4.6L18.5 9l-4.7 1.4L12 15l-1.8-4.6L5.5 9l4.7-1.4z" /><path d="M5 17l.8 2 2 .8-2 .8L5 22l-.8-1.4-2-.8 2-.8z" /></svg></button>
    {open && <div className="panel copilot"><div className="panel-h"><h3>Sentinel Copilot</h3><span className="sub">Claude · tool use</span><div className="right"><button className="btn ghost sm" onClick={() => setOpen(false)}>✕</button></div></div>
      <div className="chat">{msgs.map((m, i) => <div key={i} className={`bubble ${m.role === 'user' ? 'user' : 'bot'}`}>{m.tools && m.tools.length > 0 && <div className="tools">{m.tools.map((t, j) => <Pill key={j} tone="violet">⚙ {t}</Pill>)}</div>}{m.content}</div>)}{busy && <div className="bubble bot muted">thinking…</div>}</div>
      <div className="chips">{['What is open right now?', 'Blast radius of postgres-primary?', 'Inject a crash on payment-service', 'How much can we save this month?'].map(c => <button key={c} className="chip" onClick={() => send(c)}>{c}</button>)}</div>
      <form className="chat-in" onSubmit={e => { e.preventDefault(); send(q) }}><input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask Sentinel…" /><button className="btn primary sm" disabled={busy}>Send</button></form></div>}
  </>
}
