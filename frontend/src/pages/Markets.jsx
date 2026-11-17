import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { qs } from '../api.js'
import { ErrorNote, Field, Loading, Notice } from '../components/ui.jsx'
import { PriceChart, SeasonalBars } from '../components/charts.jsx'
import { dateLabel, monthLabel, num, rupees, signed } from '../format.js'

export default function Markets() {
  useTitle('Prices & mandis')
  const { options } = useAuth()
  const [params, setParams] = useSearchParams()
  const { data: cycles } = useApi('/cycles')
  const growing = cycles?.cycles.filter((c) => c.status === 'active').map((c) => c.crop) || []
  const crop = params.get('crop') || growing[0] || 'wheat'
  const [filters, setFilters] = useState({ radius: 250, transport: 3, quantity: '' })
  const [applied, setApplied] = useState(filters)
  const { data, error, loading, reload } = useApi(`/markets/${crop}${qs(applied)}`)
  useEffect(() => { if (!params.get('crop') && growing[0]) setParams({ crop: growing[0] }, { replace: true }) }, [growing[0]]) // eslint-disable-line

  const crops = (options?.crops || []).filter((c) => c.id !== 'sugarcane')
  const o = data?.outlook
  const m = data?.markets
  return (
    <>
      <div className="head">
        <div><h1>Prices & mandis</h1><p>Where prices are heading, when they usually peak, and which mandi near you pays most after transport.</p></div>
        <Field label="Crop">
          <select className="input" value={crop} onChange={(e) => setParams({ crop: e.target.value })} style={{ minWidth: 220 }}>
            {growing.length > 0 && <optgroup label="Growing now">{crops.filter((c) => growing.includes(c.id)).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>}
            <optgroup label="All crops">{crops.filter((c) => !growing.includes(c.id)).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>
          </select>
        </Field>
      </div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} onRetry={reload} />
      {data && !o && <Notice kind="warn">No mandi price series is available for this crop.</Notice>}
      {o && <>
        <div className="stats">
          <div className="stat"><b>{rupees(o.latest)}</b><span>per quintal, India median, {monthLabel(o.latest_month)}</span></div>
          {o.change_12m_pct != null && <div className="stat"><b>{signed(o.change_12m_pct)}</b><span>on a year earlier</span></div>}
          {o.msp && <div className="stat"><b>{rupees(o.msp)}</b><span>MSP, {o.msp_note}</span></div>}
          {o.forecast?.[2] && <div className="stat"><b>{rupees(o.forecast[2].price)}</b><span>forecast for {monthLabel(o.forecast[2].month)}</span></div>}
        </div>
        {o.advice && <div style={{ marginTop: 16 }}><Notice kind={o.advice.action === 'hold' ? 'good' : o.advice.action === 'sell' ? 'warn' : 'info'}><b>{o.advice.action === 'hold' ? 'Consider holding. ' : o.advice.action === 'sell' ? 'Consider selling soon. ' : 'No strong signal. '}</b>{o.advice.text}</Notice></div>}
        <div className="panel" style={{ marginTop: 16 }}>
          <PriceChart history={o.history} forecast={o.forecast} msp={o.msp} />
        </div>
        {o.seasonal_pct && (
          <section className="section">
            <div className="section-title"><h2>When prices usually peak</h2></div>
            <div className="panel">
              <SeasonalBars pct={o.seasonal_pct} best={o.best_month} />
              <p className="small muted" style={{ marginTop: 10 }}>Typical % above or below the yearly average, from {Math.round(o.months_of_history / 12)} years of prices. Usually highest in {o.best_month}, lowest in {o.worst_month}.</p>
            </div>
          </section>
        )}
      </>}

      {m && (
        <section className="section">
          <div className="section-title"><h2>Best mandis near you</h2></div>
          <div className="panel" style={{ marginBottom: 12 }}>
            <form className="row" style={{ alignItems: 'flex-end' }} onSubmit={(e) => { e.preventDefault(); setApplied(filters) }}>
              <Field label="Within (km)"><input className="input" type="number" min="10" max="800" value={filters.radius} onChange={(e) => setFilters({ ...filters, radius: e.target.value })} style={{ width: 110 }} /></Field>
              <Field label="Transport (₹ per quintal per 10 km)"><input className="input" type="number" min="0" step="0.5" value={filters.transport} onChange={(e) => setFilters({ ...filters, transport: e.target.value })} style={{ width: 120 }} /></Field>
              <Field label="Your quantity (q)"><input className="input" type="number" min="0" value={filters.quantity} placeholder="optional" onChange={(e) => setFilters({ ...filters, quantity: e.target.value })} style={{ width: 120 }} /></Field>
              <button className="btn secondary">Update</button>
            </form>
          </div>
          {m.markets.length === 0 ? (
            <Notice kind="warn">No mandi within {m.radius_km} km has reported {m.name.toLowerCase()} in the data we have. Try a larger distance.</Notice>
          ) : (
            <div className="list">
              {m.markets.map((x, i) => (
                <div key={`${x.market}-${x.district}`} className={`mandi ${i === 0 ? 'best' : ''}`}>
                  <div>
                    <b>{x.market}</b> <span className="muted small">{x.district}, {x.state}</span>
                    {i === 0 && <span className="chip leaf" style={{ marginLeft: 8 }}>best after transport</span>}
                    {m.nearest && x.market === m.nearest.market && x.district === m.nearest.district && <span className="chip" style={{ marginLeft: 8 }}>nearest</span>}
                  </div>
                  <div className="net">{rupees(x.net_per_q)}<span className="xs muted"> /q</span></div>
                  <div className="sub">
                    About {x.distance_km} km. Price {rupees(x.price)} minus transport {rupees(x.transport_per_q)}.
                    {x.level_pct != null && ` Usually ${Math.abs(x.level_pct)}% ${x.level_pct >= 0 ? 'above' : 'below'} the national median.`}
                    {' '}Last report {dateLabel(x.last_report.date, { day: 'numeric', month: 'short', year: 'numeric' })}: {rupees(x.last_report.modal)}.
                    {x.gain_vs_nearest_per_q > 0 && ` ${rupees(x.gain_vs_nearest_per_q)}/q more than the nearest mandi.`}
                    {x.net_total != null && ` For your ${num(Number(applied.quantity))} q: ${rupees(x.net_total)}.`}
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="footer-note">{m.note} Mandi positions are district centres, so distances are approximate. Price reports from Agmarknet, {dateLabel(m.snapshot_dates[0], { month: 'short', year: 'numeric' })} to {dateLabel(m.snapshot_dates[m.snapshot_dates.length - 1], { month: 'short', year: 'numeric' })}{m.live ? ', plus today\'s live reports' : ''}.</p>
        </section>
      )}
    </>
  )
}
