export type Effect = 'allow' | 'ask' | 'deny'

export interface Rule { id: string; effect: Effect; category: string; agents: string[]; source: string }
export interface Grant { agent: string; operations: string[]; expires_at: string; revoked: boolean }
export interface Escalation { id: string; agent: string; operation: string; category: string; item_count: number; created_at: string }
export interface OpSpec { description: string; params: Record<string, string>; exposure: number }
export interface Source { description: string; operations: Record<string, OpSpec> }
export interface Digest {
  requests: number; agents: string[]; shared: number; hidden: number; blocked_requests: number
  hidden_by_category: Record<string, number>; pending_escalations: number
}
export interface Overview {
  template: string; templates: Record<string, Record<string, Effect>>; categories: string[]
  rules: Rule[]; grants: Grant[]; escalations: Escalation[]; digest: Digest
  sources: Record<string, Source>; interpreter: string
}
export interface LedgerEntry {
  id: number; ts: string; agent: string; operation: string; params: Record<string, unknown>
  outcome: string; released: string[]; escalations: string[]; interpreted_from: string | null
  hidden: { id: string; categories: string[]; effect: Effect; rules: string[] }[]
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText)
  return res.json()
}

const post = (path: string, body: unknown = {}) => call(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  overview: () => call<Overview>('/api/overview'),
  ledger: () => call<LedgerEntry[]>('/api/ledger'),
  setTemplate: (name: string) => post('/api/template', { name }),
  addRule: (effect: Effect, category: string, agents: string[]) => post('/api/rules', { effect, category, agents }),
  deleteRule: (id: string) => call(`/api/rules/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  connect: (agent: string, hours: number) => post('/api/agents', { agent, hours }),
  revoke: (agent: string) => post(`/api/agents/${encodeURIComponent(agent)}/revoke`),
  resolve: (id: string, choice: 'always' | 'never' | 'dismiss') => post(`/api/escalations/${id}`, { choice }),
}
