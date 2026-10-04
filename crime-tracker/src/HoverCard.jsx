import { useLayoutEffect, useRef } from 'react'
import { MINI_SPARK_MONTHS } from './config.js'
import { recordFor } from './api.js'
import { fmtNum } from './format.js'
import { TierChip } from './Swatch.jsx'

const OFFSET = 14
const W = 250
const H = 40

/** Last 12 months of severity-weighted activity; in forecast mode, then the forecast point. */
function MiniSpark({ series, month, forecast }) {
  const end = series.findIndex((r) => r.month === month)
  if (end < 0) return null
  const pts = series.slice(Math.max(0, end - MINI_SPARK_MONTHS + 1), end + 1)
  if (pts.length < 2) return null
  const slots = pts.length - 1 + (forecast ? forecast.horizon : 0)
  const max = Math.max(...pts.map((p) => p.weighted_index), forecast?.high ?? 0, 1)
  const x = (i) => 2 + (i * (W - 6)) / slots
  const y = (v) => H - 3 - (v / max) * (H - 6)
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.weighted_index).toFixed(1)}`).join('')
  const lx = x(pts.length - 1)
  const ly = y(pts[pts.length - 1].weighted_index)
  return (
    <svg className="mini" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <path d={d} className="mini__line" />
      {forecast ? (
        <>
          <line x1={x(slots)} x2={x(slots)} y1={y(forecast.low)} y2={y(forecast.high)} className="mini__range" />
          <line x1={lx} y1={ly} x2={x(slots)} y2={y(forecast.value)} className="mini__dash" />
          <circle cx={x(slots)} cy={y(forecast.value)} r="2.5" className="mini__dot" />
        </>
      ) : (
        <circle cx={lx} cy={ly} r="2.5" className="mini__dot" />
      )}
    </svg>
  )
}

function Figures({ rec, mode }) {
  if (!rec) return <p className="hover-card__figs">No data for this month</p>
  if (mode === 'forecast') {
    if (rec.tier === 'insufficient_data') return <p className="hover-card__figs">Too few incidents to forecast</p>
    return (
      <p className="hover-card__figs">
        <span>Forecast {fmtNum(rec.forecast_weighted_index)}</span>
        <span>About {fmtNum(rec.forecast_incident_count)} reported incidents</span>
      </p>
    )
  }
  return (
    <p className="hover-card__figs">
      <span>Activity {fmtNum(rec.weighted_index)}</span>
      <span>Reported incidents {fmtNum(rec.incident_count)}</span>
    </p>
  )
}

/**
 * The single hover card. It is rendered from React state only (no Leaflet tooltips), so there is never more
 * than one, and it disappears the moment that state is cleared.
 */
export default function HoverCard({ hover, data, mode, month, rightInset = 0 }) {
  const ref = useRef(null)

  // Place the card at the cursor + 14px, flipped to stay inside the visible map. Measured before paint.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || !hover) return
    const w = el.offsetWidth
    const h = el.offsetHeight
    const flipX = hover.x + OFFSET + w > hover.w - rightInset - 8
    const flipY = hover.y + OFFSET + h > hover.h - 8
    const left = flipX ? Math.max(8, hover.x - OFFSET - w) : hover.x + OFFSET
    const top = flipY ? Math.max(8, hover.y - OFFSET - h) : hover.y + OFFSET
    el.style.transform = `translate(${Math.round(left)}px, ${Math.round(top)}px)`
  })

  if (!hover) return null
  const { name } = hover
  const rec = recordFor(data, mode, month, name)
  const series = data.seriesByArea.get(name) ?? []
  const forecast =
    mode === 'forecast' && rec && rec.tier !== 'insufficient_data'
      ? {
          value: rec.forecast_weighted_index,
          low: rec.interval_low,
          high: rec.interval_high,
          horizon: rec.horizon_months ?? data.meta.horizon_months,
        }
      : null

  return (
    <div className="hover-card" ref={ref} aria-hidden="true">
      <p className="hover-card__name">{name}</p>
      <TierChip tier={rec?.tier ?? 'none'} />
      <Figures rec={rec} mode={mode} />
      <MiniSpark series={series} month={mode === 'forecast' ? data.meta.data_through : month} forecast={forecast} />
    </div>
  )
}
