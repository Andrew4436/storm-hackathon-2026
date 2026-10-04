import { FILL_NONE, HIST_SATURATE_PCT, LABEL_INSUFFICIENT, LABEL_NONE } from './config.js'
import { HATCH_FILL, scaleGradient, scalePos } from './scale.js'
import { Swatch } from './Swatch.jsx'

const GRADIENT = scaleGradient()

// Forecast: v = p_above - p_below, so +/-0.8 is a 90% chance one way (when "within" is close to 0).
const FORECAST = {
  labels: ['Likely below usual', 'Even', 'Likely above usual'],
  ticks: [
    { v: -0.8, caption: '90%' },
    { v: 0, caption: '50/50' },
    { v: 0.8, caption: '90%' },
  ],
  note: 'Colour shows the chance of the month ending below or above its usual level. Ticks mark a 90% chance below, even odds, and a 90% chance above.',
}
const HISTORICAL = {
  labels: [`${HIST_SATURATE_PCT}% below usual`, 'Usual', `${HIST_SATURATE_PCT}% above usual`],
  ticks: [{ v: 0, caption: '' }],
  note: `Colour shows how far the month was from its usual level for the time of year, at full strength from ${HIST_SATURATE_PCT}% either way.`,
}

/**
 * The legend under the control bar: the continuous colour scale as a gradient bar with text labels at both ends
 * and the middle, plus swatches for the two fills that are not on the scale.
 */
export default function Legend({ mode, showNone }) {
  const s = mode === 'forecast' ? FORECAST : HISTORICAL
  const [lo, mid, hi] = s.labels
  return (
    <section className="legend surface surface--frost" aria-label="Map legend">
      <div className="legend__scale">
        <span className="legend__lo">{lo}</span>
        <span className="legend__mid">{mid}</span>
        <span className="legend__hi">{hi}</span>
        <span className="legend__bar" style={{ backgroundImage: GRADIENT }} aria-hidden="true" />
        <span className="legend__caps" aria-hidden="true">
          {s.ticks.map((t) => (
            <span key={t.v} className="legend__tick" style={{ left: scalePos(t.v) }}>
              {t.caption}
            </span>
          ))}
        </span>
        <span className="visually-hidden">{s.note}</span>
      </div>
      <ul className="legend__list">
        <li className="legend__item">
          <Swatch fill={HATCH_FILL} />
          {LABEL_INSUFFICIENT}
        </li>
        {showNone && (
          <li className="legend__item">
            <Swatch fill={FILL_NONE} />
            {LABEL_NONE}
          </li>
        )}
      </ul>
    </section>
  )
}
