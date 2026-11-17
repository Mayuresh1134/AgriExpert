import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { Field, Tabs } from '../components/ui.jsx'
import { SeasonRibbon } from '../components/farm.jsx'
import { Logo } from '../App.jsx'
import { useTitle } from '../hooks.js'

// A wheat season, used as the picture on the sign-in screen.
const DEMO = {
  day: 72, stage: 'flowering', stage_label: 'Flowering',
  windows: [
    { id: 'sowing', label: 'Sowing', start_day: 0, end_day: 3 },
    { id: 'germination', label: 'Germination', start_day: 3, end_day: 18 },
    { id: 'vegetative', label: 'Growth', start_day: 18, end_day: 60 },
    { id: 'flowering', label: 'Flowering', start_day: 60, end_day: 90 },
    { id: 'maturation', label: 'Grain filling', start_day: 90, end_day: 118 },
    { id: 'harvesting', label: 'Harvest', start_day: 118, end_day: 146 },
  ],
}

export default function AuthPage() {
  const [mode, setMode] = useState('login')
  useTitle(mode === 'login' ? 'Log in' : 'Create account')
  const { signIn, options } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', login: '', password: '', language: 'en' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    setError(''); setBusy(true)
    try {
      const me = await signIn(mode === 'login' ? '/auth/login' : '/auth/register', form)
      navigate(me.farm ? '/' : '/farm', { replace: true })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="auth">
      <section className="auth-art">
        <div className="row"><Logo size={36} /><strong style={{ fontSize: '1.3rem' }}>AgriExpert</strong></div>
        <div>
          <h1>Know what your field needs this week.</h1>
          <p>What to grow on your land, what to do at every stage, which leaf disease it is, and where to sell for the best price.</p>
        </div>
        <SeasonRibbon progress={DEMO} big />
      </section>
      <section className="auth-form">
        <form className="box form" onSubmit={submit} noValidate>
          <Tabs value={mode} onChange={(m) => { setMode(m); setError('') }} label="Account"
            options={[{ value: 'login', label: 'Log in' }, { value: 'register', label: 'Create account' }]} />
          <div>
            <h2>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
            <p className="muted">{mode === 'login' ? 'Use the mobile number or email you signed up with.' : 'Takes a minute. Your data stays on this server.'}</p>
          </div>
          {mode === 'register' && (
            <Field label="Your name"><input className="input" value={form.name} onChange={set('name')} autoComplete="name" required /></Field>
          )}
          <Field label="Mobile number or email">
            <input className="input" value={form.login} onChange={set('login')} autoComplete="username" inputMode="email" placeholder="98765 43210" required />
          </Field>
          <Field label="Password" hint={mode === 'register' ? 'At least 6 characters' : undefined}>
            <input className="input" type="password" value={form.password} onChange={set('password')}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
          </Field>
          {mode === 'register' && options && (
            <Field label="Language for Krishi Mitra answers" hint="Screens are in English; the assistant can answer in your language when Gemini is connected.">
              <select className="input" value={form.language} onChange={set('language')}>
                {Object.entries(options.languages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn block" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}</button>
        </form>
      </section>
    </div>
  )
}
