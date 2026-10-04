import { AREAS } from './areas.js'
import { LEGEND_ORDER, TIERS } from './config.js'

const SORTED = [...AREAS].sort((a, b) => a.name.localeCompare(b.name))

/** "6 below, 10 typical, 7 above, 1 with insufficient data" */
function countsText(tiers) {
  const counts = {}
  for (const t of tiers.values()) counts[t] = (counts[t] ?? 0) + 1
  return [...LEGEND_ORDER, 'none']
    .filter((t) => counts[t])
    .map((t) => `${counts[t]} ${TIERS[t].short}`)
    .join(', ')
}

/**
 * The whole city at a glance: one cell per area, alphabetical, filled with its tier for the current view.
 * The cells are a mouse shortcut; the list below is the keyboard, touch and screen-reader route to every area
 * (on touch screens the cells are too small to tap, so CSS turns their pointer events off).
 */
export default function PulseStrip({ tiers, selected, highlighted, onHover, onSelect, drawerOpen, selectRef }) {
  const hovered = highlighted && tiers.has(highlighted) ? highlighted : null
  return (
    <section className="pulse surface surface--frost" aria-label="All 24 neighbourhoods">
      <div className="pulse__top">
        <div className="pulse__cells" aria-hidden="true" onMouseLeave={() => onHover(null)}>
          {SORTED.map((a) => (
            <div
              key={a.slug}
              className={[
                'pulse__cell',
                `swatch--${tiers.get(a.name) ?? 'none'}`,
                a.name === selected ? 'is-selected' : '',
                a.name === hovered ? 'is-hovered' : '',
              ].join(' ')}
              onMouseEnter={() => onHover(a.name)}
              onClick={() => onSelect(a.name)}
            />
          ))}
        </div>
        <p className="pulse__counts">{countsText(tiers)}</p>
      </div>
      <div className="pulse__bottom">
        <p className="pulse__hint">
          {hovered
            ? `${hovered}, ${TIERS[tiers.get(hovered)]?.label.toLowerCase() ?? ''}`
            : drawerOpen
              ? 'Select another neighbourhood on the map'
              : 'Select a neighbourhood on the map'}
        </p>
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
      </div>
    </section>
  )
}
