import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Check, ThumbsUp } from 'lucide-react'
import { api, qs } from '../api.js'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Choices, Dialog, Empty, ErrorNote, Field, Loading, Tabs, useAction, useToast } from '../components/ui.jsx'
import { timeAgo } from '../format.js'

export default function Community() {
  useTitle('Community')
  const { farm, options } = useAuth()
  const [scope, setScope] = useState('all')
  const [crop, setCrop] = useState('')
  const { data, error, loading, reload, setData } = useApi(`/community${qs({ scope: scope === 'all' ? '' : scope, crop })}`)
  const [writing, setWriting] = useState(false)
  const toast = useToast()
  const cropName = Object.fromEntries((options?.crops || []).map((c) => [c.id, c.name]))

  const vote = async (p) => {
    try {
      const r = await api(`/community/${p.id}/upvote`, { method: 'POST' })
      setData((d) => ({ posts: d.posts.map((x) => (x.id === p.id ? { ...x, upvoted: r.upvoted, upvotes: r.upvotes } : x)) }))
    } catch (e) { toast(e.message, 'error') }
  }
  return (
    <>
      <div className="head">
        <div><h1>Community</h1><p>Ask farmers near you, or share what worked on your field. A helpful answer earns points.</p></div>
        <button className="btn" onClick={() => setWriting(true)}>Ask or share</button>
      </div>
      <div className="row between" style={{ marginBottom: 14 }}>
        <Tabs label="Show posts from" value={scope} onChange={setScope} options={[
          { value: 'all', label: 'All India' }, { value: 'state', label: farm.state }, { value: 'district', label: farm.district }, { value: 'mine', label: 'Mine' }]} />
        <select className="input" aria-label="Filter by crop" value={crop} onChange={(e) => setCrop(e.target.value)} style={{ width: 200 }}>
          <option value="">All crops</option>
          {(options?.crops || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} onRetry={reload} />
      {data?.posts.length === 0 && (
        <Empty title="No posts here yet" action={<button className="btn" onClick={() => setWriting(true)}>Write the first one</button>}>
          Be the first to ask a question or share a tip{scope === 'district' ? ` in ${farm.district}` : ''}.
        </Empty>
      )}
      {data?.posts.length > 0 && (
        <div className="list">
          {data.posts.map((p) => (
            <div key={p.id} className="post">
              <div className="vote">
                <button aria-pressed={p.upvoted} disabled={p.mine} onClick={() => vote(p)} aria-label={p.upvoted ? 'Remove upvote' : 'Upvote'}><ThumbsUp size={16} /></button>
                {p.upvotes}
              </div>
              <Link to={`/community/${p.id}`} style={{ color: 'inherit', textDecoration: 'none' }}>
                <div className="row" style={{ gap: 6 }}>
                  <span className={`chip ${p.kind === 'tip' ? 'leaf' : ''}`}>{p.kind === 'tip' ? 'Tip' : 'Question'}</span>
                  {p.solved && <span className="chip leaf"><Check size={12} />Solved</span>}
                  {p.crop && <span className="chip soil">{cropName[p.crop]}</span>}
                </div>
                <h3 style={{ marginTop: 6 }}>{p.title}</h3>
                <p className="small muted" style={{ marginTop: 2, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>{p.body}</p>
                <div className="meta"><span>{p.author} ({p.author_level})</span>{p.district && <span>{p.district}, {p.state}</span>}<span>{timeAgo(p.created_at)}</span><span>{p.replies} {p.replies === 1 ? 'answer' : 'answers'}</span></div>
              </Link>
            </div>
          ))}
        </div>
      )}
      {writing && <NewPost onClose={() => setWriting(false)} onPosted={() => { setWriting(false); reload() }} />}
    </>
  )
}

function NewPost({ onClose, onPosted }) {
  const { options } = useAuth()
  const [busy, run] = useAction()
  const [f, setF] = useState({ kind: 'question', title: '', body: '', crop: '' })
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault(); setError('')
    try { await run(() => api('/community', { method: 'POST', body: { ...f, crop: f.crop || null } }), 'Posted. +5 points'); onPosted() } catch (err) { setError(err.message) }
  }
  return (
    <Dialog title="Ask or share" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <Choices value={f.kind} onChange={(v) => setF({ ...f, kind: v })} options={[{ value: 'question', label: 'Ask a question' }, { value: 'tip', label: 'Share a tip' }]} />
        <Field label={f.kind === 'tip' ? 'Your tip in one line' : 'Your question in one line'}>
          <input className="input" value={f.title} maxLength={140} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder={f.kind === 'tip' ? 'e.g. Neem cake cut white grub in my groundnut' : 'e.g. Yellow leaves on soybean after rain'} />
        </Field>
        <Field label="Details" hint="Crop stage, what you see, what you have tried">
          <textarea className="input" value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} />
        </Field>
        <Field label="Crop (optional)">
          <select className="input" value={f.crop} onChange={(e) => setF({ ...f, crop: e.target.value })}>
            <option value="">None</option>
            {(options?.crops || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </Field>
        {error && <p className="form-error">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? 'Posting…' : 'Post'}</button>
      </form>
    </Dialog>
  )
}

export function PostDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, error, loading, reload, setData } = useApi(`/community/${id}`)
  const [reply, setReply] = useState('')
  const [busy, run] = useAction()
  useTitle(data?.post.title)
  if (loading && !data) return <Loading />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  const { post, replies } = data
  const send = async (e) => {
    e.preventDefault()
    if (!reply.trim()) return
    await run(() => api(`/community/${id}/replies`, { method: 'POST', body: { body: reply } }), post.mine ? 'Reply added' : 'Answer posted. +10 points')
    setReply(''); reload()
  }
  const accept = (rid) => run(() => api(`/community/${id}/replies/${rid}/accept`, { method: 'POST' }), 'Marked as the answer').then(setData)
  const remove = async () => {
    if (!window.confirm('Delete this post and its answers?')) return
    await run(() => api(`/community/${id}`, { method: 'DELETE' }), 'Post deleted'); navigate('/community')
  }
  return (
    <>
      <Link to="/community" className="btn ghost sm" style={{ paddingLeft: 0, marginBottom: 8 }}><ArrowLeft size={16} />Community</Link>
      <div className="panel">
        <div className="row" style={{ gap: 6 }}>
          <span className={`chip ${post.kind === 'tip' ? 'leaf' : ''}`}>{post.kind === 'tip' ? 'Tip' : 'Question'}</span>
          {post.solved && <span className="chip leaf"><Check size={12} />Solved</span>}
        </div>
        <h1 style={{ marginTop: 8, fontSize: 'var(--t-xl)' }}>{post.title}</h1>
        <p className="small muted" style={{ marginTop: 4 }}>{post.author} ({post.author_level}){post.district ? `, ${post.district}` : ''}, {timeAgo(post.created_at)}</p>
        <p style={{ marginTop: 14, whiteSpace: 'pre-wrap' }} className="prose">{post.body}</p>
        {post.mine && <button className="btn danger sm" style={{ marginTop: 14 }} onClick={remove}>Delete</button>}
      </div>
      <section className="section">
        <div className="section-title"><h2>{replies.length} {replies.length === 1 ? 'answer' : 'answers'}</h2></div>
        {replies.length > 0 && (
          <div className="list">
            {replies.map((r) => (
              <div key={r.id} className={`reply ${r.accepted ? 'accepted' : ''}`}>
                <p style={{ whiteSpace: 'pre-wrap' }}>{r.body}</p>
                <div className="row between" style={{ marginTop: 6 }}>
                  <span className="xs muted">{r.author} ({r.author_level}), {timeAgo(r.created_at)}{r.accepted ? '. Marked as the answer' : ''}</span>
                  {post.mine && !r.accepted && post.kind === 'question' && <button className="btn ghost sm" disabled={busy} onClick={() => accept(r.id)}><Check size={14} />This solved it</button>}
                </div>
              </div>
            ))}
          </div>
        )}
        <form className="form" style={{ marginTop: 14 }} onSubmit={send}>
          <Field label={post.mine ? 'Add more detail' : 'Your answer'}>
            <textarea className="input" value={reply} onChange={(e) => setReply(e.target.value)} />
          </Field>
          <button className="btn" disabled={busy || !reply.trim()}>{post.mine ? 'Reply' : 'Post answer'}</button>
        </form>
      </section>
    </>
  )
}
