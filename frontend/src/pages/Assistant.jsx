import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Send, Trash2 } from 'lucide-react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { ErrorNote, Loading, useToast } from '../components/ui.jsx'

const SUGGESTIONS = [
  'What should I do on my farm this week?',
  'Will it rain in the next few days?',
  'How much urea for my crop?',
  'Which crop should I grow next season?',
  'Is it a good time to sell?',
  'Tell me about crop insurance',
]

export default function Assistant() {
  useTitle('Ask Krishi Mitra')
  const { user, options } = useAuth()
  const toast = useToast()
  const { data, error, loading, reload } = useApi('/assistant')
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [language, setLanguage] = useState(user.language || 'en')
  const end = useRef(null)
  useEffect(() => { if (data) setMessages(data.messages) }, [data])
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [messages, busy])

  const send = async (q) => {
    const question = (q ?? text).trim()
    if (!question || busy) return
    setText('')
    setMessages((m) => [...m, { role: 'user', text: question, id: `tmp-${Date.now()}` }])
    setBusy(true)
    try {
      const r = await api('/assistant', { method: 'POST', body: { message: question, language } })
      setMessages((m) => [...m, { role: 'assistant', text: r.answer, links: r.links, id: `a-${Date.now()}` }])
    } catch (e) {
      toast(e.message, 'error')
      setMessages((m) => m.slice(0, -1)); setText(question)
    } finally { setBusy(false) }
  }
  const clear = async () => {
    if (!window.confirm('Clear the whole conversation?')) return
    await api('/assistant', { method: 'DELETE' }); setMessages([])
  }

  const gemini = data?.mode === 'gemini'
  return (
    <div className="chat">
      <div className="head" style={{ marginBottom: 10 }}>
        <div>
          <h1>Ask Krishi Mitra</h1>
          <p>{gemini ? 'Answers use your farm, your crops and this week\'s weather.' : 'Built-in assistant: knows your crops, weather, fertiliser, prices and schemes. Answers in English.'}</p>
        </div>
        <div className="row">
          {gemini && options && (
            <select className="input" aria-label="Answer language" value={language} onChange={(e) => setLanguage(e.target.value)} style={{ width: 150 }}>
              {Object.entries(options.languages).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          )}
          {messages.length > 0 && <button className="btn ghost iconbtn" onClick={clear} aria-label="Clear conversation"><Trash2 size={18} /></button>}
        </div>
      </div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} onRetry={reload} />
      <div className="messages" aria-live="polite">
        {messages.length === 0 && data && <p className="muted" style={{ marginTop: 20 }}>Ask anything about your crops. Try one of these:</p>}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            {m.text}
            {m.links?.length > 0 && <div className="links">{m.links.map((l) => <Link key={l.to} className="btn secondary sm" to={l.to}>{l.label}</Link>)}</div>}
          </div>
        ))}
        {busy && <div className="msg assistant"><div className="spinner" aria-label="Thinking" /></div>}
        <div ref={end} />
      </div>
      {messages.length < 2 && (
        <div className="suggest">{SUGGESTIONS.map((s) => <button key={s} className="choice" onClick={() => send(s)}>{s}</button>)}</div>
      )}
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send() }}>
        <textarea className="input" rows={1} value={text} placeholder="Type your question…" aria-label="Your question"
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }} />
        <button className="btn iconbtn" style={{ width: 48, height: 48 }} disabled={busy || !text.trim()} aria-label="Send"><Send size={20} /></button>
      </form>
    </div>
  )
}
