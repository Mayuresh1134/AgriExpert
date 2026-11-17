import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Field, useAction } from '../components/ui.jsx'
import { num, rupees, timeAgo } from '../format.js'

export default function Profile() {
  useTitle('Profile')
  const { user, setUser, farm, options, logout } = useAuth()
  const { data: pts } = useApi('/me/points')
  const { data: models } = useApi('/meta/models')
  const [busy, run] = useAction()
  const [f, setF] = useState({ name: user.name, language: user.language, age: user.age || '' })
  const [pw, setPw] = useState({ current_password: '', new_password: '' })

  const save = async (e) => {
    e.preventDefault()
    const r = await run(() => api('/me', { method: 'PUT', body: { ...f, age: f.age === '' ? null : Number(f.age) } }), 'Profile saved')
    setUser(r.user)
  }
  const changePw = async (e) => {
    e.preventDefault()
    await run(() => api('/me', { method: 'PUT', body: pw }), 'Password changed')
    setPw({ current_password: '', new_password: '' })
  }
  const lvl = pts?.summary
  return (
    <>
      <div className="head">
        <div><h1>{user.name}</h1><p>{user.login}</p></div>
        <button className="btn secondary" onClick={logout}><LogOut size={18} />Log out</button>
      </div>

      <div className="grid2">
        <section className="panel">
          <h3>Farm</h3>
          <dl className="kv" style={{ margin: '12px 0' }}>
            <dt>Location</dt><dd>{farm.village ? `${farm.village}, ` : ''}{farm.district}, {farm.state}</dd>
            <dt>Land</dt><dd>{num(farm.land_area_acres, 2)} acres{farm.ownership === 'tenant' ? ', leased' : ''}</dd>
            <dt>Soil</dt><dd>{farm.soil_type ? options?.soil_types[farm.soil_type] : 'Not set'}{farm.ph ? `, pH ${farm.ph}` : ''}</dd>
            <dt>Water</dt><dd>{options?.irrigation[farm.irrigation]}</dd>
            <dt>Budget</dt><dd>{farm.budget ? rupees(farm.budget) : 'Not set'}</dd>
          </dl>
          <Link className="btn secondary sm" to="/farm">Edit farm</Link>
        </section>

        <section className="panel">
          <h3>Farm score</h3>
          {lvl && <>
            <p style={{ marginTop: 8 }}><b style={{ fontSize: 'var(--t-xl)' }}>{lvl.points}</b> points, level {lvl.level_number}: <b>{lvl.level}</b></p>
            <div className="levelbar" style={{ margin: '10px 0' }}><i style={{ width: `${lvl.next_at ? ((lvl.points - lvl.level_start) / (lvl.next_at - lvl.level_start)) * 100 : 100}%` }} /></div>
            <p className="small muted">{lvl.next_level ? `${lvl.next_at - lvl.points} points to ${lvl.next_level}.` : 'Top level reached.'} Earn points by finishing tasks ({pts.rules.task}), keeping the diary ({pts.rules.log}), answering other farmers ({pts.rules.reply}, or {pts.rules.solved} when it solves the problem) and completing a season ({pts.rules.harvest}).</p>
            {pts.entries.length > 0 && (
              <div style={{ marginTop: 12 }}>
                {pts.entries.slice(0, 6).map((e) => (
                  <div key={e.id} className="row between small" style={{ padding: '3px 0' }}><span>{e.note}</span><span className="muted">+{e.points}, {timeAgo(e.created_at)}</span></div>
                ))}
              </div>
            )}
          </>}
        </section>
      </div>

      <div className="grid2" style={{ marginTop: 16 }}>
        <form className="panel form" onSubmit={save}>
          <h3>Your details</h3>
          <Field label="Name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <div className="grid2">
            <Field label="Age" hint="For pension scheme eligibility"><input className="input" type="number" min="14" max="100" value={f.age} onChange={(e) => setF({ ...f, age: e.target.value })} /></Field>
            <Field label="Assistant language">
              <select className="input" value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
                {Object.entries(options?.languages || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
          </div>
          <button className="btn" disabled={busy}>Save</button>
        </form>
        <form className="panel form" onSubmit={changePw}>
          <h3>Change password</h3>
          <Field label="Current password"><input className="input" type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password" hint="At least 6 characters"><input className="input" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <button className="btn secondary" disabled={busy || !pw.current_password || pw.new_password.length < 6}>Change password</button>
        </form>
      </div>

      {models && <ModelReport m={models} />}
    </>
  )
}

const cap = (t) => (t ? t[0].toUpperCase() + t.slice(1) : t)

function ModelReport({ m }) {
  const y = m.yield, p = m.price, d = m.disease
  const field = d?.results?.['B. Lab + field photos (used in the app)']
  const labOnly = d?.results?.['A. PlantVillage only (lab photos)']
  const ym = y?.test.models
  return (
    <section className="section" id="models">
      <div className="section-title"><h2>How accurate is the advice?</h2></div>
      <p className="prose" style={{ marginBottom: 14 }}>Each model was tested on data it never saw while learning. These are those results.</p>
      <div className="stack">
        {y && (
          <div className="panel">
            <h3>Crop yields</h3>
            <p className="small muted" style={{ margin: '4px 0 12px' }}>Trained on {num(y.trained_on.rows)} district records ({y.trained_on.years[0]}-{y.trained_on.years[1]}), {y.trained_on.districts} districts, {y.trained_on.crops} crops. {cap(y.test.method)}.</p>
            <table className="plain">
              <thead><tr><th>Method</th><th className="n">Typical error</th><th className="n">Within 25%</th></tr></thead>
              <tbody>{Object.entries(ym).map(([k, v]) => <tr key={k}><td>{k}</td><td className="n">{v.median_error_pct}%</td><td className="n">{v.within_25_pct}%</td></tr>)}</tbody>
            </table>
            <p className="small muted" style={{ marginTop: 10 }}>The likely range held the real yield {y.test.range_80_coverage_pct}% of the time (aim: 80%). Where a district has a long record, the model is about as good as the district's own recent average; its value is filling in crops and districts with few or no records.</p>
          </div>
        )}
        {p && (
          <div className="panel">
            <h3>Price forecasts</h3>
            <p className="small muted" style={{ margin: '4px 0 12px' }}>{p.data.crops_with_forecast} crops with monthly prices since {p.data.first_month}. {cap(p.test.method)}.</p>
            <table className="plain">
              <thead><tr><th>Months ahead</th><th className="n">"No change" error</th><th className="n">Forecast error</th></tr></thead>
              <tbody>{Object.entries(p.test.median_error_pct_by_months_ahead).map(([h, v]) => <tr key={h}><td>{h}</td><td className="n">{v.no_change}%</td><td className="n">{v.model}%</td></tr>)}</tbody>
            </table>
            <p className="small muted" style={{ marginTop: 10 }}>Crop prices are hard to forecast: one month ahead the forecast is no better than assuming no change. From two months ahead it does better, and when prices moved more than 5% it called the direction right {p.test.direction_right_pct['3']}% of the time three months ahead.</p>
          </div>
        )}
        {field && (
          <div className="panel">
            <h3>Leaf disease checker</h3>
            <p className="small muted" style={{ margin: '4px 0 12px' }}>{d.backbone}; {d.head}. {d.classes} conditions.</p>
            <table className="plain">
              <thead><tr><th>Test photos</th><th className="n">Right first</th><th className="n">In top 3</th><th className="n">Right first, crop given</th></tr></thead>
              <tbody>
                <tr><td>Lab photos (PlantVillage)</td><td className="n">{field.plantvillage.top1}%</td><td className="n">{field.plantvillage.top3}%</td><td className="n">{field.plantvillage.top1_crop_known}%</td></tr>
                <tr><td>Field photos (PlantDoc)</td><td className="n">{field.plantdoc.top1}%</td><td className="n">{field.plantdoc.top3}%</td><td className="n">{field.plantdoc.top1_crop_known}%</td></tr>
                <tr><td>Rice field photos (Paddy Doctor)</td><td className="n">{field.paddy.top1}%</td><td className="n">{field.paddy.top3}%</td><td className="n">{field.paddy.top1_crop_known}%</td></tr>
              </tbody>
            </table>
            {labOnly && <p className="small muted" style={{ marginTop: 10 }}>Trained on lab photos alone, the same approach got only {labOnly.plantdoc.top1}% of field photos right, which is why field photos were added to training.</p>}
          </div>
        )}
      </div>
    </section>
  )
}
