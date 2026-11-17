const inr = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export const rupees = (n) => (n === null || n === undefined || Number.isNaN(n) ? '—'
  : n < 0 ? `−₹${inr.format(Math.round(-n))}` : `₹${inr.format(Math.round(n))}`)
export const num = (n, digits = 0) =>
  n === null || n === undefined ? '—' : new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(n)

export function signed(n, suffix = '%') {
  if (n === null || n === undefined) return '—'
  return `${n > 0 ? '+' : ''}${num(n, 1)}${suffix}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
export function monthLabel(ym, withYear = true) {
  if (!ym) return ''
  const [y, m] = ym.split('-').map(Number)
  return withYear ? `${MONTHS[m - 1]} ${y}` : MONTHS[m - 1]
}

export function dateLabel(iso, opts = { day: 'numeric', month: 'short' }) {
  if (!iso) return ''
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return d.toLocaleDateString('en-IN', opts)
}

export function weekday(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short' })
}

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`
  return dateLabel(iso, { day: 'numeric', month: 'short', year: 'numeric' })
}

export const todayISO = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function inDays(n) {
  if (n === 0) return 'today'
  if (n === 1) return 'tomorrow'
  if (n === -1) return 'yesterday'
  return n > 0 ? `in ${n} days` : `${-n} days ago`
}
