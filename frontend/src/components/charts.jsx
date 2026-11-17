import { useMemo, useState } from 'react'
import { monthLabel, rupees } from '../format.js'

/** Monthly price history, the forecast with its likely range, and the MSP line. */
export function PriceChart({ history, forecast = [], msp }) {
  const [hover, setHover] = useState(null)
  const W = 720, H = 260, L = 56, R = 16, T = 14, B = 30
  const points = useMemo(() => {
    const h = history.map(([m, p]) => ({ m, p, kind: 'h' }))
    const f = forecast.map((x) => ({ m: x.month, p: x.price, lo: x.low, hi: x.high, kind: 'f' }))
    return [...h, ...f]
  }, [history, forecast])
  if (!points.length) return null
  const values = points.flatMap((p) => [p.p, p.lo, p.hi]).filter(Boolean).concat(msp ? [msp] : [])
  let lo = Math.min(...values), hi = Math.max(...values)
  const pad = (hi - lo) * 0.08 || hi * 0.1
  lo = Math.max(0, lo - pad); hi += pad
  const x = (i) => L + (i / (points.length - 1)) * (W - L - R)
  const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B)
  const hist = points.map((p, i) => ({ ...p, i })).filter((p) => p.kind === 'h')
  const fc = points.map((p, i) => ({ ...p, i })).filter((p) => p.kind === 'f')
  const line = (arr) => arr.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.p).toFixed(1)}`).join('')
  const lastH = hist[hist.length - 1]
  const band = fc.length
    ? `M${x(lastH.i)},${y(lastH.p)} ` + fc.map((p) => `L${x(p.i)},${y(p.hi)}`).join(' ') + ' ' +
      [...fc].reverse().map((p) => `L${x(p.i)},${y(p.lo)}`).join(' ') + ` L${x(lastH.i)},${y(lastH.p)}Z`
    : ''
  const ticks = 4
  const yt = Array.from({ length: ticks + 1 }, (_, k) => lo + ((hi - lo) * k) / ticks)
  const xt = points.map((p, i) => ({ ...p, i })).filter((p) => p.m.endsWith('-01'))

  const onMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const px = ((e.clientX - rect.left) / rect.width) * W
    const i = Math.round(((px - L) / (W - L - R)) * (points.length - 1))
    setHover(points[Math.max(0, Math.min(points.length - 1, i))] ? Math.max(0, Math.min(points.length - 1, i)) : null)
  }
  const hp = hover !== null ? points[hover] : null
  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} onMouseMove={onMove} onMouseLeave={() => setHover(null)}
        role="img" aria-label="Price per quintal by month, with forecast">
        {yt.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="#E8EBF2" />
            <text x={L - 8} y={y(v) + 4} textAnchor="end">{Math.round(v).toLocaleString('en-IN')}</text>
          </g>
        ))}
        {xt.map((p) => <text key={p.m} x={x(p.i)} y={H - 8} textAnchor="middle">{p.m.slice(0, 4)}</text>)}
        {msp && <>
          <line x1={L} x2={W - R} y1={y(msp)} y2={y(msp)} stroke="#2E7D4B" strokeWidth="1.5" strokeDasharray="5 4" />
          <text x={W - R} y={y(msp) - 6} textAnchor="end" style={{ fill: '#2E7D4B', fontWeight: 700 }}>MSP {rupees(msp)}</text>
        </>}
        {band && <path d={band} fill="#E3A21A" opacity="0.22" />}
        <path d={line(hist)} fill="none" stroke="#1F2A56" strokeWidth="2.2" strokeLinejoin="round" />
        {fc.length > 0 && <path d={line([lastH, ...fc])} fill="none" stroke="#B57F00" strokeWidth="2.2" strokeDasharray="6 4" />}
        {hp && <>
          <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke="#7A82A0" strokeDasharray="2 3" />
          <circle cx={x(hover)} cy={y(hp.p)} r="4.5" fill={hp.kind === 'f' ? '#E3A21A' : '#1F2A56'} />
          <g transform={`translate(${Math.min(x(hover) + 10, W - 170)}, ${T + 4})`}>
            <rect width="160" height={hp.kind === 'f' ? 50 : 34} rx="8" fill="#fff" stroke="#D8DDE8" />
            <text x="10" y="15" style={{ fill: '#4A5378', fontWeight: 700 }}>{monthLabel(hp.m)}{hp.kind === 'f' ? ' (forecast)' : ''}</text>
            <text x="10" y="29" style={{ fill: '#1F2A56', fontSize: 13, fontWeight: 800 }}>{rupees(hp.p)} / quintal</text>
            {hp.kind === 'f' && <text x="10" y="43">likely {rupees(hp.lo)} to {rupees(hp.hi)}</text>}
          </g>
        </>}
      </svg>
      <div className="legend">
        <span><i style={{ background: '#1F2A56' }} />Monthly median, all mandis in India</span>
        {fc.length > 0 && <span><i style={{ background: '#B57F00' }} />Forecast, shaded area is the likely range (8 in 10)</span>}
        {msp && <span><i style={{ background: '#2E7D4B' }} />Minimum Support Price</span>}
      </div>
    </div>
  )
}

const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
export function SeasonalBars({ pct, best }) {
  const max = Math.max(...pct.map(Math.abs), 1)
  const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return (
    <div className="seasonal" role="img" aria-label={`Usual price by month compared with the yearly average; highest in ${best}`}>
      {pct.map((v, i) => (
        <div key={i} className={names[i] === best ? 'best' : ''} title={`${names[i]}: ${v > 0 ? '+' : ''}${v}%`}>
          <span className="up">{v > 0 && <><em>+{Math.round(v)}</em><i style={{ height: `${(v / max) * 100}%` }} /></>}</span>
          <span className="down">{v < 0 && <><i className="neg" style={{ height: `${(-v / max) * 100}%` }} /><em>{Math.round(v)}</em></>}</span>
          <b>{MONTHS[i]}</b>
        </div>
      ))}
    </div>
  )
}

export function Bar({ value, max = 100, color }) {
  return <span className="bar"><i style={{ width: `${Math.max(2, (value / max) * 100)}%`, background: color }} /></span>
}
