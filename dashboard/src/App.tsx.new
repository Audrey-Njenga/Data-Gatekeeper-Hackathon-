import { useCallback, useEffect, useState } from 'react'
import { api, type Effect, type LedgerEntry, type Overview } from './api'

const CATEGORY_HELP: Record<string, string> = {
  financial: 'Banking, payments, loans, spending',
  health: 'Medical, therapy, appointments',
  location: 'Addresses and where you are',
  people: 'Contacts, emails, attendees',
  credentials: 'Passwords, IDs, passports',
  private_notes: 'Free-text notes',
  work: 'Work-related items',
  general: 'Low-risk, non-identifying',
}

type Tab = 'overview' | 'rules' | 'agents' | 'activity' | 'sources'

function EffectBadge({ effect }: { effect: string }) {
  return <span className={`badge badge-${effect}`}>{effect}</span>
}

function fmt(ts: string) {
  return new Date(ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function App() {
  const [data, setData] = useState<Overview | null>(null)
  const [ledger, setLedger] = useState<LedgerEntry[]>([])
  const [tab, setTab] = useState<Tab>('overview')
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [o, l] = await Promise.all([api.overview(), api.ledger()])
      setData(o); setLedger(l); setError(null)
    } catch (e) {
      setError(`Cannot reach the gatekeeper API (${(e as Error).message}). Is it running on :8000?`)
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 3000)
    return () => clearInterval(t)
  }, [refresh])

  const act = (fn: () => Promise<unknown>) => async () => {
    try { await fn(); await refresh() } catch (e) { setError((e as Error).message) }
  }

  const pending = data?.escalations.length ?? 0

  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <h1>Data Gatekeeper</h1>
            <p>Your agents get answers, not your data.</p>
          </div>
        </div>
        {data && <span className="pill">model: {data.interpreter}</span>}
      </header>

      <nav>
        {(['overview', 'rules', 'agents', 'activity', 'sources'] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
            {t === 'overview' && pending > 0 && <span className="count">{pending}</span>}
          </button>
        ))}
      </nav>

      {error && <div className="error">{error}</div>}
      {!data ? <p className="muted">Loading…</p> : (
        <main>
          {tab === 'overview' && <OverviewTab data={data} act={act} />}
          {tab === 'rules' && <RulesTab data={data} act={act} />}
          {tab === 'agents' && <AgentsTab data={data} act={act} />}
          {tab === 'activity' && <ActivityTab ledger={ledger} />}
          {tab === 'sources' && <SourcesTab data={data} />}
        </main>
      )}
    </div>
  )
}

type Act = (fn: () => Promise<unknown>) => () => Promise<void>

function OverviewTab({ data, act }: { data: Overview; act: Act }) {
  const d = data.digest
  return (
    <>
      <section className="stats">
        <Stat label="Requests" value={d.requests} />
        <Stat label="Items shared" value={d.shared} tone="allow" />
        <Stat label="Items withheld" value={d.hidden} tone="ask" />
        <Stat label="Requests blocked" value={d.blocked_requests} tone="deny" />
      </section>

      <section className="card">
        <h2>Needs your decision</h2>
        {data.escalations.length === 0 ? (
          <p className="muted">Nothing waiting. Your rules handled everything automatically.</p>
        ) : data.escalations.map((e) => (
          <div key={e.id} className="escalation">
            <div>
              <strong>{e.agent}</strong> wants <strong>{e.category.replace('_', ' ')}</strong> data
              <div className="muted small">
                {e.item_count} item(s) via <code>{e.operation}</code> · {fmt(e.created_at)}
              </div>
            </div>
            <div className="actions">
              <button className="allow" onClick={act(() => api.resolve(e.id, 'always'))}>Always allow</button>
              <button className="deny" onClick={act(() => api.resolve(e.id, 'never'))}>Never</button>
              <button className="ghost" onClick={act(() => api.resolve(e.id, 'dismiss'))}>Dismiss</button>
            </div>
          </div>
        ))}
        {data.escalations.length > 0 && (
          <p className="muted small">"Always" and "Never" become rules for that agent, so you won't be asked again.</p>
        )}
      </section>

      <section className="card">
        <h2>Withheld by category</h2>
        {Object.keys(d.hidden_by_category).length === 0 ? <p className="muted">Nothing withheld yet.</p> : (
          <div className="bars">
            {Object.entries(d.hidden_by_category).sort((a, b) => b[1] - a[1]).map(([c, n]) => (
              <div key={c} className="bar-row">
                <span>{c.replace('_', ' ')}</span>
                <div className="bar"><div style={{ width: `${(n / Math.max(...Object.values(d.hidden_by_category))) * 100}%` }} /></div>
                <span>{n}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  )
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return <div className={`stat ${tone ?? ''}`}><div className="value">{value}</div><div className="label">{label}</div></div>
}

function RulesTab({ data, act }: { data: Overview; act: Act }) {
  const [effect, setEffect] = useState<Effect>('deny')
  const [category, setCategory] = useState(data.categories[0])
  const [agent, setAgent] = useState('*')
  const userRules = data.rules.filter((r) => r.source === 'user')
  const agents = ['*', ...data.grants.map((g) => g.agent)]

  return (
    <>
      <section className="card">
        <h2>Privacy template</h2>
        <p className="muted">A starting point. Your own rules always apply on top, and a deny always wins.</p>
        <div className="templates">
          {Object.entries(data.templates).map(([name, cats]) => (
            <button key={name} className={`template ${data.template === name ? 'selected' : ''}`}
              onClick={act(() => api.setTemplate(name))}>
              <h3>{name}</h3>
              <ul>
                {data.categories.map((c) => (
                  <li key={c}><span>{c.replace('_', ' ')}</span><EffectBadge effect={cats[c] ?? 'ask'} /></li>
                ))}
              </ul>
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Your rules</h2>
        <form className="rule-form" onSubmit={(e) => { e.preventDefault(); act(() => api.addRule(effect, category, [agent]))() }}>
          <select value={effect} onChange={(e) => setEffect(e.target.value as Effect)}>
            <option value="deny">Never share</option>
            <option value="ask">Ask me about</option>
            <option value="allow">Always share</option>
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {data.categories.map((c) => <option key={c} value={c}>{c.replace('_', ' ')} data</option>)}
          </select>
          <span>with</span>
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            {agents.map((a) => <option key={a} value={a}>{a === '*' ? 'any agent' : a}</option>)}
          </select>
          <button type="submit">Add rule</button>
        </form>
        <p className="muted small">{CATEGORY_HELP[category]}</p>
        {userRules.length === 0 ? <p className="muted">No custom rules yet.</p> : (
          <table>
            <thead><tr><th>Effect</th><th>Category</th><th>Agents</th><th /></tr></thead>
            <tbody>
              {userRules.map((r) => (
                <tr key={r.id}>
                  <td><EffectBadge effect={r.effect} /></td>
                  <td>{r.category.replace('_', ' ')}</td>
                  <td>{r.agents.includes('*') ? 'any agent' : r.agents.join(', ')}</td>
                  <td><button className="ghost" onClick={act(() => api.deleteRule(r.id))}>Remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}

function AgentsTab({ data, act }: { data: Overview; act: Act }) {
  const [name, setName] = useState('')
  const [hours, setHours] = useState(24)
  const now = Date.now()
  return (
    <section className="card">
      <h2>Connected agents</h2>
      <form className="rule-form" onSubmit={(e) => { e.preventDefault(); if (name) act(() => api.connect(name, hours))(); setName('') }}>
        <input placeholder="agent name" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
          <option value={1}>1 hour</option><option value={24}>24 hours</option><option value={168}>7 days</option>
        </select>
        <button type="submit">Connect</button>
      </form>
      {data.grants.length === 0 ? <p className="muted">No agents connected.</p> : (
        <table>
          <thead><tr><th>Agent</th><th>Access</th><th>Status</th><th /></tr></thead>
          <tbody>
            {data.grants.map((g) => {
              const expired = new Date(g.expires_at).getTime() <= now
              const status = g.revoked ? 'revoked' : expired ? 'expired' : 'active'
              return (
                <tr key={g.agent}>
                  <td><strong>{g.agent}</strong></td>
                  <td><code>{g.operations.join(', ')}</code></td>
                  <td><span className={`badge badge-${status === 'active' ? 'allow' : 'deny'}`}>{status}</span>
                    {status === 'active' && <span className="muted small"> until {fmt(g.expires_at)}</span>}</td>
                  <td>
                    {status === 'active'
                      ? <button className="deny" onClick={act(() => api.revoke(g.agent))}>Revoke</button>
                      : <button className="ghost" onClick={act(() => api.connect(g.agent, 24))}>Reconnect</button>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}

function ActivityTab({ ledger }: { ledger: LedgerEntry[] }) {
  return (
    <section className="card">
      <h2>Activity</h2>
      <p className="muted small">The ledger records what crossed the boundary by item ID and category, never the content itself.</p>
      {ledger.length === 0 ? <p className="muted">No activity yet.</p> : ledger.map((e) => (
        <div key={e.id} className="ledger-entry">
          <div className="ledger-head">
            <strong>{e.agent}</strong>
            <code>{e.operation}</code>
            <span className={`badge badge-${e.outcome === 'ok' ? 'allow' : 'deny'}`}>{e.outcome.replace(/_/g, ' ')}</span>
            <span className="muted small">{fmt(e.ts)}</span>
          </div>
          {e.interpreted_from && <div className="quote">“{e.interpreted_from}”</div>}
          {e.outcome === 'ok' && (
            <div className="ledger-body">
              <span className="allow-text">{e.released.length} shared</span>
              {e.hidden.length > 0 && (
                <span>· withheld: {e.hidden.map((h) => (
                  <span key={h.id} className={`chip chip-${h.effect}`} title={h.rules.join(', ')}>
                    {h.categories.filter((c) => c !== 'general').join('+') || 'general'}
                  </span>
                ))}</span>
              )}
            </div>
          )}
        </div>
      ))}
    </section>
  )
}

function SourcesTab({ data }: { data: Overview }) {
  return (
    <section className="card">
      <h2>Data sources</h2>
      <p className="muted small">Agents can only call these operations. Lower exposure means less revealed.</p>
      <div className="sources">
        {Object.entries(data.sources).map(([name, s]) => (
          <div key={name} className="source">
            <h3>{name}</h3>
            <p className="muted small">{s.description}</p>
            <ul>
              {Object.entries(s.operations).map(([op, spec]) => (
                <li key={op}>
                  <code>{name}.{op}</code>
                  <span className={`exposure e${spec.exposure}`}>{['', 'derived', 'fields', 'raw'][spec.exposure]}</span>
                  <div className="muted small">{spec.description}</div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}
