import { SPARK_MONTHS } from './config.js'
import { recordFor } from './api.js'
import {
  bandWords,
  beyondWords,
  comparisonNote,
  deviationText,
  edgeWords,
  fmtNum,
  intervalPct,
  likelyText,
  monthLabel,
  numberWord,
  outcomeKey,
  referenceLevel,
  wholePercents,
} from './format.js'
import { colourFor, fillFor } from './scale.js'
import Sparkline from './Sparkline.jsx'
import { Swatch } from './Swatch.jsx'

const NO_REFERENCE = 'No comparison level yet: an area needs 12 months of history first.'
const capitalise = (s) => s.charAt(0).toUpperCase() + s.slice(1)

/** The dot colour for the sparklines: the area's place on the scale, or none (hatch and "no reference"). */
const dotFill = (rec) => (rec?.kind === 'value' ? fillFor(rec) : null)

/** Uncertainty range as a horizontal bar: the band, the forecast point and the 12-month baseline tick. */
function RangeBar({ low, high, value, baseline }) {
  const lo = Math.min(low, baseline ?? low)
  const hi = Math.max(high, baseline ?? high)
  const pad = (hi - lo) * 0.12 || 1
  const min = Math.max(0, lo - pad)
  const max = hi + pad
  const pos = (v) => `${(((v - min) / (max - min)) * 100).toFixed(2)}%`
  return (
    <figure className="range">
      <div className="range__track" aria-hidden="true">
        <span className="range__band" style={{ left: pos(low), width: `calc(${pos(high)} - ${pos(low)})` }} />
        {baseline != null && <span className="range__tick" style={{ left: pos(baseline) }} />}
        <span className="range__point" style={{ left: pos(value) }} />
      </div>
      <figcaption className="range__caption">
        <span>
          Uncertainty range {fmtNum(low)} to {fmtNum(high)}
        </span>
        {baseline != null && <span className="range__key">12-month average {fmtNum(baseline)}</span>}
      </figcaption>
    </figure>
  )
}

// Segments of the probability bar, left to right like the legend: below (teal), within (neutral), above (amber).
const SEGMENTS = [
  { key: 'below', v: -1 },
  { key: 'within', v: 0 },
  { key: 'above', v: 1 },
]
const MIN_LABEL_PCT = 12 // a segment narrower than this shows no number inside (the sentence below has it)

/**
 * The three chances for the forecast month as one stacked bar, a key, and the sentence that carries the numbers:
 * "56% chance that October 2026 ends more than 10% above its October 2025 level, 19% chance more than 10% below,
 * 25% chance within 10% of it."
 */
function Chances({ rec, meta }) {
  const pct = wholePercents(rec.probs)
  const month = meta.forecast_month
  const band = bandWords(meta)
  const edge = edgeWords(meta)
  // Key names: "More than 10% below", "Within 10%", "More than 10% above".
  const names = { below: capitalise(edge.below), within: capitalise(band.replace(/ of$/, '')), above: capitalise(edge.above) }
  return (
    <section className="chances">
      <h3 className="detail__h3 chances__title">
        Chance of ending {beyondWords(meta)} {referenceLevel(meta, month)}
      </h3>
      <div className="chances__bar" aria-hidden="true">
        {SEGMENTS.map((s) =>
          pct[s.key] > 0 ? (
            <span
              key={s.key}
              className="chances__seg"
              style={{ flexGrow: pct[s.key], background: colourFor(s.v) }}
            >
              {pct[s.key] >= MIN_LABEL_PCT ? `${pct[s.key]}%` : ''}
            </span>
          ) : null,
        )}
      </div>
      <ul className="chances__key" aria-hidden="true">
        {SEGMENTS.map((s) => (
          <li key={s.key}>
            <Swatch fill={colourFor(s.v)} />
            {names[s.key]}
          </li>
        ))}
      </ul>
      <p className="detail__text chances__text">
        {pct.above}% chance that {monthLabel(month)} ends {edge.above} {referenceLevel(meta, month)}, {pct.below}%
        chance {edge.below}, {pct.within}% chance {band} it.
      </p>
      {rec.likely && (
        <p className="chances__likely">
          Most likely: {likelyText(rec.likely, meta, month)} ({pct[outcomeKey(rec.likely)]}%)
        </p>
      )}
    </section>
  )
}

function HistoricalDetail({ data, name, month, rec }) {
  const { meta } = data
  return (
    <>
      <dl className="figures">
        <div className="figure">
          <dt>Severity-weighted activity</dt>
          <dd>{fmtNum(rec.weighted_index)}</dd>
        </div>
        <div className="figure">
          <dt>Reported incidents</dt>
          <dd>{fmtNum(rec.incident_count)}</dd>
        </div>
      </dl>
      {rec.kind === 'insufficient_data' && (
        <p className="detail__text">Too few reported incidents here to compare one month with another.</p>
      )}
      {rec.kind === 'none' && <p className="detail__text">{NO_REFERENCE}</p>}
      {rec.kind === 'value' && (
        <>
          <p className="detail__text">{deviationText(rec.pct_vs_typical, meta, month)}.</p>
          <p className="detail__note">{comparisonNote(meta)}</p>
        </>
      )}
      <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months</h3>
      <Sparkline series={data.seriesByArea.get(name)} month={month} fill={dotFill(rec)} />
    </>
  )
}

function ForecastDetail({ data, name, rec }) {
  const { meta } = data
  const horizon = rec.horizon_months ?? meta.horizon_months
  const series = data.seriesByArea.get(name)
  if (rec.kind === 'insufficient_data') {
    return (
      <>
        <p className="detail__text">
          Too few reported incidents here to forecast meaningfully, so this area has no forecast number.
        </p>
        <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months</h3>
        <Sparkline series={series} month={meta.data_through} fill={null} />
      </>
    )
  }
  return (
    <>
      <div className="forecast">
        <p className="forecast__label">Severity-weighted activity, forecast</p>
        <p className="forecast__value">{fmtNum(rec.forecast_weighted_index)}</p>
        <p className="forecast__count">About {fmtNum(rec.forecast_incident_count)} reported incidents</p>
      </div>
      <RangeBar
        low={rec.interval_low}
        high={rec.interval_high}
        value={rec.forecast_weighted_index}
        baseline={rec.baseline_weighted_index}
      />
      {rec.probs ? (
        <Chances rec={rec} meta={meta} />
      ) : rec.kind === 'value' && rec.pct_vs_typical != null ? (
        // An older forecast file without chances: the forecast's own deviation instead.
        <p className="detail__text">
          The forecast is {deviationText(rec.pct_vs_typical, meta, meta.forecast_month).replace(/^A/, 'a')}.
        </p>
      ) : (
        <p className="detail__text">{NO_REFERENCE}</p>
      )}
      <p className="detail__note">
        {comparisonNote(meta)} The chances come from how far past forecasts landed from what happened. The
        12-month average is the simple baseline the forecast is tested against. The range covers{' '}
        {intervalPct(meta)}% of likely outcomes.
      </p>
      <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months and forecast</h3>
      <Sparkline
        series={series}
        month={meta.data_through}
        fill={dotFill(rec)}
        forecast={{
          month: rec.month,
          value: rec.forecast_weighted_index,
          low: rec.interval_low,
          high: rec.interval_high,
          horizon,
        }}
      />
      <p className="detail__note">
        Forecast made with data through {monthLabel(rec.data_through ?? meta.data_through)}, {numberWord(horizon)}{' '}
        {horizon === 1 ? 'month' : 'months'} ahead.
      </p>
    </>
  )
}

export default function AreaDetail({ data, mode, month, name }) {
  const rec = recordFor(data, mode, month, name)
  return (
    <article className="detail">
      <header className="detail__head">
        <h2 className="detail__name">{name}</h2>
        <p className="detail__month">
          {mode === 'forecast' ? `Forecast for ${monthLabel(data.meta.forecast_month)}` : monthLabel(month)}
        </p>
      </header>
      {!rec && <p className="detail__text">No data for this month.</p>}
      {rec && mode === 'historical' && <HistoricalDetail data={data} name={name} month={month} rec={rec} />}
      {rec && mode === 'forecast' && <ForecastDetail data={data} name={name} rec={rec} />}
    </article>
  )
}
