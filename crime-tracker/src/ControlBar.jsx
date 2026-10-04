import { AREAS } from './areas.js'
import { FORECAST_MONTH } from './config.js'
import { monthLabel } from './format.js'
import { ChevronDownIcon, NextIcon, PauseIcon, PlayIcon, PrevIcon } from './Icons.jsx'

const MODES = [
  { id: 'historical', label: 'Historical' },
  { id: 'forecast', label: 'Forecast' },
]

const SORTED = [...AREAS].sort((a, b) => a.name.localeCompare(b.name))

/**
 * Mode, month, "How this works" and the neighbourhood list on the first row; playback and the month scrubber on
 * the second. The month label has a fixed width, so the bar never changes size as the months go by. The list is
 * the keyboard, touch and screen-reader route to every area.
 */
export default function ControlBar({
  mode,
  onMode,
  month,
  onMonth,
  months,
  playing,
  onPlay,
  onAbout,
  aboutOpen,
  aboutRef,
  selected,
  onSelect,
  selectRef,
}) {
  const forecast = mode === 'forecast'
  const idx = Math.max(0, months.indexOf(month))
  const last = months.length - 1
  const step = (d) => onMonth(months[Math.min(last, Math.max(0, idx + d))])

  return (
    <div className="bar surface surface--frost" role="group" aria-label="Map controls">
      <div className="bar__row">
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
        <p className="bar__month" aria-live={playing ? 'off' : 'polite'}>
          {monthLabel(forecast ? FORECAST_MONTH : month)}
          {forecast && <span className="visually-hidden"> forecast</span>}
        </p>
        <button
          type="button"
          className="btn btn--quiet bar__about"
          onClick={onAbout}
          aria-expanded={aboutOpen}
          ref={aboutRef}
        >
          How this works
        </button>
        <div className="select-wrap bar__area">
          <label className="visually-hidden" htmlFor="area-select">
            Neighbourhood
          </label>
          <select
            id="area-select"
            ref={selectRef}
            className="select"
            value={selected ?? ''}
            onChange={(e) => onSelect(e.target.value || null)}
          >
            <option value="">Choose from the list</option>
            {SORTED.map((a) => (
              <option key={a.slug} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
          <ChevronDownIcon />
        </div>
      </div>

      <div className={forecast ? 'scrub scrub--off' : 'scrub'}>
        <button
          type="button"
          className="btn btn--play"
          onClick={onPlay}
          disabled={forecast}
        >
          {playing ? <PauseIcon /> : <PlayIcon />}
          {playing ? 'Pause' : 'Play months'}
        </button>
        <button
          type="button"
          className="btn btn--icon scrub__prev"
          onClick={() => step(-1)}
          disabled={forecast || idx === 0}
          aria-label="Previous month"
        >
          <PrevIcon />
        </button>
        <input
          type="range"
          className="scrub__range"
          min={0}
          max={last}
          step={1}
          value={forecast ? last : idx}
          onChange={(e) => onMonth(months[Number(e.target.value)])}
          disabled={forecast}
          aria-label="Month"
          aria-valuetext={forecast ? `Forecast month is fixed to ${monthLabel(FORECAST_MONTH)}` : monthLabel(month)}
        />
        <button
          type="button"
          className="btn btn--icon scrub__next"
          onClick={() => step(1)}
          disabled={forecast || idx === last}
          aria-label="Next month"
        >
          <NextIcon />
        </button>
      </div>
    </div>
  )
}
