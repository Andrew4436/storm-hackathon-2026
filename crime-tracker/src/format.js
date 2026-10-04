import { MODEL_NAMES } from './config.js'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

const nf = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 0 })
const nf1 = new Intl.NumberFormat('en-CA', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const nfUpTo1 = new Intl.NumberFormat('en-CA', { maximumFractionDigits: 1 })

export const fmtNum = (n) => (n == null || Number.isNaN(n) ? '–' : nf.format(n))

/** "12.9%": a percentage with one decimal, for the evaluation figures. */
export const fmtPct1 = (n) => `${nf1.format(n)}%`

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

const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve']

/** Small whole numbers in words ("two months ahead"), larger ones as digits. */
export const numberWord = (n) => WORDS[n] ?? fmtNum(n)

/* ---------- Wording built from meta.json (see META_DEFAULTS in config.js) ---------- */

const seasonal = (meta) => meta.tier_reference === 'seasonal'

/** What an area's typical level is: "the area's average over the previous 36 complete months". */
export function typicalLevelText(meta) {
  const w = meta.tier_window_months
  return seasonal(meta)
    ? `the area’s usual level for that time of year, worked out from the previous ${w} complete months`
    : `the area’s average over the previous ${w} complete months`
}

/**
 * "12% above this area's typical level (36-month average)" from pct_vs_typical. Within a point of a tier
 * threshold it keeps one decimal ("5.3% above"), so the figure never contradicts the colour.
 */
export function pctText(pct, meta) {
  const w = meta.tier_window_months
  const typical = seasonal(meta)
    ? `this area’s typical level for the time of year (last ${w} months)`
    : `this area’s typical level (${w}-month average)`
  const [lo, hi] = meta.tier_thresholds_pct
  const nearEdge = Math.abs(Math.abs(pct) - (pct < 0 ? -lo : hi)) < 1
  const shown = nearEdge ? nfUpTo1.format(Math.abs(pct)) : nf.format(Math.abs(Math.round(pct)))
  if (shown === '0') return `About the same as ${typical}`
  return `${shown}% ${pct > 0 ? 'above' : 'below'} ${typical}`
}

/** The tier thresholds as two numbers, "5" and "5" for [-5, 5]. */
function bounds(meta) {
  const [lo, hi] = meta.tier_thresholds_pct
  return [nfUpTo1.format(Math.abs(lo)), nfUpTo1.format(hi)]
}

/** "Typical means within 5% of that level." */
export function bandText(meta) {
  const [lo, hi] = bounds(meta)
  return lo === hi
    ? `Typical means within ${hi}% of that level.`
    : `Typical means from ${lo}% below to ${hi}% above that level.`
}

/** "Within 5% of it is typical; more than 5% lower is below typical; more than 5% higher is above typical." */
export function thresholdText(meta) {
  const [lo, hi] = bounds(meta)
  const typical = lo === hi ? `Within ${hi}% of it is typical` : `From ${lo}% lower to ${hi}% higher is typical`
  return `${typical}; more than ${lo}% lower is below typical; more than ${hi}% higher is above typical.`
}

/** "80" from an interval level of 0.8. */
export const intervalPct = (meta) => Math.round(meta.interval_level * 100)

/** "five" for an 80% range: roughly one month in five lands outside it. */
export const oneIn = (meta) => numberWord(Math.round(1 / (1 - meta.interval_level)))

/** "a Poisson regression (GLM)" from "poisson_glm". */
export const modelName = (meta) => MODEL_NAMES[meta.model] ?? `the ${meta.model.replace(/_/g, ' ')} model`
