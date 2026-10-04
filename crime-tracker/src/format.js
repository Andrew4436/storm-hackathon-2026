import { TIER_WINDOW_MONTHS } from './config.js'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const nf = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 })

export const fmtNum = (n) => (n == null || Number.isNaN(n) ? '–' : nf.format(n))

export function monthLabel(key, short = false) {
  const [y, m] = key.split('-').map(Number)
  const name = MONTHS[m - 1]
  return `${short ? name.slice(0, 3) : name} ${y}`
}

export function addMonths(key, n) {
  const [y, m] = key.split('-').map(Number)
  const t = y * 12 + (m - 1) + n
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
}

const TYPICAL = `this area's typical level (${TIER_WINDOW_MONTHS}-month average)`

/** "12% above this area's typical level (36-month average)" from pct_vs_typical. */
export function pctText(pct) {
  const r = Math.round(pct)
  if (r === 0) return `About the same as ${TYPICAL}`
  return `${Math.abs(r)}% ${r > 0 ? 'above' : 'below'} ${TYPICAL}`
}
