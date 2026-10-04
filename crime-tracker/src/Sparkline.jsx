import { SPARK_MONTHS } from './config.js'
import { fmtNum, monthLabel } from './format.js'

const W = 320
const H = 88
const PAD = { l: 4, r: 8, t: 8, b: 6 }

/**
 * Severity-weighted activity over a 36-month window.
 * Historical: the window ends at (or, early in the record, contains) the selected month, which is marked.
 * Forecast: the last 36 complete months, then the forecast point with its uncertainty range, `forecast.horizon`
 * months after the last one.
 * `fill` colours the marked dot with the area's place on the map's colour scale; null leaves it plain.
 */
export default function Sparkline({ series, month, forecast, fill }) {
  if (!series?.length) return null
  const idx = forecast ? series.length - 1 : series.findIndex((r) => r.month === month)
  if (idx < 0) return null
  const start = Math.max(0, Math.min(idx - SPARK_MONTHS + 1, series.length - SPARK_MONTHS))
  const pts = series.slice(start, start + SPARK_MONTHS)
  const markIdx = idx - start

  const slots = pts.length - 1 + (forecast ? forecast.horizon : 0)
  const max = Math.max(...pts.map((p) => p.weighted_index), forecast?.high ?? 0, 1)
  const x = (i) => PAD.l + (slots ? (i * (W - PAD.l - PAD.r)) / slots : 0)
  const y = (v) => H - PAD.b - (v / max) * (H - PAD.t - PAD.b)

  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.weighted_index).toFixed(1)}`).join('')
  const mark = pts[markIdx]
  const fx = x(slots)
  const first = pts[0].month
  const last = forecast ? forecast.month : pts[pts.length - 1].month
  const label = forecast
    ? `Severity-weighted activity from ${monthLabel(first)} to ${monthLabel(pts[pts.length - 1].month)}, then the forecast for ${monthLabel(forecast.month)}: ${fmtNum(forecast.value)}, range ${fmtNum(forecast.low)} to ${fmtNum(forecast.high)}.`
    : `Severity-weighted activity from ${monthLabel(first)} to ${monthLabel(pts[pts.length - 1].month)}. ${monthLabel(mark.month)}: ${fmtNum(mark.weighted_index)}.`

  return (
    <figure className="spark">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="spark__svg">
        <line x1={PAD.l} x2={W - PAD.r} y1={H - PAD.b} y2={H - PAD.b} className="spark__axis" />
        <path d={line} className="spark__line" />
        {forecast ? (
          <g className="spark__forecast">
            <rect
              x={fx - 5}
              width={10}
              y={y(forecast.high)}
              height={Math.max(1, y(forecast.low) - y(forecast.high))}
              rx={2}
              className="spark__band"
            />
            <line x1={x(pts.length - 1)} y1={y(mark.weighted_index)} x2={fx} y2={y(forecast.value)} strokeDasharray="3 3" />
            <circle
              cx={fx}
              cy={y(forecast.value)}
              r="4"
              className="spark__dot"
              style={fill ? { fill } : undefined}
            />
          </g>
        ) : (
          <g>
            <line x1={x(markIdx)} x2={x(markIdx)} y1={PAD.t} y2={H - PAD.b} className="spark__guide" />
            <circle
              cx={x(markIdx)}
              cy={y(mark.weighted_index)}
              r="4"
              className="spark__dot"
              style={fill ? { fill } : undefined}
            />
          </g>
        )}
      </svg>
      <figcaption className="spark__caption">
        <span>{monthLabel(first, true)}</span>
        <span>{forecast ? `Forecast ${monthLabel(last, true)}` : monthLabel(last, true)}</span>
      </figcaption>
    </figure>
  )
}
