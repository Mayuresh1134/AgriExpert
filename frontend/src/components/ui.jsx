import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'

/* ---------------- toasts */
const ToastContext = createContext(() => {})
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((text, kind = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setItems((xs) => [...xs, { id, text, kind }])
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 3800)
  }, [])
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
      </div>
    </ToastContext.Provider>
  )
}
export const useToast = () => useContext(ToastContext)

/* ---------------- basics */
export function Loading({ text = 'Loading…' }) {
  return <div className="loading"><div className="spinner" aria-hidden="true" />{text}</div>
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="notice danger" role="alert">
      <AlertTriangle size={18} />
      <div>
        {error.message || String(error)}
        {onRetry && <> <button className="btn ghost sm" onClick={onRetry}>Try again</button></>}
      </div>
    </div>
  )
}

export function Notice({ kind = 'info', children }) {
  const Icon = kind === 'good' ? CheckCircle2 : kind === 'info' ? Info : AlertTriangle
  return <div className={`notice ${kind}`}><Icon size={18} /><div>{children}</div></div>
}

export function Empty({ title, children, action }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

/** A labelled form control. Use `group` when the child is a set of buttons rather than one input,
 *  so the label names the group instead of becoming the first button's name. */
export function Field({ label, hint, error, group = false, children }) {
  const Tag = group ? 'div' : 'label'
  return (
    <Tag className="field" {...(group ? { role: 'group', 'aria-label': label } : {})}>
      <span className="label">{label}</span>
      {children}
      {hint && !error && <span className="hint">{hint}</span>}
      {error && <span className="form-error">{error}</span>}
    </Tag>
  )
}

export function Choices({ value, onChange, options, cards = false, label }) {
  return (
    <div className={`choices ${cards ? 'cards' : ''}`} role="group" aria-label={label}>
      {options.map((o) => (
        <button type="button" key={o.value} className="choice" aria-pressed={value === o.value}
          onClick={() => onChange(value === o.value && o.toggle ? null : o.value)}>
          {o.label}{o.sub && <small>{o.sub}</small>}
        </button>
      ))}
    </div>
  )
}

export function Tabs({ value, onChange, options, label }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button type="button" key={o.value} role="tab" aria-selected={value === o.value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  )
}

export function Dialog({ title, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const first = ref.current?.querySelector('input, select, textarea, button:not(.iconbtn)')
    first?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="dialog-head">
          <h2>{title}</h2>
          <button className="btn ghost iconbtn" onClick={onClose} aria-label="Close"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

/** Run an async action with a busy flag and a toast on failure. */
export function useAction() {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const run = useCallback(async (fn, success) => {
    setBusy(true)
    try {
      const r = await fn()
      if (success) toast(success)
      return r
    } catch (e) {
      toast(e.message || 'Something went wrong', 'error')
      throw e
    } finally { setBusy(false) }
  }, [toast])
  return [busy, run]
}

export function Score({ points, level, next, nextAt, start }) {
  const pct = nextAt ? Math.min(1, (points - start) / (nextAt - start)) : 1
  const r = 15, c = 2 * Math.PI * r
  return (
    <svg className="ring" viewBox="0 0 38 38" aria-hidden="true">
      <circle cx="19" cy="19" r={r} fill="none" stroke="#E8EBF2" strokeWidth="5" />
      <circle cx="19" cy="19" r={r} fill="none" stroke="#E3A21A" strokeWidth="5" strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`} transform="rotate(-90 19 19)" />
    </svg>
  )
}
