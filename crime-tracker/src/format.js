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

/** "An area's usual level is worked out from the same time of year in the previous 12 complete months." */
export function usualLevelNote(meta) {
  const w = meta.tier_window_months
  return seasonal(meta)
    ? `An area’s usual level is worked out from the same time of year in the previous ${w} complete months.`
    : `An area’s usual level is its average over the previous ${w} complete months.`
}

/** "its usual level for the time of year" (seasonal) or "its 12-month average". */
const usualRef = (meta) =>
  seasonal(meta) ? 'its usual level for the time of year' : `its ${meta.tier_window_months}-month average`

/** "15% above its usual level for the time of year" from pct_vs_typical (a realised or forecast deviation). */
export function deviationText(pct, meta) {
  const shown = nf.format(Math.abs(Math.round(pct)))
  if (shown === '0') return `About the same as ${usualRef(meta)}`
  return `${shown}% ${pct > 0 ? 'above' : 'below'} ${usualRef(meta)}`
}

/** "15% above usual" for the hover card. */
export function deviationShort(pct) {
  const shown = nf.format(Math.abs(Math.round(pct)))
  return shown === '0' ? 'About usual' : `${shown}% ${pct > 0 ? 'above' : 'below'} usual`
}

/** The band around the usual level as two numbers: "10" and "10" for [-10, 10]. */
function bounds(meta) {
  const [lo, hi] = meta.tier_thresholds_pct
  return [nfUpTo1.format(Math.abs(lo)), nfUpTo1.format(hi)]
}

/** "within 10% of" or "between 5% below and 10% above": the band, before "it" / "its usual level". */
export function bandWords(meta) {
  const [lo, hi] = bounds(meta)
  return lo === hi ? `within ${hi}% of` : `between ${lo}% below and ${hi}% above`
}

/** "more than 10% higher" / "more than 10% lower": what "above" and "below" mean. */
export function edgeWords(meta) {
  const [lo, hi] = bounds(meta)
  return { above: `more than ${hi}% higher`, below: `more than ${lo}% lower` }
}

/** Whole percentages for {below, within, above} that add up to 100 (largest remainder). */
export function wholePercents(probs) {
  const keys = ['below', 'within', 'above']
  const raw = keys.map((k) => probs[k] * 100)
  const out = raw.map(Math.floor)
  let left = 100 - out.reduce((a, b) => a + b, 0)
  const order = raw.map((r, i) => [r - out[i], i]).sort((a, b) => b[0] - a[0])
  for (const [, i] of order) {
    if (left <= 0) break
    out[i] += 1
    left -= 1
  }
  return Object.fromEntries(keys.map((k, i) => [k, out[i]]))
}

/** The most likely outcome in words: "above its usual level", "within 10% of its usual level". */
export function likelyText(likely, meta) {
  if (likely === 'above_typical') return 'above its usual level'
  if (likely === 'below_typical') return 'below its usual level'
  return `${bandWords(meta)} its usual level`
}

/**
 * The largest of the three chances as a short label for the hover card: {label: "Above usual", pct: 72}.
 * Ties go to the most likely outcome in the file.
 */
export function topChance(probs, likely, meta) {
  const pct = wholePercents(probs)
  const pick = { above_typical: 'above', below_typical: 'below', typical: 'within' }[likely]
  const key = ['above', 'below', 'within'].reduce((a, b) => (pct[b] > pct[a] || (pct[b] === pct[a] && b === pick) ? b : a))
  const [lo, hi] = bounds(meta)
  const label = { above: 'Above usual', below: 'Below usual', within: lo === hi ? `Within ${hi}% of usual` : 'Near usual' }
  return { label: label[key], pct: pct[key] }
}

/** "0.171": a probability score (Brier, ranked probability score) with three decimals. */
export const fmtScore = (n) => n.toFixed(3)

/** "80" from an interval level of 0.8. */
export const intervalPct = (meta) => Math.round(meta.interval_level * 100)

/** "five" for an 80% range: roughly one month in five lands outside it. */
export const oneIn = (meta) => numberWord(Math.round(1 / (1 - meta.interval_level)))

/** "a Poisson regression (GLM)" from "poisson_glm". */
export const modelName = (meta) => MODEL_NAMES[meta.model] ?? `the ${meta.model.replace(/_/g, ' ')} model`
