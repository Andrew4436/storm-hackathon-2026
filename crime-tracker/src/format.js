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

/** "2025-10" from "2026-10": the same calendar month one year earlier. */
export function yearEarlier(key) {
  const [y, m] = key.split('-')
  return `${Number(y) - 1}-${m}`
}

/**
 * True when a month's comparison level is exactly the same calendar month one year earlier: a seasonal
 * reference (tier_reference "seasonal") over a 12-month window holds one month of each kind, so October 2026 is
 * compared with October 2025 and June 2024 with June 2023.
 */
export const sameMonthLastYear = (meta) => meta.tier_reference === 'seasonal' && meta.tier_window_months === 12

/**
 * The comparison level when it is not one named month, owned by `owner`: "its usual level for that time of year,
 * from the previous 24 complete months" (seasonal) or "its average over the previous 12 complete months".
 */
function genericReference(meta, owner = 'its') {
  const w = meta.tier_window_months
  return meta.tier_reference === 'seasonal'
    ? `${owner} usual level for that time of year, from the previous ${w} complete months`
    : `${owner} average over the previous ${w} complete months`
}

/**
 * What a month is compared with: "October 2025" for "2026-10" when the reference is the same month one year
 * earlier (sameMonthLastYear), otherwise the generic phrase. `short` gives "Oct 2025" (or "usual") for the hover
 * card; `owner` replaces "its" in the generic phrase ("this area’s").
 */
export function referenceLabel(meta, monthStr, { short = false, owner = 'its' } = {}) {
  if (sameMonthLastYear(meta)) return monthLabel(yearEarlier(monthStr), short)
  return short ? 'usual' : genericReference(meta, owner)
}

/** The comparison level as a noun phrase: "its October 2025 level", "this area’s October 2025 level". */
export function referenceLevel(meta, monthStr, owner = 'its') {
  return sameMonthLastYear(meta) ? `${owner} ${referenceLabel(meta, monthStr)} level` : genericReference(meta, owner)
}

/** "The comparison level is this area’s severity-weighted activity in the same month one year earlier." */
export function comparisonNote(meta, owner = 'this area’s') {
  return sameMonthLastYear(meta)
    ? `The comparison level is ${owner} severity-weighted activity in the same month one year earlier.`
    : `The comparison level is ${genericReference(meta, owner)}.`
}

/** "15% above June 2023", or "About the same as June 2023" within 1%, from a deviation in percent. */
function deviation(pct, ref) {
  if (Math.abs(pct) < 1) return ref === 'usual' ? 'About usual' : `About the same as ${ref}`
  return `${nf.format(Math.abs(Math.round(pct)))}% ${pct > 0 ? 'above' : 'below'} ${ref}`
}

/** "15% above June 2023" from pct_vs_typical (a realised or forecast deviation) for the month monthStr. */
export const deviationText = (pct, meta, monthStr) => deviation(pct, referenceLabel(meta, monthStr))

/** "15% above Jun 2023" for the hover card. */
export const deviationShort = (pct, meta, monthStr) => deviation(pct, referenceLabel(meta, monthStr, { short: true }))

/**
 * The band around the comparison level in percent: 10 for tier_thresholds_pct [-10, 10]. `side` 'below' gives
 * the lower edge, as a positive number.
 */
export function bandPct(meta, side = 'above') {
  const [lo, hi] = meta.tier_thresholds_pct
  return side === 'below' ? Math.abs(lo) : hi
}

/** The two edges of the band as text: ["10", "10"] for [-10, 10]. */
const bounds = (meta) => [nfUpTo1.format(bandPct(meta, 'below')), nfUpTo1.format(bandPct(meta))]

/** "within 10% of" or "between 5% below and 10% above": the band, before "it" or a reference. */
export function bandWords(meta) {
  const [lo, hi] = bounds(meta)
  return lo === hi ? `within ${hi}% of` : `between ${lo}% below and ${hi}% above`
}

/** "more than 10% above" / "more than 10% below": what the outcomes "above" and "below" mean. */
export function edgeWords(meta) {
  const [lo, hi] = bounds(meta)
  return { above: `more than ${hi}% above`, below: `more than ${lo}% below` }
}

/** "more than 10% above or below" (or "more than 10% above or 5% below"), before a reference. */
export function beyondWords(meta) {
  const [lo, hi] = bounds(meta)
  return lo === hi ? `more than ${hi}% above or below` : `more than ${hi}% above or ${lo}% below`
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

const OUTCOME_KEYS = { above_typical: 'above', below_typical: 'below', typical: 'within' }

/** 'above', 'below' or 'within' from most_likely ('above_typical', 'below_typical', 'typical'). */
export const outcomeKey = (likely) => OUTCOME_KEYS[likely]

/** The most likely outcome in words: "more than 10% above October 2025", "within 10% of October 2025". */
export function likelyText(likely, meta, monthStr) {
  const key = outcomeKey(likely)
  const ref = referenceLabel(meta, monthStr)
  return key === 'within' ? `${bandWords(meta)} ${ref}` : `${edgeWords(meta)[key]} ${ref}`
}

/**
 * The largest of the three chances as one short line for the hover card: "56% chance above Oct 2025 level",
 * "40% chance within 10% of Oct 2025 level". Ties go to the most likely outcome in the file.
 */
export function chanceShort(probs, likely, meta, monthStr) {
  const pct = wholePercents(probs)
  const pick = outcomeKey(likely)
  const key = ['above', 'below', 'within'].reduce((a, b) => (pct[b] > pct[a] || (pct[b] === pct[a] && b === pick) ? b : a))
  const ref = `${referenceLabel(meta, monthStr, { short: true })} level`
  return `${pct[key]}% chance ${key === 'within' ? bandWords(meta) : key} ${ref}`
}

/** "0.171": a probability score (Brier, ranked probability score) with three decimals. */
export const fmtScore = (n) => n.toFixed(3)

/** "80" from an interval level of 0.8. */
export const intervalPct = (meta) => Math.round(meta.interval_level * 100)

/** "five" for an 80% range: roughly one month in five lands outside it. */
export const oneIn = (meta) => numberWord(Math.round(1 / (1 - meta.interval_level)))

/** "a Poisson regression (GLM)" from "poisson_glm". */
export const modelName = (meta) => MODEL_NAMES[meta.model] ?? `the ${meta.model.replace(/_/g, ' ')} model`
