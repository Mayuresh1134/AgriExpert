import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Dialog, ErrorNote, Field, Loading, Notice, Tabs, useAction, useToast } from '../components/ui.jsx'
import { Alerts, CropName, SeasonRibbon, WeatherStrip } from '../components/farm.jsx'
import { dateLabel, inDays, num, rupees, todayISO } from '../format.js'

export default function CycleDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { options, setUser } = useAuth()
  const { data, error, loading, reload, setData } = useApi(`/cycles/${id}`)
  const [tab, setTab] = useState('tasks')
  const [logging, setLogging] = useState(null)
  const [busy, run] = useAction()
  const c = data?.cycle
  useTitle(c?.crop_name)
  if (loading && !data) return <Loading />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  const p = c.progress
  const stages = options?.stages || []

  const toggle = async (t) => {
    setData((d) => ({ cycle: { ...d.cycle, tasks: d.cycle.tasks.map((x) => (x.id === t.id ? { ...x, done: !t.done } : x)) } }))
    try {
      const r = await api(`/cycles/${id}/tasks/${t.id}`, { method: 'POST', body: { done: !t.done } })
      setUser(r.user)
      if (r.points) toast(`Done. +${r.points} points`)
    } catch (e) { toast(e.message, 'error'); reload() }
  }
  const setStage = (stage) => run(() => api(`/cycles/${id}`, { method: 'PATCH', body: { stage } }), 'Stage updated').then((r) => setData(r))
  const finish = () => run(() => api(`/cycles/${id}`, { method: 'PATCH', body: { status: 'completed' } }), 'Season completed. +50 points').then((r) => setData(r))
  const remove = async () => {
    if (!window.confirm(`Delete this ${c.crop_name} record and its diary? This cannot be undone.`)) return
    await run(() => api(`/cycles/${id}`, { method: 'DELETE' }), 'Crop deleted')
    navigate('/crops')
  }
  const delLog = async (logId) => {
    await run(() => api(`/cycles/${id}/logs/${logId}`, { method: 'DELETE' }), 'Entry deleted')
    reload()
  }

  const byStage = stages.map((s) => ({ ...s, tasks: c.tasks.filter((t) => t.stage === s.id) })).filter((s) => s.tasks.length)
  const nextIdx = Math.min(stages.length - 1, p.stage_index + 1)
  const s = c.summary
  return (
    <>
      <Link to="/crops" className="btn ghost sm" style={{ paddingLeft: 0, marginBottom: 8 }}><ArrowLeft size={16} />My crops</Link>
      <div className="stagehead">
        <div>
          <h1><CropName name={c.crop_name} local={c.crop_local} /></h1>
          <p className="muted">{num(c.area_acres, 2)} acres{c.field_name ? `, ${c.field_name}` : ''}{c.variety ? `, variety ${c.variety}` : ''}. Sown {dateLabel(c.sowing_date, { day: 'numeric', month: 'long', year: 'numeric' })}.</p>
        </div>
        {c.status !== 'active' && <span className="chip leaf">{c.status}</span>}
      </div>

      <div className="panel" style={{ marginTop: 18 }}>
        <div className="stats" style={{ marginBottom: 6 }}>
          <div className="stat"><b>{p.stage_label}</b><span>stage now</span></div>
          <div className="stat"><b>{p.day < 0 ? `${-p.day} days` : `Day ${p.day}`}</b><span>{p.day < 0 ? 'until sowing' : 'since sowing'}</span></div>
          <div className="stat"><b>{dateLabel(p.expected_harvest)}</b><span>expected harvest ({p.days_to_harvest > 0 ? inDays(p.days_to_harvest) : 'due'})</span></div>
        </div>
        <SeasonRibbon progress={p} big />
        {c.status === 'active' && (
          <div className="row small" style={{ marginTop: 14 }}>
            <span className="muted">Crop ahead of the calendar?</span>
            {p.stage_index < stages.length - 1 && <button className="btn ghost sm" disabled={busy} onClick={() => setStage(stages[nextIdx].id)}>Move to {stages[nextIdx].label.toLowerCase()}</button>}
            {c.stage_override && <button className="btn ghost sm" disabled={busy} onClick={() => setStage(null)}>Follow the calendar again</button>}
            {p.stage === 'harvesting' && <button className="btn sun sm" disabled={busy} onClick={finish}>Mark season complete</button>}
          </div>
        )}
      </div>

      {(c.alerts?.length > 0 || c.water) && (
        <section className="section">
          <div className="section-title"><h2>This week</h2></div>
          <Alerts alerts={c.alerts} />
          {c.water && (
            <div style={{ marginTop: 8 }}>
              <Notice kind={c.water.irrigation_mm > 0 ? 'warn' : 'good'}>
                Crop water use this week about <b>{c.water.crop_use_mm} mm</b>; forecast rain {c.water.rain_mm} mm.{' '}
                {c.water.irrigation_mm > 0
                  ? <>Give about <b>{c.water.irrigation_mm} mm</b> by irrigation, roughly {num(c.water.litres_per_acre)} litres per acre.</>
                  : 'Rain should cover it; no irrigation needed.'}
              </Notice>
            </div>
          )}
          <div style={{ marginTop: 12 }}><WeatherStrip forecast={c.weather} /></div>
        </section>
      )}

      <div className="section">
        <Tabs label="Crop sections" value={tab} onChange={setTab} options={[
          { value: 'tasks', label: 'Checklist' }, { value: 'diary', label: `Diary (${c.logs.length})` },
          { value: 'fertiliser', label: 'Fertiliser' }, { value: 'money', label: 'Money' }]} />
      </div>

      {tab === 'tasks' && (
        <div style={{ marginTop: 14 }}>
          {byStage.map((st) => {
            const done = st.tasks.filter((t) => t.done).length
            return (
              <details key={st.id} className="stage-group" open={st.id === p.stage}>
                <summary><span>{st.label}{st.id === p.stage && <span className="chip sun" style={{ marginLeft: 8 }}>now</span>}</span><span className="muted small">{done} of {st.tasks.length}</span></summary>
                {st.tasks.map((t) => {
                  const due = t.due_day != null ? t.due_day - p.day : null
                  return (
                    <label key={t.id} className={`check ${t.done ? 'done' : ''}`}>
                      <input type="checkbox" checked={t.done} onChange={() => toggle(t)} />
                      <div>
                        <b>{t.title}</b>
                        {due != null && !t.done && <span className={`due ${due < 0 && st.id === p.stage ? 'over' : ''}`}>{due === 0 ? 'today' : due > 0 ? inDays(due) : `day ${t.due_day}`}</span>}
                        <p>{t.detail}</p>
                      </div>
                    </label>
                  )
                })}
              </details>
            )
          })}
        </div>
      )}

      {tab === 'diary' && (
        <div style={{ marginTop: 14 }}>
          <div className="row" style={{ marginBottom: 12 }}>
            {['irrigation', 'fertilizer', 'spray', 'weeding', 'observation', 'expense', 'harvest', 'sale'].map((k) => (
              <button key={k} className="btn secondary sm" onClick={() => setLogging(k)}>+ {options?.log_kinds[k]}</button>
            ))}
          </div>
          {c.logs.length === 0 ? <p className="muted">Nothing written yet. Each irrigation, spray or expense you add here builds your season's cost and profit.</p> : (
            <div className="list">
              {c.logs.map((l) => (
                <div key={l.id} className="diary-item">
                  <span className="date">{dateLabel(l.date)}</span>
                  <div>
                    <b>{options?.log_kinds[l.kind]}</b>
                    {l.product && <>, {l.product}{l.amount ? ` (${l.amount})` : ''}</>}
                    {l.quantity_q != null && <>, {num(l.quantity_q, 2)} q</>}
                    {l.price != null && <> at {rupees(l.price)}/q{l.buyer ? ` to ${l.buyer}` : ''}</>}
                    {l.cost ? <>, cost {rupees(l.cost)}</> : null}
                    {l.note && <div className="small muted">{l.note}</div>}
                  </div>
                  <button className="btn ghost iconbtn" aria-label="Delete entry" onClick={() => delLog(l.id)}><Trash2 size={16} /></button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'fertiliser' && <FertiliserPlan plan={c.fertilizer} />}

      {tab === 'money' && (
        <div className="panel" style={{ marginTop: 14 }}>
          <div className="stats">
            <div className="stat"><b>{rupees(s.cost)}</b><span>spent so far</span></div>
            <div className="stat"><b>{rupees(s.revenue)}</b><span>from {num(s.sold_q, 2)} q sold</span></div>
            <div className="stat"><b style={{ color: s.profit >= 0 ? 'var(--leaf)' : 'var(--chilli)' }}>{rupees(s.profit)}</b><span>profit</span></div>
            {s.yield_q_acre && <div className="stat"><b>{num(s.yield_q_acre, 1)} q</b><span>harvested per acre</span></div>}
          </div>
          <p className="small muted" style={{ marginTop: 12 }}>Worked out from the costs, harvest and sales in the diary. Add every expense, including labour and machine hire, for a true figure.</p>
        </div>
      )}

      <div className="row" style={{ marginTop: 32 }}>
        <button className="btn danger sm" onClick={remove} disabled={busy}><Trash2 size={16} />Delete this crop</button>
      </div>
      {logging && <LogDialog kind={logging} label={options?.log_kinds[logging]} cycleId={id} onClose={() => setLogging(null)} onSaved={() => { setLogging(null); reload() }} />}
    </>
  )
}

function FertiliserPlan({ plan }) {
  const p = plan.products
  return (
    <div className="panel" style={{ marginTop: 14 }}>
      <p className="prose">For {num(plan.area_acres, 2)} acres you need {plan.nutrients_kg.n} kg nitrogen, {plan.nutrients_kg.p2o5} kg phosphate and {plan.nutrients_kg.k2o} kg potash
        {Object.keys(plan.adjusted_for).length > 0 && <> (adjusted for your soil test: {Object.entries(plan.adjusted_for).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(', ')})</>}.
        In common fertilisers:</p>
      <div className="stats" style={{ margin: '14px 0' }}>
        <div className="stat"><b>{p.urea_bags_45kg} bags</b><span>urea, 45 kg ({p.urea_kg} kg)</span></div>
        <div className="stat"><b>{p.dap_bags_50kg} bags</b><span>DAP, 50 kg ({p.dap_kg} kg)</span></div>
        <div className="stat"><b>{p.mop_bags_50kg} bags</b><span>MOP, 50 kg ({p.mop_kg} kg)</span></div>
      </div>
      <table className="plain">
        <thead><tr><th>When</th><th className="n">Urea</th><th className="n">DAP</th><th className="n">MOP</th></tr></thead>
        <tbody>
          {plan.schedule.map((r) => (
            <tr key={r.when}><td>{r.when}</td><td className="n">{r.urea_kg ? `${r.urea_kg} kg` : '—'}</td><td className="n">{r.dap_kg ? `${r.dap_kg} kg` : '—'}</td><td className="n">{r.mop_kg ? `${r.mop_kg} kg` : '—'}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="small muted" style={{ marginTop: 12 }}>{plan.note} <Link to="/farm">Add soil test results</Link></p>
    </div>
  )
}

function LogDialog({ kind, label, cycleId, onClose, onSaved }) {
  const [busy, run] = useAction()
  const [f, setF] = useState({ date: todayISO(), note: '', cost: '', quantity_q: '', price: '', product: '', amount: '', buyer: '' })
  const [error, setError] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const submit = async (e) => {
    e.preventDefault(); setError('')
    const body = Object.fromEntries(Object.entries({ ...f, kind }).filter(([, v]) => v !== ''))
    try { await run(() => api(`/cycles/${cycleId}/logs`, { method: 'POST', body }), 'Added to the diary'); onSaved() } catch (err) { setError(err.message) }
  }
  return (
    <Dialog title={`Add ${label?.toLowerCase()}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label="Date"><input className="input" type="date" value={f.date} max={todayISO()} onChange={set('date')} /></Field>
        {(kind === 'fertilizer' || kind === 'spray') && (
          <div className="grid2">
            <Field label="Product"><input className="input" value={f.product} onChange={set('product')} placeholder={kind === 'spray' ? 'e.g. Mancozeb 75 WP' : 'e.g. Urea'} /></Field>
            <Field label="Amount"><input className="input" value={f.amount} onChange={set('amount')} placeholder={kind === 'spray' ? 'e.g. 2.5 g/L, 200 L' : 'e.g. 2 bags'} /></Field>
          </div>
        )}
        {(kind === 'harvest' || kind === 'sale') && (
          <Field label="Quantity (quintals)" hint="1 quintal = 100 kg"><input className="input" type="number" min="0.01" step="0.01" value={f.quantity_q} onChange={set('quantity_q')} required /></Field>
        )}
        {kind === 'sale' && (
          <div className="grid2">
            <Field label="Price per quintal (₹)"><input className="input" type="number" min="1" value={f.price} onChange={set('price')} required /></Field>
            <Field label="Sold to (optional)"><input className="input" value={f.buyer} onChange={set('buyer')} placeholder="e.g. Lasalgaon APMC" /></Field>
          </div>
        )}
        {kind !== 'sale' && kind !== 'harvest' && (
          <Field label="Cost (₹, optional)" hint="Include labour and machine hire"><input className="input" type="number" min="0" value={f.cost} onChange={set('cost')} /></Field>
        )}
        <Field label="Note (optional)"><textarea className="input" value={f.note} onChange={set('note')} /></Field>
        {error && <p className="form-error">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Add to diary'}</button>
      </form>
    </Dialog>
  )
}
