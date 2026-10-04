import { LEGEND_ORDER, TIERS } from './config.js'
import { Swatch } from './Swatch.jsx'

export default function Legend({ showNone }) {
  const rows = showNone ? [...LEGEND_ORDER, 'none'] : LEGEND_ORDER
  return (
    <section className="legend surface" aria-label="Map legend">
      <ul className="legend__list">
        {rows.map((tier) => (
          <li key={tier} className="legend__row">
            <Swatch tier={tier} />
            {TIERS[tier].label}
          </li>
        ))}
      </ul>
    </section>
  )
}
