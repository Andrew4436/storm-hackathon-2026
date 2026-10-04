import { TIER_WINDOW_MONTHS } from './config.js'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const nf = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 })

export const fmtNum = (n) => (n == null || Number.isNaN(n) ? '–' : nf.format(n))

export function monthLabel(key, short = false) {
  const [y, m] = key.split('-').map(Number)
  const name = MONTHS[m - 1]
  return `${short ? name.slice(0, 3) : name} ${y}`
}

/** "25 September 2026" from "2026-09-25". */
export function dayLabel(key) {
  const [y, m, d] = key.split('-').map(Number)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

const TYPICAL = `this area's typical level (${TIER_WINDOW_MONTHS}-month average)`

/** "12% above this area's typical level (36-month average)" from pct_vs_typical. */
export function pctText(pct) {
  const r = Math.round(pct)
  if (r === 0) return `About the same as ${TYPICAL}`
  return `${Math.abs(r)}% ${r > 0 ? 'above' : 'below'} ${TYPICAL}`
}

const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']

/** Small whole numbers in words ("two months ahead"), larger ones as digits. */
export const numberWord = (n) => WORDS[n] ?? fmtNum(n)
