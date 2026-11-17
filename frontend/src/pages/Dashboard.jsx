import { Link } from 'react-router-dom'
import { Droplets, MessageCircle, ScanLine, Sprout, Store } from 'lucide-react'
import { useAuth } from '../auth.jsx'
import { useApi, useTitle } from '../hooks.js'
import { Empty, ErrorNote, Loading, Notice, Score } from '../components/ui.jsx'
import { Alerts, CropName, SeasonRibbon, WeatherIcon, WeatherStrip } from '../components/farm.jsx'
import { dateLabel, inDays, monthLabel, num, rupees, signed } from '../format.js'

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function Dashboard() {
  useTitle('Home')
  const { user } = useAuth()
  const { data, error, loading, reload } = useApi('/dashboard')
  if (loading && !data) return <Loading />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  const { farm, weather, cycles = [], prices = [], alerts = [] } = data
  const u = data.user
  const now = weather?.current
  return (
    <>
      <div className="hello">
        <div>
          <h1>{greeting()}, {user.name.split(' ')[0]}</h1>
          <p>{farm.village ? `${farm.village}, ` : ''}{farm.district}, {farm.state}. {dateLabel(data.today, { weekday: 'long', day: 'numeric', month: 'long' })}.</p>
        </div>
        <Link to="/profile" className="score" aria-label={`Farm score ${u.points} points, level ${u.level}`}>
          <Score points={u.points} nextAt={u.next_at} start={u.level_start} />
          <span><b>{u.points}</b><small>{u.level}</small></span>
        </Link>
      </div>

      <section aria-labelledby="wx">
        <h2 id="wx" className="sr-only">Weather</h2>
        {now && (
          <div className="weather-now">
            <WeatherIcon icon={now.icon} size={34} />
            <span className="big">{Math.round(now.temp)}°</span>
            <span>{now.summary}<br /><span className="small">Humidity {now.humidity}%, wind {Math.round(now.wind_kmh)} km/h</span></span>
          </div>
        )}
        <WeatherStrip forecast={weather} />
        {!weather?.live && (
          <p className="small muted" style={{ marginTop: 8 }}>
            {weather?.error ? `${weather.error}. ` : ''}Showing the normal rainfall for {weather?.month}{weather?.normal_month_rain_mm != null ? ` (${weather.normal_month_rain_mm} mm in the month)` : ''} instead.
          </p>
        )}
      </section>

      {alerts.length > 0 && <section className="section"><Alerts alerts={alerts} /></section>}

      <section className="section" aria-labelledby="mycrops">
        <div className="section-title"><h2 id="mycrops">Your crops this week</h2><Link to="/crops">All crops</Link></div>
        {cycles.length === 0 ? (
          <Empty title="Nothing planted yet" action={<div className="row"><Link className="btn" to="/recommend">See what to grow</Link><Link className="btn secondary" to="/crops?new=1">I have already sown</Link></div>}>
            Start tracking a crop and this page fills with the week's tasks, weather warnings for its stage and water needs.
          </Empty>
        ) : cycles.map((c) => <CropThisWeek key={c.id} c={c} />)}
      </section>

      <section className="section">
        <div className="quick">
          <Link to="/scan"><ScanLine />Check a leaf<small>Photo to diagnosis</small></Link>
          <Link to="/recommend"><Sprout />What to grow<small>{data.season_label}</small></Link>
          <Link to="/markets"><Store />Best mandi<small>Prices and forecast</small></Link>
          <Link to="/assistant"><MessageCircle />Ask Krishi Mitra<small>Any farming question</small></Link>
        </div>
      </section>

      {prices.length > 0 && (
        <section className="section" aria-labelledby="prices">
          <div className="section-title"><h2 id="prices">Prices for your crops</h2><Link to="/markets">Markets</Link></div>
          <div className="list">
            {prices.map((p) => (
              <Link key={p.crop} className="item" to={`/markets?crop=${p.crop}`}>
                <div className="pricerow">
                  <div><b>{p.name}</b><div className="xs muted">All-India mandi median, {monthLabel(p.month)}{p.msp ? `. MSP ${rupees(p.msp)}` : ''}</div></div>
                  <div style={{ textAlign: 'right' }}>
                    <span className="p">{rupees(p.latest)}</span><span className="xs muted"> /q</span>
                    <div className="xs muted">{signed(p.change_12m_pct)} on last year{p.next ? `. ${monthLabel(p.next.month, false)} forecast ${rupees(p.next.price)}` : ''}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </>
  )
}

function CropThisWeek({ c }) {
  const p = c.progress
  return (
    <Link to={`/crops/${c.id}`} className="cropblock">
      <div className="top">
        <h3><CropName name={c.crop_name} local={c.crop_local} /></h3>
        <span className="small muted">{num(c.area_acres, 2)} acres{c.field_name ? `, ${c.field_name}` : ''}. Harvest around {dateLabel(p.expected_harvest)}</span>
      </div>
      <SeasonRibbon progress={p} />
      {c.alerts?.length > 0 && <div style={{ marginTop: 14 }}><Alerts alerts={c.alerts.slice(0, 2)} /></div>}
      {c.water && c.water.irrigation_mm > 0 && (
        <div style={{ marginTop: 12 }}><Notice kind="info"><Droplets size={16} style={{ display: 'inline', verticalAlign: '-3px' }} /> This week the crop needs about <b>{c.water.irrigation_mm} mm</b> more water than the forecast rain gives (about {num(c.water.litres_per_acre)} litres per acre).</Notice></div>
      )}
      {c.next_tasks?.length > 0 && (
        <ul className="tasklist">
          {c.next_tasks.map((t) => {
            const d = t.due_day - p.day
            return <li key={t.id} className={d < 0 ? 'overdue' : ''}><span aria-hidden="true">○</span>{t.title}<span className="when">{d < 0 ? `due ${inDays(d)}` : inDays(d)}</span></li>
          })}
        </ul>
      )}
    </Link>
  )
}
