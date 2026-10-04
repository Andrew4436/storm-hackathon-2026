import { META_DEFAULTS, SLIDER_START } from './config.js'
import { AREAS } from './areas.js'
import { forecastShade, historyShade } from './scale.js'

// With VITE_API_URL set, read from the backend; otherwise read the static files in public/data/.
const API = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
// BASE_URL is '/' locally and '/storm-hackathon-2026/' on GitHub Pages (vite.config.js); it ends with one slash.
const STATIC = `${import.meta.env.BASE_URL.replace(/\/*$/, '/')}data`

/** Where each file comes from. The static forecast file is named after meta.json's forecast_month. */
export const SOURCES = API
  ? {
      meta: `${API}/meta`,
      history: `${API}/history`,
      forecast: () => `${API}/forecast`,
      boundaries: `${API}/boundaries`,
    }
  : {
      meta: `${STATIC}/meta.json`,
      history: `${STATIC}/history.json`,
      forecast: (month) => `${STATIC}/forecast_${month}.json`,
      boundaries: `${STATIC}/local-area-boundary.geojson`,
    }

/** An error with a plain-language summary (what failed) next to the technical detail. */
function loadError(what, detail) {
  const err = new Error(detail)
  err.summary = `The ${what} could not be loaded.`
  return err
}

async function getJson(url, signal, what) {
  let res
  try {
    res = await fetch(url, { signal })
  } catch (e) {
    if (signal?.aborted) throw e
    throw loadError(what, `${url}: ${e.message}`)
  }
  if (!res.ok) throw loadError(what, `${url} returned HTTP ${res.status}.`)
  try {
    return await res.json()
  } catch {
    // A static host may answer a missing file with its HTML index page.
    throw loadError(what, `${url} did not return valid JSON (is the file missing?).`)
  }
}

/* ---------- meta.json: optional, checked field by field ---------- */

const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/
const isObject = (v) => v != null && typeof v === 'object' && !Array.isArray(v)
const finite = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const wholeIn = (lo, hi) => (v) => Number.isInteger(v) && v >= lo && v <= hi

const META_CHECKS = {
  model: (v) => typeof v === 'string' && v.trim() !== '',
  data_through: (v) => typeof v === 'string' && MONTH_RE.test(v),
  forecast_month: (v) => typeof v === 'string' && MONTH_RE.test(v),
  horizon_months: wholeIn(1, 24),
  tier_window_months: wholeIn(1, 240),
  tier_thresholds_pct: (v) =>
    Array.isArray(v) && v.length === 2 && v.every((x) => finite(x) != null) && v[0] <= 0 && v[1] >= 0 && v[0] < v[1],
  tier_reference: (v) => v === 'trailing_mean' || v === 'seasonal',
  interval_level: (v) => finite(v) != null && v > 0 && v < 1,
  tier_mode: (v) => typeof v === 'string' && v.trim() !== '',
  probability_method: (v) => typeof v === 'string' && v.trim() !== '',
}
const EVAL_NUMBERS = [
  'wape_pct',
  'improvement_vs_mean_12_pct',
  'improvement_vs_previous_pct',
  'interval_coverage_pct',
  'tier_accuracy_pct',
  'tier_majority_baseline_pct',
  'tier_macro_f1',
]
const PROB_NUMBERS = [
  'brier_above',
  'brier_below',
  'brier_above_baseline',
  'brier_below_baseline',
  'rps',
  'rps_baseline',
  'rps_hard_tier',
]
const text = (v) => (typeof v === 'string' && v.trim() !== '' ? v.trim() : null)

/** Reliability bins [{bin, predicted, observed, n}]; malformed entries are dropped. */
const reliability = (rows) =>
  (Array.isArray(rows) ? rows : [])
    .filter((r) => isObject(r) && typeof r.bin === 'string')
    .map((r) => ({ bin: r.bin, predicted: finite(r.predicted), observed: finite(r.observed), n: finite(r.n) ?? 0 }))

/** evaluation.probabilistic: how well the chances scored. Missing figures are null and their lines are left out. */
function normaliseProbabilistic(p) {
  if (!isObject(p)) return null
  const out = {}
  for (const k of PROB_NUMBERS) out[k] = finite(p[k])
  out.reliability_above = reliability(p.reliability_above)
  out.reliability_below = reliability(p.reliability_below)
  out.statement = text(p.statement)
  out.scored_on = text(p.scored_on)
  return out
}

/**
 * The file's evaluation block, or the defaults when it has none. The two are never mixed, so every figure in
 * "How well does it forecast?" comes from the same run; a figure the file lacks is left out.
 */
function normaliseEvaluation(e) {
  if (!isObject(e)) return META_DEFAULTS.evaluation
  const out = { folds: e.folds ?? null }
  for (const k of EVAL_NUMBERS) out[k] = finite(e[k])
  const mae = isObject(e.pooled_mae_weighted_index) ? e.pooled_mae_weighted_index : {}
  out.pooled_mae_weighted_index = {
    mean_12: finite(mae.mean_12),
    previous_glm: finite(mae.previous_glm),
    shipped: finite(mae.shipped),
  }
  const { mean_12: base, shipped } = out.pooled_mae_weighted_index
  if (out.improvement_vs_mean_12_pct == null && base > 0 && shipped != null) {
    out.improvement_vs_mean_12_pct = (1 - shipped / base) * 100
  }
  out.probabilistic = normaliseProbabilistic(e.probabilistic)
  return out
}

/** meta.json with every missing or invalid field replaced by its value in META_DEFAULTS. */
export function normaliseMeta(raw) {
  if (!isObject(raw)) return { ...META_DEFAULTS, source: 'defaults' }
  const meta = { ...META_DEFAULTS, source: 'file' }
  const ignored = []
  for (const [key, ok] of Object.entries(META_CHECKS)) {
    if (ok(raw[key])) meta[key] = raw[key]
    else ignored.push(key)
  }
  if (ignored.length) console.warn(`meta.json: using the defaults in src/config.js for ${ignored.join(', ')}.`)
  meta.evaluation = normaliseEvaluation(raw.evaluation)
  return meta
}

async function loadMeta(signal) {
  try {
    return normaliseMeta(await getJson(SOURCES.meta, signal, 'meta file'))
  } catch (e) {
    if (signal?.aborted) throw e
    console.warn(`${e.message} Using the defaults in src/config.js.`)
    return normaliseMeta(null)
  }
}

/**
 * Every record gains `kind` ('value', 'insufficient_data', or 'none' when there is no usual level to compare
 * with: an area's first 12 months, the partial month) and `v`, its position on the colour scale (src/scale.js).
 * Forecast records also gain `probs` ({below, within, above}, or null) and `likely` (the most likely outcome).
 * relative_activity_tier is read only to spot 'insufficient_data'.
 */
export async function loadData(signal) {
  // The forecast file is named after meta.forecast_month, so it waits for meta; the rest load in parallel.
  const metaReady = loadMeta(signal)
  const [meta, history, forecast, boundaries] = await Promise.all([
    metaReady,
    getJson(SOURCES.history, signal, 'history file'),
    metaReady.then((m) => getJson(SOURCES.forecast(m.forecast_month), signal, 'forecast file')),
    getJson(SOURCES.boundaries, signal, 'neighbourhood boundary file'),
  ])
  if (!Array.isArray(history) || !Array.isArray(forecast) || !Array.isArray(boundaries?.features)) {
    throw loadError('data', 'One of the data files has an unexpected format.')
  }

  const byKey = new Map()
  const seriesByArea = new Map()
  const monthSet = new Set()
  for (const r of history) {
    const row = { ...r, ...historyShade(r) }
    byKey.set(`${r.neighbourhood}|${r.month}`, row)
    // The partial month (is_partial = 1, PARTIAL_MONTH in config) is never shown as a complete month.
    if (r.is_partial === 1 || r.month > meta.data_through) continue
    monthSet.add(r.month)
    if (!seriesByArea.has(r.neighbourhood)) seriesByArea.set(r.neighbourhood, [])
    seriesByArea.get(r.neighbourhood).push(row)
  }
  for (const s of seriesByArea.values()) s.sort((a, b) => (a.month < b.month ? -1 : 1))

  const forecastByArea = new Map(forecast.map((f) => [f.neighbourhood, { ...f, ...forecastShade(f) }]))

  return {
    meta,
    months: [...monthSet].filter((m) => m >= SLIDER_START).sort(),
    areas: AREAS.map((a) => a.name),
    byKey,
    seriesByArea,
    forecastByArea,
    boundaries,
  }
}

/** The record shown for one area in the current view (forecast row or history row), or null. */
export function recordFor(data, mode, month, name) {
  if (mode === 'forecast') return data.forecastByArea.get(name) ?? null
  return data.byKey.get(`${name}|${month}`) ?? null
}
