import { Link } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { useApi, useTitle } from '../hooks.js'
import { ErrorNote, Loading } from '../components/ui.jsx'

const MATCH = {
  yes: ['leaf', 'Fits your farm'],
  maybe: ['sun', 'Check eligibility'],
  done: ['', 'Already done'],
  no: ['chilli', 'Probably not for you'],
}

export default function Schemes() {
  useTitle('Schemes')
  const { data, error, loading, reload } = useApi('/schemes')
  return (
    <>
      <div className="head"><div>
        <h1>Government schemes</h1>
        <p>Central schemes for farmers, checked against your farm profile. Open one to see who qualifies, what to bring and how to apply.</p>
      </div></div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} onRetry={reload} />
      {data && <>
        {data.schemes.map((s) => (
          <details key={s.id} className="panel scheme">
            <summary>
              <div>
                <h3>{s.name}</h3>
                <p className="small muted">{s.full}</p>
                <p style={{ marginTop: 6 }}>{s.benefit}</p>
              </div>
              <span className={`chip ${MATCH[s.match][0]}`}>{MATCH[s.match][1]}</span>
            </summary>
            {s.why && <p className="small" style={{ marginBottom: 10 }}><b>For you: </b>{s.why}</p>}
            <dl className="kv">
              <dt>Who can apply</dt><dd>{s.who}</dd>
              <dt>Bring</dt><dd>{s.documents.join(', ')}</dd>
              <dt>How</dt><dd>{s.how}</dd>
            </dl>
            <a className="btn secondary sm" style={{ marginTop: 14 }} href={s.url} target="_blank" rel="noreferrer">Official site<ExternalLink size={14} /></a>
          </details>
        ))}
        <p className="footer-note">Details checked in {data.checked}. Amounts and rules change, and the official site has the final word. Your state also runs its own schemes: ask at the agriculture office or a Common Service Centre. The match uses your <Link to="/farm">farm profile</Link> and the age in your <Link to="/profile">profile</Link>.</p>
      </>}
    </>
  )
}
