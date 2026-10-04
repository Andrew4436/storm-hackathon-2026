import { FILL_NONE, FIRST_MONTH, HIST_SATURATE_PCT, LABEL_INSUFFICIENT, LABEL_NONE } from './config.js'
import {
  beyondWords,
  edgeWords,
  monthLabel,
  referenceLabel,
  referenceLevel,
  sameMonthLastYear,
  yearEarlier,
} from './format.js'
import { HATCH_FILL, scaleGradient } from './scale.js'
import { Swatch } from './Swatch.jsx'

const GRADIENT = scaleGradient()
const NBSP = String.fromCharCode(0xa0)

/**
 * The legend's words, all built from meta.json and the month on show: a title that names exactly what is compared
 * with what (the months and the band), short labels at the two ends of the bar and under its middle, and a note for
 * screen readers on how the colour is worked out.
 */
function legendText(mode, meta, month) {
  if (mode === 'forecast') {
    // v = p_above - p_below: the ends of the bar are a chance of about 90% or more one way (src/scale.js).
    const m = meta.forecast_month
    const edge = edgeWords(meta)
    return {
      title: `Chance that ${monthLabel(m)} ends ${beyondWords(meta)} ${referenceLevel(meta, m, 'this area’s')}`,
      labels: ['Quieter', 'Even odds', 'Busier'],
      note: `The colour is the chance of ending ${edge.above} minus the chance of ending ${edge.below}; the ends of the bar mean about a 90% chance one way.`,
    }
  }
  // The record's first year has no month a year earlier to compare with.
  const before = sameMonthLastYear(meta) && yearEarlier(month) < FIRST_MONTH
  return {
    title: before
      ? `Severity-weighted activity in ${monthLabel(month)}: nothing to compare with yet (the record starts in ${monthLabel(FIRST_MONTH)})`
      : `Severity-weighted activity in ${monthLabel(month)} compared with ${referenceLabel(meta, month, { owner: 'this area’s' })}`,
    labels: ['Quieter', 'Same', 'Busier'],
    note: `The colour reaches full strength at ${HIST_SATURATE_PCT}% lower or higher.`,
  }
}

/**
 * The legend under the control bar: a title of one or two lines, the continuous colour scale as a gradient bar with
 * short labels at both ends and under the middle, plus swatches for the two fills that are not on the scale.
 */
export default function Legend({ mode, meta, month, showNone }) {
  const s = legendText(mode, meta, month ?? meta.data_through)
  const [lo, mid, hi] = s.labels
  return (
    <section className="legend surface surface--frost" aria-label="Map legend">
      {/* A no-break space keeps each month with its year when the title wraps ("September 2024"). */}
      <p className="legend__title">{s.title.replace(/ (\d{4})\b/g, `${NBSP}$1`)}</p>
      <div className="legend__row">
        <div className="legend__scale">
          {/* Reading order left, middle, right; the grid areas in App.css place them around the bar. */}
          <span className="legend__lo">{lo}</span>
          <span className="legend__mid">{mid}</span>
          <span className="legend__hi">{hi}</span>
          <span className="legend__bar" style={{ backgroundImage: GRADIENT }} aria-hidden="true" />
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
      </div>
    </section>
  )
}
