import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Camera, Phone, RotateCcw } from 'lucide-react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Field, Notice, Tabs, useToast } from '../components/ui.jsx'
import { timeAgo } from '../format.js'

/** Shrink big phone photos before upload: faster on slow rural connections. */
async function shrink(file, max = 1024) {
  try {
    const bmp = await createImageBitmap(file)
    const scale = Math.min(1, max / Math.max(bmp.width, bmp.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bmp.width * scale); canvas.height = Math.round(bmp.height * scale)
    canvas.getContext('2d').drawImage(bmp, 0, 0, canvas.width, canvas.height)
    return await new Promise((res) => canvas.toBlob((b) => res(b || file), 'image/jpeg', 0.88))
  } catch { return file }
}

const SEVERITY = { high: ['chilli', 'Serious: act within a day or two'], medium: ['sun', 'Moderate'], low: ['leaf', 'Mild'], none: ['leaf', 'Healthy'] }

export default function Scan() {
  useTitle('Check a leaf')
  const { options } = useAuth()
  const toast = useToast()
  const { data: cycles } = useApi('/cycles')
  const { data: history, reload: reloadHistory } = useApi('/scans')
  const [crop, setCrop] = useState('')
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  const [tab, setTab] = useState('organic')
  const input = useRef(null)

  const scanCrops = options?.scan_crops || []
  // pre-select the crop the farmer is growing, if the model knows it
  useEffect(() => {
    if (crop || !cycles) return
    const map = { chilli: 'pepper' }
    const growing = cycles.cycles.filter((c) => c.status === 'active').map((c) => map[c.crop] || c.crop)
    const hit = growing.find((g) => scanCrops.some((s) => s.id === g))
    if (hit) setCrop(hit)
  }, [cycles, scanCrops, crop])

  const choose = (f) => {
    if (!f) return
    if (!f.type.startsWith('image/')) { toast('Choose a photo (JPG or PNG)', 'error'); return }
    setFile(f); setResult(null)
    setPreview(URL.createObjectURL(f))
  }
  const submit = async () => {
    if (!file) return
    setBusy(true)
    try {
      const form = new FormData()
      form.append('image', await shrink(file), 'leaf.jpg')
      if (crop) form.append('crop', crop)
      const r = await api('/scan', { method: 'POST', form })
      setResult(r); setTab(r.result.organic?.length ? 'organic' : 'chemical'); reloadHistory()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const reset = () => { setFile(null); setPreview(null); setResult(null) }

  const r = result?.result
  const pct = (x) => (x < 0.01 ? '<1' : Math.min(99, Math.round(x * 100)))
  const conf = r ? Math.min(99, Math.round(r.confidence * 100)) : 0
  return (
    <>
      <div className="head"><div>
        <h1>Check a leaf</h1>
        <p>Photograph one affected leaf, close up, in daylight. Get the likely problem and what to do about it.</p>
      </div></div>

      <div className="grid2" style={{ alignItems: 'start' }}>
        <div className="stack">
          <Field label="Which crop is it?" hint="Telling the crop makes the answer much more reliable.">
            <select className="input" value={crop} onChange={(e) => setCrop(e.target.value)}>
              <option value="">Not sure</option>
              {scanCrops.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <div className={`drop ${over ? 'over' : ''}`} role="button" tabIndex={0}
            onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); choose(e.dataTransfer.files[0]) }}>
            {preview ? <img src={preview} alt="The leaf you chose" /> : <>
              <Camera size={40} color="var(--indigo-2)" />
              <b>Take a photo or choose one</b>
              <span className="small muted">One leaf filling most of the frame, in focus</span>
            </>}
          </div>
          <input ref={input} type="file" accept="image/*" capture="environment" hidden onChange={(e) => choose(e.target.files[0])} />
          <div className="row">
            <button className="btn" onClick={submit} disabled={!file || busy}>{busy ? 'Checking…' : 'Check this leaf'}</button>
            {file && <button className="btn ghost" onClick={reset}><RotateCcw size={16} />Another photo</button>}
          </div>
          {!result && <p className="small muted">Covers 15 crops: rice, maize, tomato, potato, chilli and capsicum, grapes, apple and more. For other crops, <Link to="/assistant">describe the problem</Link> or <Link to="/community">ask other farmers</Link>.</p>}
        </div>

        <div>
          {result && (
            <div className="panel">
              {result.unsure && <div style={{ marginBottom: 14 }}><Notice kind="warn">The model is not sure about this photo. Retake it closer, in daylight, with one leaf filling the frame, and compare with the other possibilities below.</Notice></div>}
              {!result.crop_used && result.crop_seen.confidence < 0.6 && <div style={{ marginBottom: 14 }}><Notice kind="warn">This may not be a leaf of a crop the checker knows. Choose the crop above and check again.</Notice></div>}
              <div className="result-head">
                <div>
                  <span className={`chip ${SEVERITY[r.severity][0]}`}>{SEVERITY[r.severity][1]}</span>
                  <h2 style={{ marginTop: 8 }}>{r.name}</h2>
                  <p className="muted small">{r.crop}{r.kind !== 'healthy' ? `, caused by a ${r.kind}` : ''}</p>
                </div>
                <div style={{ textAlign: 'right' }}><b style={{ fontSize: 'var(--t-xl)' }}>{conf}%</b><div className="xs muted">confidence</div></div>
              </div>
              <div className={`meter ${conf >= 70 ? '' : conf >= 50 ? 'mid' : 'low'}`}><i style={{ width: `${conf}%` }} /></div>
              <div className="advice">
                <h4>What it looks like</h4><p className="prose">{r.symptoms}</p>
                {r.cause && <><h4>Cause</h4><p className="prose">{r.cause}</p></>}
                {r.spread && <Notice kind="danger">{r.spread}</Notice>}
                {r.kind !== 'healthy' && (
                  <div style={{ marginTop: 16 }}>
                    <Tabs label="Treatment" value={tab} onChange={setTab} options={[
                      { value: 'organic', label: 'First steps' }, { value: 'chemical', label: 'Sprays' }, { value: 'prevention', label: 'Prevent' }]} />
                    <ul style={{ marginTop: 12 }}>
                      {(tab === 'organic' ? r.organic : tab === 'chemical' ? r.chemical : r.prevention).map((x) => <li key={x}>{x}</li>)}
                      {tab === 'chemical' && r.chemical.length === 0 && <li>No spray cures this. Remove affected plants and follow the first steps.</li>}
                    </ul>
                    {tab === 'chemical' && r.chemical.length > 0 && <p className="xs muted" style={{ marginTop: 8 }}>Read the label, wear gloves and a mask, and keep to the waiting period before harvest.</p>}
                  </div>
                )}
              </div>
              {result.alternatives.length > 0 && (
                <div style={{ marginTop: 18 }}>
                  <h4 style={{ marginBottom: 6 }}>Could also be</h4>
                  {result.alternatives.map((a) => (
                    <div key={a.id} className="row between small" style={{ padding: '4px 0' }}><span>{a.name}</span><span className="muted">{pct(a.confidence)}%</span></div>
                  ))}
                </div>
              )}
              <p className="small" style={{ marginTop: 18 }}><Phone size={14} style={{ display: 'inline', verticalAlign: '-2px' }} /> Not improving? Call the Kisan Call Centre on <a href={`tel:${result.helpline.replace(/-/g, '')}`}><b>{result.helpline}</b></a> (free) or show the leaf at your nearest KVK.</p>
            </div>
          )}
          {!result && history?.scans?.length > 0 && (
            <div>
              <h3 style={{ marginBottom: 10 }}>Earlier checks</h3>
              <div className="list">
                {history.scans.slice(0, 8).map((s) => (
                  <div key={s.id} className="row between small">
                    <span><b>{s.result_name}</b>{s.unsure && <span className="muted"> (unsure)</span>}</span>
                    <span className="muted">{pct(s.confidence)}%, {timeAgo(s.created_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      <p className="footer-note">The checker is a neural network trained on 67,000 leaf photos (PlantVillage, PlantDoc and Paddy Doctor). On field photos it never saw during training it named the right problem first 73% of the time when told the crop, and had it in its top three 93% of the time. Treat it as a first opinion, not a lab test.</p>
    </>
  )
}
