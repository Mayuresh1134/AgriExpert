import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LocateFixed, Search } from 'lucide-react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { Choices, Field, Notice, useToast } from '../components/ui.jsx'
import { useTitle } from '../hooks.js'

const STEPS = ['Location', 'Land & soil', 'Water & money']

export default function FarmSetup() {
  const { farm, setFarm, options } = useAuth()
  const editing = !!farm
  useTitle(editing ? 'Farm profile' : 'Set up your farm')
  const navigate = useNavigate()
  const toast = useToast()
  const [step, setStep] = useState(0)
  const [f, setF] = useState(() => ({
    name: '', state: '', district: '', village: '', land_area_acres: '', soil_type: null, ph: '', irrigation: 'limited',
    water_source: '', budget: '', ownership: 'owned', experience: 'experienced', soil_status: { n: null, p: null, k: null },
    lat: null, lng: null, ...(farm || {}),
  }))
  const [districts, setDistricts] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [place, setPlace] = useState('')
  const [places, setPlaces] = useState([])
  const [locating, setLocating] = useState(false)
  const set = (k) => (v) => setF((x) => ({ ...x, [k]: v?.target ? v.target.value : v }))

  useEffect(() => {
    if (!f.state) { setDistricts([]); return }
    api(`/meta/districts?state=${encodeURIComponent(f.state)}`).then((r) => setDistricts(r.districts)).catch(() => setDistricts([]))
  }, [f.state])

  const useGps = () => {
    if (!navigator.geolocation) { toast('This device cannot share its location', 'error'); return }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const { latitude: lat, longitude: lng } = pos.coords
        const r = await api(`/meta/locate?lat=${lat}&lng=${lng}`)
        setF((x) => ({ ...x, state: r.state, district: r.district, lat, lng, location_source: 'gps' }))
        toast(`Found you in ${r.district}, ${r.state}`)
      } catch (e) { toast(e.message, 'error') } finally { setLocating(false) }
    }, () => { setLocating(false); toast('Location permission was refused. Pick your district instead.', 'error') },
    { enableHighAccuracy: true, timeout: 12000 })
  }

  const searchPlace = async (e) => {
    e.preventDefault()
    if (place.trim().length < 2) return
    const r = await api(`/meta/places?q=${encodeURIComponent(place)}`).catch(() => ({ results: [] }))
    setPlaces(r.results)
    if (!r.results.length) toast('No match. Check the spelling or pick your district below.', 'error')
  }
  const pickPlace = (p) => {
    if (!p.state) { toast('That place is outside the map we have', 'error'); return }
    setF((x) => ({ ...x, state: p.state, district: p.district, lat: p.lat, lng: p.lng, location_source: 'gps', village: x.village || p.name }))
    setPlaces([]); setPlace('')
  }

  const validate = (s) => {
    if (s === 0 && (!f.state || !f.district)) return 'Choose your state and district'
    if (s === 1 && !(Number(f.land_area_acres) > 0)) return 'Enter your land area in acres'
    if (s === 1 && f.ph && (Number(f.ph) < 3 || Number(f.ph) > 10)) return 'Soil pH is usually between 4 and 9'
    return ''
  }
  const next = () => { const e = validate(step); setError(e); if (!e) setStep(step + 1) }

  const save = async () => {
    for (const s of [0, 1]) { const e = validate(s); if (e) { setError(e); setStep(s); return } }
    setBusy(true); setError('')
    try {
      const payload = { ...f, land_area_acres: Number(f.land_area_acres), ph: f.ph === '' ? null : Number(f.ph),
        budget: f.budget === '' || f.budget === null ? null : Number(f.budget) }
      // only an exact position (GPS or a searched place) is sent; otherwise the server uses the district centre
      if (f.location_source !== 'gps' || payload.lat == null || payload.lng == null) { delete payload.lat; delete payload.lng }
      const r = await api('/farm', { method: 'PUT', body: payload })
      setFarm(r.farm)
      toast(editing ? 'Farm saved' : 'Farm added')
      navigate(editing ? '/profile' : '/recommend')
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (!options) return null
  const soilOptions = Object.entries(options.soil_types).map(([value, label]) => ({ value, label, toggle: true }))
  const rating = (k) => (
    <Choices label={`Soil ${k}`} value={f.soil_status?.[k]} onChange={(v) => setF((x) => ({ ...x, soil_status: { ...x.soil_status, [k]: v } }))}
      options={['low', 'medium', 'high'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1), toggle: true }))} />
  )

  return (
    <div style={{ maxWidth: 640 }}>
      <div className="head"><div>
        <h1>{editing ? 'Farm profile' : 'Tell us about your farm'}</h1>
        <p>{editing ? 'Recommendations, alerts and fertiliser amounts all use these details.' : 'Three short steps. This is what turns general advice into advice for your field.'}</p>
      </div></div>
      <div className="steps" aria-label={`Step ${step + 1} of 3: ${STEPS[step]}`}>
        {STEPS.map((s, i) => <i key={s} className={i < step ? 'on' : i === step ? 'now' : ''} />)}
      </div>

      <div className="panel form">
        {step === 0 && <>
          <h3>Where is the farm?</h3>
          <button type="button" className="btn secondary" onClick={useGps} disabled={locating}>
            <LocateFixed size={18} />{locating ? 'Finding you…' : 'Use my current location'}
          </button>
          <form onSubmit={searchPlace}>
            <Field label="Or search your village or town">
              <div className="row" style={{ flexWrap: 'nowrap' }}>
                <input className="input" value={place} onChange={(e) => setPlace(e.target.value)} placeholder="e.g. Pimpalgaon Baswant" />
                <button className="btn secondary iconbtn" aria-label="Search"><Search size={18} /></button>
              </div>
            </Field>
            {places.length > 0 && (
              <div className="place-results list">
                {places.map((p, i) => (
                  <button type="button" key={i} onClick={() => pickPlace(p)}>
                    <b>{p.name}</b> <span className="muted small">{p.admin}{p.district ? ` (district: ${p.district})` : ''}</span>
                  </button>
                ))}
              </div>
            )}
          </form>
          <div className="grid2">
            <Field label="State">
              <select className="input" value={f.state} onChange={(e) => setF((x) => ({ ...x, state: e.target.value, district: '', lat: null, lng: null, location_source: 'district' }))}>
                <option value="">Choose…</option>
                {options.states.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
            <Field label="District">
              <select className="input" value={f.district} onChange={(e) => setF((x) => ({ ...x, district: e.target.value, lat: null, lng: null, location_source: 'district' }))} disabled={!f.state}>
                <option value="">Choose…</option>
                {districts.map((d) => <option key={d}>{d}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Village (optional)"><input className="input" value={f.village || ''} onChange={set('village')} /></Field>
          {f.lat && f.location_source === 'gps' && <Notice kind="good">Exact location saved: weather will be for your field, not the district centre.</Notice>}
        </>}

        {step === 1 && <>
          <h3>Land and soil</h3>
          <Field label="Land you farm (acres)" hint="1 hectare = 2.47 acres. 1 acre is about 2.5 bigha in many states, but bigha varies.">
            <input className="input" type="number" inputMode="decimal" min="0.1" step="0.1" value={f.land_area_acres} onChange={set('land_area_acres')} />
          </Field>
          <Field group label="Do you own it?">
            <Choices value={f.ownership} onChange={set('ownership')} options={[{ value: 'owned', label: 'I own it' }, { value: 'tenant', label: 'Leased / sharecrop' }, { value: 'both', label: 'Some of each' }]} />
          </Field>
          <Field group label="Soil type" hint="Not sure? Leave it blank; the district's records still guide the advice.">
            <Choices value={f.soil_type} onChange={set('soil_type')} options={soilOptions} />
          </Field>
          <Field label="Soil pH (optional)" hint="From your Soil Health Card">
            <input className="input" type="number" inputMode="decimal" step="0.1" value={f.ph ?? ''} onChange={set('ph')} style={{ maxWidth: 160 }} />
          </Field>
          <div className="field"><span className="label">Soil test results (optional)</span>
            <span className="hint">From the Soil Health Card. Fertiliser doses go up 25% for a nutrient rated low and down 25% for one rated high.</span>
            <div className="kv" style={{ alignItems: 'center', marginTop: 6 }}>
              <dt>Nitrogen (N)</dt><dd>{rating('n')}</dd>
              <dt>Phosphorus (P)</dt><dd>{rating('p')}</dd>
              <dt>Potassium (K)</dt><dd>{rating('k')}</dd>
            </div>
          </div>
        </>}

        {step === 2 && <>
          <h3>Water and money</h3>
          <Field group label="Irrigation">
            <Choices cards value={f.irrigation} onChange={set('irrigation')} options={[
              { value: 'none', label: 'Rainfed', sub: 'No irrigation' },
              { value: 'limited', label: 'Limited', sub: '2-3 irrigations a season' },
              { value: 'assured', label: 'Assured', sub: 'Canal or borewell' },
            ]} />
          </Field>
          <Field label="Budget for this season (₹, optional)" hint="Seed, fertiliser, sprays, labour and machines. Used to warn when a crop costs more than you can spend.">
            <input className="input" type="number" inputMode="numeric" min="0" step="1000" value={f.budget ?? ''} onChange={set('budget')} />
          </Field>
          <Field group label="Farming experience">
            <Choices value={f.experience} onChange={set('experience')} options={[{ value: 'new', label: 'New to farming' }, { value: 'experienced', label: 'Experienced' }]} />
          </Field>
        </>}

        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="row between">
          {step > 0 ? <button type="button" className="btn ghost" onClick={() => setStep(step - 1)}>Back</button> : <span />}
          <div className="row">
            {editing && step < 2 && <button type="button" className="btn secondary" onClick={save} disabled={busy}>Save</button>}
            {step < 2
              ? <button type="button" className="btn" onClick={next}>Next</button>
              : <button type="button" className="btn" onClick={save} disabled={busy}>{busy ? 'Saving…' : editing ? 'Save farm' : 'Save and see what to grow'}</button>}
          </div>
        </div>
      </div>
    </div>
  )
}
