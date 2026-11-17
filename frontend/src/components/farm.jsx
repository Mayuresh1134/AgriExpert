import { Cloud, CloudLightning, CloudRain, CloudSun, Snowflake, Sun } from 'lucide-react'
import { weekday } from '../format.js'

/* Stage colours run from soil through leaf to grain: the crop's year as a band. */
export const STAGE_COLORS = {
  preparation: '#8B5A36',
  sowing: '#A9764A',
  germination: '#8DB86B',
  vegetative: '#2E7D4B',
  flowering: '#5E9E3A',
  maturation: '#C9A227',
  harvesting: '#E3A21A',
}

/** The season ribbon: every stage of the crop as a coloured band, with a pin at today. */
export function SeasonRibbon({ progress, big = false, showLabels = true }) {
  const windows = progress.windows.filter((w) => w.id !== 'preparation' || progress.day < 0)
  const start = windows[0].start_day
  const end = windows[windows.length - 1].end_day
  const span = end - start
  const pos = Math.max(0, Math.min(1, (progress.day - start) / span))
  const pinLabel = progress.day < 0 ? `${-progress.day} days to sowing` : `Day ${progress.day}`
  return (
    <div className={`ribbon ${big ? 'big' : ''}`} aria-label={`${progress.stage_label}, ${pinLabel}`} role="img">
      <div className="ribbon-pin" style={{ left: `${pos * 100}%` }}>
        <span>{pinLabel}</span><i />
      </div>
      <div className="ribbon-band">
        {windows.map((w) => {
          const width = ((w.end_day - w.start_day) / span) * 100
          const past = progress.day >= w.start_day
          return <div key={w.id} className={past ? 'past' : 'future'} style={{ width: `${width}%`, background: STAGE_COLORS[w.id] }} title={w.label} />
        })}
      </div>
      {showLabels && (
        <div className="ribbon-labels" aria-hidden="true">
          {windows.map((w) => (
            <div key={w.id} className={w.id === progress.stage ? 'now' : ''} style={{ width: `${((w.end_day - w.start_day) / span) * 100}%` }}>
              {w.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const ICONS = { sun: Sun, partly: CloudSun, cloud: Cloud, rain: CloudRain, storm: CloudLightning, snow: Snowflake }
export function WeatherIcon({ icon, size = 22 }) {
  const Icon = ICONS[icon] || Cloud
  return <Icon size={size} aria-hidden="true" />
}

export function WeatherStrip({ forecast }) {
  if (!forecast) return null
  const days = forecast.days || []
  const maxRain = Math.max(20, ...days.map((d) => d.rain_mm || 0))
  return (
    <div className="weather" role="table" aria-label="Seven-day forecast">
      {days.map((d, i) => (
        <div key={d.date} className={`wday ${i === 0 ? 'today' : ''}`} role="row">
          <span className="d">{i === 0 ? 'Today' : weekday(d.date)}</span>
          {forecast.live && <WeatherIcon icon={d.icon} />}
          {d.tmax !== null && d.tmax !== undefined
            ? <span className="t">{Math.round(d.tmax)}° <small>{Math.round(d.tmin)}°</small></span>
            : <span className="t muted">—</span>}
          <span className="rainbar" title={`${d.rain_mm ?? 0} mm`}><i style={{ height: `${Math.min(100, ((d.rain_mm || 0) / maxRain) * 100)}%` }} /></span>
          <span className="mm">{d.rain_mm === null || d.rain_mm === undefined ? '—' : `${Math.round(d.rain_mm)} mm`}</span>
        </div>
      ))}
    </div>
  )
}

export function Alerts({ alerts }) {
  if (!alerts?.length) return null
  return (
    <div className="alerts">
      {alerts.map((a, i) => (
        <div key={i} className={`alert ${a.level}`} role={a.level === 'danger' ? 'alert' : undefined}>
          <div><b>{a.title}</b><p>{a.text}</p></div>
        </div>
      ))}
    </div>
  )
}

export function CropName({ name, local }) {
  return <>{name}{local && <span className="local" lang="hi">{local}</span>}</>
}
