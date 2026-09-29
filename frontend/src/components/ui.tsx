import type { ReactNode } from 'react'
export const sevClass = (s: string) => s === 'critical' ? 'crit' : s === 'high' ? 'crit' : s === 'medium' ? 'warn' : s === 'low' ? 'info' : 'neutral'
export const statusClass = (s: string) => ({ resolved: 'ok', healthy: 'ok', connected: 'ok', fixed: 'ok', ready: 'accent', failed: 'crit', down: 'crit', error: 'crit', degraded: 'warn', awaiting_approval: 'warn', fallback: 'neutral', open: 'warn', accepted: 'neutral' } as Record<string, string>)[s] || 'violet'
export const fmtT = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour12: false })
export const ago = (t: number) => { const s = Math.max(0, Date.now() / 1000 - t); return s < 60 ? `${Math.round(s)}s ago` : s < 3600 ? `${Math.round(s / 60)}m ago` : `${Math.round(s / 3600)}h ago` }
export const Pill = ({ tone, children, pulse }: { tone: string; children: ReactNode; pulse?: boolean }) => <span className={`pill ${tone}`}>{pulse && <i className="dot pulse" />}{children}</span>
export const Panel = ({ title, sub, right, children, className = '' }: { title?: string; sub?: string; right?: ReactNode; children: ReactNode; className?: string }) => (
  <div className={`panel ${className}`}>{title && <div className="panel-h"><h3>{title}</h3>{sub && <span className="sub">{sub}</span>}{right && <div className="right">{right}</div>}</div>}{children}</div>
)
export function Spark({ data, color = 'var(--accent)', w = 110, h = 28 }: { data: number[]; color?: string; w?: number; h?: number }) {
  if (data.length < 2) return <svg width={w} height={h} />
  const max = Math.max(...data) || 1, min = Math.min(...data)
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - 2 - ((v - min) / (max - min || 1)) * (h - 4)}`).join(' ')
  return <svg width={w} height={h}><polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" /></svg>
}
export function Ring({ value, size = 96, color = 'var(--accent)', label }: { value: number; size?: number; color?: string; label?: string }) {
  const r = size / 2 - 7, c = 2 * Math.PI * r
  return <svg width={size} height={size}><circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(148,163,184,.12)" strokeWidth="7" fill="none" />
    <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="7" fill="none" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset .8s ease' }} />
    <text x="50%" y="50%" dy="6" textAnchor="middle" fill="var(--text)" fontSize={size / 4.2} fontWeight="700">{Math.round(value)}</text>
    {label && <text x="50%" y="50%" dy={size / 4.2 + 8} textAnchor="middle" fill="var(--muted)" fontSize="9" letterSpacing="1">{label}</text>}</svg>
}
export const Stat = ({ label, value, unit, delta, color = 'var(--accent)' }: { label: string; value: ReactNode; unit?: string; delta?: ReactNode; color?: string }) => (
  <div className="panel stat"><span className="glow" style={{ background: color }} /><span className="label">{label}</span><span className="value">{value}{unit && <small>{unit}</small>}</span>{delta && <span className="delta">{delta}</span>}</div>
)
