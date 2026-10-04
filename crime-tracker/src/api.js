import { DATA_THROUGH } from './config.js'
import { AREAS } from './areas.js'

// With VITE_API_URL set, read from the backend; otherwise read the static files in public/data/.
const API = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const STATIC = `${import.meta.env.BASE_URL}data`

export const SOURCES = API
  ? { history: `${API}/history`, forecast: `${API}/forecast`, boundaries: `${API}/boundaries` }
  : {
      history: `${STATIC}/history.json`,
      forecast: `${STATIC}/forecast_2026-10.json`,
      boundaries: `${STATIC}/local-area-boundary.geojson`,
    }

async function getJson(url, signal) {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`${url} returned HTTP ${res.status}.`)
  try {
    return await res.json()
  } catch {
    // A static host may answer a missing file with its HTML index page.
    throw new Error(`${url} did not return valid JSON (is the file missing?).`)
  }
}

/** Normalise a tier: '' and null (first 12 months of an area, partial month) become 'none'. */
const tierOf = (t) => (t ? t : 'none')

export async function loadData(signal) {
  const [history, forecast, boundaries] = await Promise.all([
    getJson(SOURCES.history, signal),
    getJson(SOURCES.forecast, signal),
    getJson(SOURCES.boundaries, signal),
  ])
  if (!Array.isArray(history) || !Array.isArray(forecast) || !Array.isArray(boundaries?.features)) {
    throw new Error('Unexpected data format')
  }

  const byKey = new Map()
  const seriesByArea = new Map()
  const monthSet = new Set()
  for (const r of history) {
    const row = { ...r, tier: tierOf(r.relative_activity_tier) }
    byKey.set(`${r.neighbourhood}|${r.month}`, row)
    // The partial month (is_partial = 1, 2026-09) is never shown as a complete month.
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
