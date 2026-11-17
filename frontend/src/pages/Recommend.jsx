import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, qs } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Choices, Dialog, ErrorNote, Field, Loading, Notice, Tabs, useAction } from '../components/ui.jsx'
import { CropName } from '../components/farm.jsx'
import { Bar } from '../components/charts.jsx'
import { num, rupees, todayISO } from '../format.js'

const PART_LABELS = { track: 'Grown here', yield: 'Yield', soil: 'Soil', water: 'Water', profit: 'Profit', budget: 'Budget' }

export default function Recommend() {
  useTitle('What to grow')
  const { farm, options } = useAuth()
  const [params, setParams] = useSearchParams()
  const season = params.get('season') || ''
  const [whatIf, setWhatIf] = useState({ irrigation: '', land_area_acres: '', budget: '' })
  const [applied, setApplied] = useState({})
  const { data, error, loading, reload } = useApi(`/recommend${qs({ season, ...applied })}`)
  const [starting, setStarting] = useState(null)
  const [detail, setDetail] = useState(null)

  const seasonOpts = [{ value: 'kharif', label: 'Kharif' }, { value: 'rabi', label: 'Rabi' }, { value: 'summer', label: 'Summer' }]
  return (
    <>
      <div className="head">
        <div>
          <h1>What to grow</h1>
          <p>Every crop your district grows, ranked for your {num(farm.land_area_acres, 2)} acres: its record here, expected yield, soil and water fit, profit at today's prices and your budget.</p>
        </div>
      </div>
      <div className="row between" style={{ marginBottom: 16 }}>
        <Tabs label="Season" value={data?.season || season} onChange={(v) => setParams({ season: v })} options={seasonOpts} />
        <details>
          <summary className="btn secondary sm" style={{ listStyle: 'none' }}>Try different conditions</summary>
          <div className="panel form" style={{ marginTop: 10, maxWidth: 520 }}>
            <Field group label="Irrigation">
              <Choices value={whatIf.irrigation || farm.irrigation} onChange={(v) => setWhatIf({ ...whatIf, irrigation: v })}
                options={Object.entries(options?.irrigation || {}).map(([value, label]) => ({ value, label: label.split(' (')[0] }))} />
            </Field>
            <div className="grid2">
              <Field label="Acres"><input className="input" type="number" min="0.1" step="0.1" placeholder={farm.land_area_acres} value={whatIf.land_area_acres} onChange={(e) => setWhatIf({ ...whatIf, land_area_acres: e.target.value })} /></Field>
              <Field label="Budget (₹)"><input className="input" type="number" min="0" step="1000" placeholder={farm.budget || 'none'} value={whatIf.budget} onChange={(e) => setWhatIf({ ...whatIf, budget: e.target.value })} /></Field>
            </div>
            <div className="row">
              <button className="btn sm" onClick={() => setApplied(Object.fromEntries(Object.entries(whatIf).filter(([, v]) => v)))}>Update ranking</button>
              <button className="btn ghost sm" onClick={() => { setWhatIf({ irrigation: '', land_area_acres: '', budget: '' }); setApplied({}) }}>Back to my farm</button>
            </div>
          </div>
        </details>
      </div>

      {Object.keys(applied).length > 0 && <div style={{ marginBottom: 12 }}><Notice kind="warn">Showing a what-if ranking. Your saved farm is unchanged.</Notice></div>}
      {loading && !data && <Loading text="Ranking crops for your farm…" />}
      <ErrorNote error={error} onRetry={reload} />
      {data && <>
        {data.borrowed_from && <div style={{ marginBottom: 12 }}><Notice>{data.district} has no crop records of its own (it may be a newer district), so the records of neighbouring {data.borrowed_from} are used.</Notice></div>}
        {data.crops.length === 0 && <Notice kind="warn">No crops have records for this season in your district. Try another season.</Notice>}
        {data.crops.map((c, i) => (
          <article key={c.id} className={`rec ${i === 0 ? 'first' : ''}`}>
            <div className="rank" aria-label={`Score ${c.score} out of 100`}>{c.score}</div>
            <div>
              <h3><CropName name={c.name} local={c.local} /></h3>
              <div className="row small muted" style={{ gap: 8, marginTop: 4 }}>
                <span>{Math.round(c.duration_days / 30 * 10) / 10} months</span>
                {c.sow_months.length > 0 && <span>Sow in {c.sow_months.join(', ')}</span>}
                <span className={`chip ${c.risk === 'low' ? 'leaf' : c.risk === 'medium' ? 'sun' : 'chilli'}`}>{c.risk} risk</span>
                {c.beginner_friendly && farm.experience === 'new' && <span className="chip">good first crop</span>}
              </div>
              <div className="figures">
                <div><b>{num(c.yield_q_acre, 1)} q</b><span>per acre, likely {num(c.yield_low, 1)} to {num(c.yield_high, 1)}</span></div>
                <div><b>{rupees(c.profit_acre)}</b><span>profit per acre</span></div>
                <div><b>{rupees(c.cost_acre)}</b><span>cost per acre</span></div>
              </div>
              {c.reasons.length > 0 && <ul className="reasons">{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
              {c.cautions.length > 0 && <ul className="cautions">{c.cautions.map((r) => <li key={r}>{r}</li>)}</ul>}
              <button className="btn ghost sm" style={{ marginTop: 8, paddingLeft: 0 }} onClick={() => setDetail(c)}>How this was worked out</button>
            </div>
            <div className="actions"><button className={`btn ${i === 0 ? 'sun' : 'secondary'}`} onClick={() => setStarting(c)}>Grow this</button></div>
          </article>
        ))}
        <p className="footer-note">
          Yields: a model trained on {data.data_years[0]}-{data.data_years[1]} district crop statistics (Ministry of Agriculture). Prices: average mandi price of the last 3 months to {data.price_month}. Costs: CACP cost of cultivation where published, otherwise a rough typical figure. Profit leaves out land rent. <Link to="/profile#models">How accurate is this?</Link>
        </p>
      </>}
      {starting && <StartCycle crop={starting} season={data.season} onClose={() => setStarting(null)} />}
      {detail && <Workings crop={detail} weights={data.weights} onClose={() => setDetail(null)} />}
    </>
  )
}

function Workings({ crop, weights, onClose }) {
  return (
    <Dialog title={crop.name} onClose={onClose}>
      <div className="parts" style={{ maxWidth: 'none', gridTemplateColumns: '110px 1fr 40px' }}>
        {Object.entries(crop.parts).map(([k, v]) => (
          <div key={k} style={{ display: 'contents' }}>
            <span>{PART_LABELS[k]} <span className="muted">({weights[k]}%)</span></span><Bar value={v} /><b>{v}</b>
          </div>
        ))}
      </div>
      <dl className="kv" style={{ marginTop: 18 }}>
        <dt>Records in district</dt><dd>{crop.district_years ? `${crop.district_years} years, last ${crop.district_last_year}; ${crop.area_share_pct}% of the season's area` : 'None'}</dd>
        <dt>Expected yield</dt><dd>{num(crop.yield_q_acre, 1)} q/acre of {crop.product} ({crop.yield_vs_national_pct > 0 ? '+' : ''}{crop.yield_vs_national_pct}% vs national)</dd>
        <dt>Price used</dt><dd>{rupees(crop.price)}/q, {crop.price_basis}</dd>
        {crop.msp && <><dt>MSP</dt><dd>{rupees(crop.msp)}/q, {crop.msp_note}</dd></>}
        <dt>Income</dt><dd>{rupees(crop.revenue_acre)} per acre</dd>
        <dt>Cost</dt><dd>{rupees(crop.cost_acre)} per acre ({crop.cost_basis})</dd>
        <dt>Profit</dt><dd>{rupees(crop.profit_acre)} per acre, {rupees(crop.profit_per_month)} per month in the field</dd>
        <dt>Whole farm</dt><dd>cost {rupees(crop.total_cost)}, profit {rupees(crop.total_profit)}</dd>
        {crop.season_rain_mm != null && <><dt>Water</dt><dd>needs {crop.water_need_mm[0]}-{crop.water_need_mm[1]} mm; normal rain in its season here {crop.season_rain_mm} mm</dd></>}
      </dl>
    </Dialog>
  )
}

export function StartCycle({ crop, season, onClose }) {
  const { farm } = useAuth()
  const navigate = useNavigate()
  const [busy, run] = useAction()
  const [f, setF] = useState({ sowing_date: todayISO(), area_acres: farm.land_area_acres, field_name: '', variety: '' })
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault(); setError('')
    try {
      const r = await run(() => api('/cycles', { method: 'POST', body: { ...f, crop: crop.id, season, area_acres: Number(f.area_acres) } }), `Tracking ${crop.name}`)
      navigate(`/crops/${r.cycle.id}`)
    } catch (err) { setError(err.message) }
  }
  return (
    <Dialog title={`Grow ${crop.name}`} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Field label="Sowing date" hint="A date in the future gives you the land-preparation checklist first.">
          <input className="input" type="date" value={f.sowing_date} onChange={(e) => setF({ ...f, sowing_date: e.target.value })} required />
        </Field>
        <div className="grid2">
          <Field label="Area (acres)"><input className="input" type="number" min="0.05" step="0.05" max={farm.land_area_acres} value={f.area_acres} onChange={(e) => setF({ ...f, area_acres: e.target.value })} required /></Field>
          <Field label="Field name (optional)"><input className="input" value={f.field_name} placeholder="e.g. Near the well" onChange={(e) => setF({ ...f, field_name: e.target.value })} /></Field>
        </div>
        <Field label="Variety (optional)"><input className="input" value={f.variety} onChange={(e) => setF({ ...f, variety: e.target.value })} /></Field>
        {error && <p className="form-error">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? 'Starting…' : 'Start tracking'}</button>
      </form>
    </Dialog>
  )
}
