import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Empty, ErrorNote, Field, Loading } from '../components/ui.jsx'
import { CropName, SeasonRibbon } from '../components/farm.jsx'
import { StartCycle } from './Recommend.jsx'
import { dateLabel, num } from '../format.js'

export default function Crops() {
  useTitle('My crops')
  const { options } = useAuth()
  const [params, setParams] = useSearchParams()
  const { data, error, loading, reload } = useApi('/cycles')
  const [pick, setPick] = useState('')
  const [starting, setStarting] = useState(params.get('new') ? { picking: true } : null)
  const active = data?.cycles.filter((c) => c.status === 'active') || []
  const past = data?.cycles.filter((c) => c.status !== 'active') || []
  const crops = options?.crops || []

  const close = () => { setStarting(null); setPick(''); if (params.get('new')) setParams({}) }
  return (
    <>
      <div className="head">
        <div><h1>My crops</h1><p>Each crop you grow, from land preparation to sale, with a checklist for every stage and a field diary.</p></div>
        <button className="btn" onClick={() => setStarting({ picking: true })}><Plus size={18} />Add a crop</button>
      </div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} onRetry={reload} />
      {data && active.length === 0 && (
        <Empty title="No crops being tracked" action={<div className="row"><button className="btn" onClick={() => setStarting({ picking: true })}>Add a crop you have sown</button><Link className="btn secondary" to="/recommend">Help me choose</Link></div>}>
          Already sown? Add it with its sowing date and you get the tasks for the stage it is in now.
        </Empty>
      )}
      {active.map((c) => (
        <Link key={c.id} to={`/crops/${c.id}`} className="cropblock">
          <div className="top">
            <h3><CropName name={c.crop_name} local={c.crop_local} /></h3>
            <span className="small muted">{num(c.area_acres, 2)} acres{c.field_name ? `, ${c.field_name}` : ''}. Sown {dateLabel(c.sowing_date)}</span>
          </div>
          <SeasonRibbon progress={c.progress} />
        </Link>
      ))}
      {past.length > 0 && (
        <section className="section">
          <div className="section-title"><h2>Past seasons</h2></div>
          <div className="list">
            {past.map((c) => (
              <Link key={c.id} to={`/crops/${c.id}`} className="item row between">
                <span><b>{c.crop_name}</b> <span className="muted small">{num(c.area_acres, 2)} acres, sown {dateLabel(c.sowing_date, { day: 'numeric', month: 'short', year: 'numeric' })}</span></span>
                <span className={`chip ${c.status === 'completed' ? 'leaf' : ''}`}>{c.status}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
      {starting?.picking && !pick && (
        <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && close()}>
          <div className="dialog" role="dialog" aria-modal="true" aria-label="Choose a crop">
            <div className="dialog-head"><h2>Which crop?</h2><button className="btn ghost" onClick={close}>Cancel</button></div>
            <Field label="Crop">
              <select className="input" value={pick} onChange={(e) => setPick(e.target.value)} autoFocus>
                <option value="">Choose…</option>
                {crops.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.local})</option>)}
              </select>
            </Field>
          </div>
        </div>
      )}
      {pick && <StartCycle crop={crops.find((c) => c.id === pick)} onClose={close} />}
    </>
  )
}
