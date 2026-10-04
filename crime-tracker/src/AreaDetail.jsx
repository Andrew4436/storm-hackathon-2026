import { SPARK_MONTHS } from './config.js'
import { recordFor } from './api.js'
import { bandText, fmtNum, intervalPct, monthLabel, numberWord, pctText, typicalLevelText } from './format.js'
import Sparkline from './Sparkline.jsx'
import { TierChip } from './Swatch.jsx'

/** "12% above this area's typical level (36-month average). Typical means within 5% of that level." */
function compareText(rec, meta) {
  if (rec.tier === 'insufficient_data') return null
  if (rec.tier === 'none') return 'Comparisons start once an area has 12 months of history.'
  if (rec.pct_vs_typical == null) return null
  return `${pctText(rec.pct_vs_typical, meta)}. ${bandText(meta)}`
}

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

function HistoricalDetail({ data, name, month, rec }) {
  const cmp = compareText(rec, data.meta)
  const insufficient = rec.tier === 'insufficient_data'
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
      {insufficient && <p className="detail__text">Too few reported incidents here to compare one month with another.</p>}
      {cmp && <p className="detail__text">{cmp}</p>}
      <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months</h3>
      <Sparkline series={data.seriesByArea.get(name)} month={month} tier={rec.tier} />
    </>
  )
}

function ForecastDetail({ data, name, rec }) {
  const { meta } = data
  const insufficient = rec.tier === 'insufficient_data'
  const cmp = compareText(rec, meta)
  const horizon = rec.horizon_months ?? meta.horizon_months
  const series = data.seriesByArea.get(name)
  if (insufficient) {
    return (
      <>
        <p className="detail__text">
          Too few reported incidents here to forecast meaningfully, so this area has no forecast number.
        </p>
        <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months</h3>
        <Sparkline series={series} month={meta.data_through} tier={rec.tier} />
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
      {cmp && <p className="detail__text">{cmp}</p>}
      <p className="detail__note">
        The typical level is {typicalLevelText(meta)}. The 12-month average is the simple baseline the forecast is
        tested against. The range covers {intervalPct(meta)}% of likely outcomes.
      </p>
      <h3 className="detail__h3">Severity-weighted activity, {SPARK_MONTHS} months and forecast</h3>
      <Sparkline
        series={series}
        month={meta.data_through}
        tier={rec.tier}
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
  const tier = rec?.tier ?? 'none'
  return (
    <article className="detail">
      <header className="detail__head">
        <h2 className="detail__name">{name}</h2>
        <p className="detail__month">
          {mode === 'forecast' ? `Forecast for ${monthLabel(data.meta.forecast_month)}` : monthLabel(month)}
        </p>
        <TierChip tier={tier} />
      </header>
      {!rec && <p className="detail__text">No data for this month.</p>}
      {rec && mode === 'historical' && <HistoricalDetail data={data} name={name} month={month} rec={rec} />}
      {rec && mode === 'forecast' && <ForecastDetail data={data} name={name} rec={rec} />}
    </article>
  )
}
