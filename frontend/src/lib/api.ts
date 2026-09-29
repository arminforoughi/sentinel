const j = (r: Response) => { if (!r.ok) throw new Error(`${r.status}`); return r.json() }
const post = (url: string, body?: unknown) => fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined }).then(j)
export const api = {
  state: () => fetch('/api/state').then(j),
  graph: () => fetch('/api/graph').then(j),
  blast: (s: string) => fetch(`/api/graph/blast/${s}`).then(j),
  chaosCatalog: () => fetch('/api/chaos/catalog').then(j),
  inject: (kind: string, service?: string) => post('/api/chaos/inject', { kind, service }),
  approve: (id: string) => post(`/api/incidents/${id}/approve`),
  fix: (id: string) => post(`/api/findings/${id}/fix`),
  iac: (id: string) => post(`/api/findings/${id}/iac`),
  accept: (id: string) => post(`/api/findings/${id}/accept`),
  runAudit: () => post('/api/audit/run'),
  policy: () => fetch('/api/policy').then(j),
  setPolicy: (p: Record<string, unknown>) => post('/api/policy', p),
  resetPolicy: () => post('/api/policy/reset'),
  chain: () => fetch('/api/audit/chain').then(j),
  autonomy: (mode: string) => post('/api/autonomy', { mode }),
  chat: (messages: { role: string; content: string }[]) => post('/api/chat', { messages }),
}
