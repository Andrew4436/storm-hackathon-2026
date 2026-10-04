import { DATA_THROUGH, FORECAST_MONTH } from './config.js'
import { monthLabel } from './format.js'

const MODES = [
  { id: 'historical', label: 'Historical' },
  { id: 'forecast', label: 'Forecast' },
]

export default function Controls({ mode, onMode, month, onMonth, months }) {
  const forecast = mode === 'forecast'
  const idx = Math.max(0, months.indexOf(month))
  const step = (d) => onMonth(months[Math.min(months.length - 1, Math.max(0, idx + d))])

  return (
    <div className="controls">
      <div className="segmented" role="group" aria-label="Map mode">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            className="segmented__btn"
            aria-pressed={mode === m.id}
            onClick={() => onMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className={forecast ? 'timeline timeline--off' : 'timeline'}>
        <p className="timeline__label" aria-live="polite">
          {forecast ? (
            <>
              Forecast for {monthLabel(FORECAST_MONTH)}
              <span className="timeline__sub">, made with data through {monthLabel(DATA_THROUGH)}</span>
            </>
          ) : (
            monthLabel(month)
          )}
        </p>
        <div className="timeline__row">
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => step(-1)}
            disabled={forecast || idx === 0}
            aria-label="Previous month"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 3 5 8l5 5" />
            </svg>
          </button>
          <input
            type="range"
            className="timeline__range"
            min={0}
            max={months.length - 1}
            step={1}
            value={forecast ? months.length - 1 : idx}
            onChange={(e) => onMonth(months[Number(e.target.value)])}
            disabled={forecast}
            aria-label="Month"
            aria-valuetext={
              forecast ? `Forecast month is fixed to ${monthLabel(FORECAST_MONTH)}` : monthLabel(month)
            }
          />
          <button
            type="button"
            className="btn btn--icon"
            onClick={() => step(1)}
            disabled={forecast || idx === months.length - 1}
            aria-label="Next month"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="m6 3 5 5-5 5" />
            </svg>
          </button>
        </div>
        <div className="timeline__ends" aria-hidden="true">
          <span>{monthLabel(months[0], true)}</span>
          <span>{monthLabel(months[months.length - 1], true)}</span>
        </div>
      </div>
    </div>
  )
}
