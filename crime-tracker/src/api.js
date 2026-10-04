import { DATA_THROUGH, FORECAST_MONTH } from './config.js'
import { AREAS } from './areas.js'

// With VITE_API_URL set, read from the backend; otherwise read the static files in public/data/.
const API = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const STATIC = `${import.meta.env.BASE_URL}data`

export const SOURCES = API
  ? { history: `${API}/history`, forecast: `${API}/forecast`, boundaries: `${API}/boundaries` }
  : {
      history: `${STATIC}/history.json`,
      forecast: `${STATIC}/forecast_${FORECAST_MONTH}.json`,
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

/** Normalise a tier: '' and null (first 12 months of an area, partial month) become 'none'. */
const tierOf = (t) => (t ? t : 'none')

export async function loadData(signal) {
  const [history, forecast, boundaries] = await Promise.all([
    getJson(SOURCES.history, signal, 'history file'),
    getJson(SOURCES.forecast, signal, 'forecast file'),
    getJson(SOURCES.boundaries, signal, 'neighbourhood boundary file'),
  ])
  if (!Array.isArray(history) || !Array.isArray(forecast) || !Array.isArray(boundaries?.features)) {
    throw loadError('data', 'One of the data files has an unexpected format.')
  }

  const byKey = new Map()
  const seriesByArea = new Map()
  const monthSet = new Set()
  for (const r of history) {
    const row = { ...r, tier: tierOf(r.relative_activity_tier) }
    byKey.set(`${r.neighbourhood}|${r.month}`, row)
    // The partial month (is_partial = 1, PARTIAL_MONTH in config) is never shown as a complete month.
    if (r.is_partial === 1 || r.month > DATA_THROUGH) continue
    monthSet.add(r.month)
    if (!seriesByArea.has(r.neighbourhood)) seriesByArea.set(r.neighbourhood, [])
    seriesByArea.get(r.neighbourhood).push(row)
  }
  for (const s of seriesByArea.values()) s.sort((a, b) => (a.month < b.month ? -1 : 1))

  const forecastByArea = new Map(
    forecast.map((f) => [f.neighbourhood, { ...f, tier: tierOf(f.relative_activity_tier) }]),
  )

  return {
    months: [...monthSet].sort(),
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
