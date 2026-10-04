import { LEGEND_ORDER, TIERS } from './config.js'
import { Swatch } from './Swatch.jsx'

/** One row of swatches under the control bar (it may wrap on narrow screens). */
export default function Legend({ showNone }) {
  const rows = showNone ? [...LEGEND_ORDER, 'none'] : LEGEND_ORDER
  return (
    <section className="legend surface surface--frost" aria-label="Map legend">
      <ul className="legend__list">
        {rows.map((tier) => (
          <li key={tier} className="legend__item">
            <Swatch tier={tier} />
            {TIERS[tier].label}
          </li>
        ))}
      </ul>
    </section>
  )
}
