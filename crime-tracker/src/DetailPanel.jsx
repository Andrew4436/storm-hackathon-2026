import { AREAS } from './areas.js'
import { DATA_THROUGH, LEGEND_ORDER, TIER_WINDOW_MONTHS, TIERS } from './config.js'
import { recordFor } from './api.js'
import { fmtNum, monthLabel, pctText } from './format.js'
import Sparkline from './Sparkline.jsx'
import Swatch from './Swatch.jsx'

const SORTED = [...AREAS].sort((a, b) => a.name.localeCompare(b.name))

function compareText(rec) {
  if (rec.tier === 'insufficient_data') return 'Too few incidents to compare'
  if (rec.tier === 'none') return "Comparisons start once an area has 12 months of history"
  if (rec.pct_vs_typical == null) return null
  return pctText(rec.pct_vs_typical)
}

function TierLine({ tier }) {
  return (
    <p className="tier-line">
      <Swatch tier={tier} />
      <span>{(TIERS[tier] ?? TIERS.none).label}</span>
    </p>
  )
}

function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>
        {value}
        {sub && <span className="stat__sub">{sub}</span>}
      </dd>
    </div>
  )
}

function Summary({ data, mode, month }) {
  const counts = {}
  for (const a of AREAS) {
    const tier = recordFor(data, mode, month, a.name)?.tier ?? 'none'
    counts[tier] = (counts[tier] ?? 0) + 1
  }
  const rows = [...LEGEND_ORDER, 'none'].filter((t) => counts[t])
  return (
    <div className="summary">
      <p className="panel__prompt">Select a neighbourhood on the map, or choose one from the list above.</p>
      <h2 className="panel__h">
        {mode === 'forecast' ? 'Forecast for October 2026' : monthLabel(month)}: all 24 areas
      </h2>
      <ul className="summary__list">
        {rows.map((t) => (
          <li key={t}>
            <Swatch tier={t} />
            <span className="summary__label">{TIERS[t].label}</span>
            <span className="summary__count">
              {counts[t]} {counts[t] === 1 ? 'area' : 'areas'}
            </span>
          </li>
        ))}
      </ul>
      <p className="panel__note">
        Each area is compared with its own last three years, not with other areas, so a busy area can be
        &ldquo;below typical&rdquo; and a quiet one &ldquo;above typical&rdquo;.
      </p>
    </div>
  )
}

function HistoricalDetail({ data, name, month, rec }) {
  const cmp = compareText(rec)
  return (
    <>
      <TierLine tier={rec.tier} />
      <dl className="stats">
        <Stat label="Severity-weighted activity" value={fmtNum(rec.weighted_index)} />
        <Stat label="Reported incidents" value={fmtNum(rec.incident_count)} />
      </dl>
      {cmp && <p className="compare">{cmp}</p>}
      <h3 className="panel__h3">Severity-weighted activity, 36 months</h3>
      <Sparkline series={data.seriesByArea.get(name)} month={month} />
    </>
  )
}

function ForecastDetail({ data, name, rec }) {
  const insufficient = rec.tier === 'insufficient_data'
  const cmp = compareText(rec)
  return (
    <>
      <TierLine tier={rec.tier} />
      {!insufficient && (
        <>
          <dl className="stats">
            <Stat
              label="Severity-weighted activity (forecast)"
              value={fmtNum(rec.forecast_weighted_index)}
              sub={`Uncertainty range: ${fmtNum(rec.interval_low)} to ${fmtNum(rec.interval_high)} (80%)`}
            />
            <Stat label="Reported incidents" value={`About ${fmtNum(rec.forecast_incident_count)}`} />
            <Stat label="12-month average" value={fmtNum(rec.baseline_weighted_index)} />
          </dl>
          <p className="stats__note">
            Typical level uses the area&rsquo;s trailing {TIER_WINDOW_MONTHS} months; the 12-month average is the
            simple baseline the forecast is compared against.
          </p>
        </>
      )}
      {cmp && <p className="compare">{cmp}</p>}
      {rec.drivers?.length > 0 && (
        <>
          <h3 className="panel__h3">What this is based on</h3>
          <ul className="drivers">
            {rec.drivers.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </>
      )}
      <h3 className="panel__h3">Severity-weighted activity, 36 months{insufficient ? '' : ' and forecast'}</h3>
      <Sparkline
        series={data.seriesByArea.get(name)}
        month={DATA_THROUGH}
        forecast={
          insufficient
            ? null
            : { month: rec.month, value: rec.forecast_weighted_index, low: rec.interval_low, high: rec.interval_high }
        }
      />
      <p className="panel__note">
        Forecast made with data through {monthLabel(rec.data_through ?? DATA_THROUGH)} ({rec.horizon_months ?? 2} months
        ahead).
      </p>
    </>
  )
}

export default function DetailPanel({ data, mode, month, selected, onSelect }) {
  const rec = selected ? recordFor(data, mode, month, selected) : null
  return (
    <aside className="panel" aria-label="Neighbourhood details">
      <div className="field">
        <label htmlFor="area-select">Neighbourhood</label>
        <div className="field__row">
          <select id="area-select" value={selected ?? ''} onChange={(e) => onSelect(e.target.value || null)}>
            <option value="">All areas (summary)</option>
            {SORTED.map((a) => (
              <option key={a.slug} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
          {selected && (
            <button type="button" className="btn btn--ghost" onClick={() => onSelect(null)}>
              Clear
            </button>
          )}
        </div>
      </div>

      {!selected && <Summary data={data} mode={mode} month={month} />}
      {selected && (
        <div className="detail">
          <p className="eyebrow">{mode === 'forecast' ? 'Forecast · October 2026' : `${monthLabel(month)} · Reported`}</p>
          <h2 className="detail__name">{selected}</h2>
          {!rec && <p className="compare">No data for this month.</p>}
          {rec && mode === 'historical' && <HistoricalDetail data={data} name={selected} month={month} rec={rec} />}
          {rec && mode === 'forecast' && <ForecastDetail data={data} name={selected} rec={rec} />}
        </div>
      )}
    </aside>
  )
}
