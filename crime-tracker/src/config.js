// App-wide constants. Rename the app here; nothing else hard-codes the name.
export const APP_NAME = 'NeighbourCast'

export const FIRST_MONTH = '2003-01'
// The month the VPD extract stops part-way through (is_partial = 1), or null if it ends on a month boundary.
// "How this works" explains it only while it comes after the last complete month in meta.json.
export const PARTIAL_MONTH = '2026-09'
export const EXTRACT_END = '2026-09-25' // last day in the VPD extract
export const PARTIAL_SHARE_PCT = 70 // how much of a normal month the partial month holds
// Held-out test period named in "How well does it forecast?" (meta.json does not carry it, unless
// evaluation.folds lists the test months, in which case the first and last of those are used).
export const EVAL_FROM = '2025-01'
export const EVAL_TO = '2026-08'
export const SPARK_MONTHS = 36
export const MINI_SPARK_MONTHS = 12
// Playback speed for "Play months", in milliseconds per month.
export const PLAY_INTERVAL_MS = 350

/**
 * Fallbacks for public/data/meta.json, which the ML pipeline writes next to history.json and the forecast
 * (`npm run sync-data` copies all three). The app reads the file at load; a value here is used only when the
 * file is missing or that field is missing or invalid. Same keys as the file.
 */
export const META_DEFAULTS = {
  model: 'poisson_glm',
  data_through: '2026-08', // last complete month
  forecast_month: '2026-10', // also names the static file: public/data/forecast_<forecast_month>.json
  horizon_months: 2,
  tier_window_months: 36, // trailing window behind an area's "typical level" (tiers and pct_vs_typical)
  tier_thresholds_pct: [-5, 5], // within these % of the typical level counts as typical
  tier_reference: 'trailing_mean', // or 'seasonal': the typical level for that time of year
  interval_level: 0.8, // share of outcomes the uncertainty range is built to hold
  // Held-out evaluation. Used only when the file has no evaluation block (never mixed with the file's numbers).
  evaluation: {
    wape_pct: 12.9,
    improvement_vs_mean_12_pct: 4.3,
    interval_coverage_pct: 79.7,
    tier_accuracy_pct: 53.0,
    tier_majority_baseline_pct: 61.1,
  },
}

// Plain-language names for the model ids meta.json can carry; any other id is shown as written.
export const MODEL_NAMES = {
  poisson_glm: 'a Poisson regression (GLM)',
  negative_binomial_glm: 'a negative binomial regression (GLM)',
  mean_12: 'each area’s 12-month average',
  seasonal_naive: 'the same month a year earlier',
}

// Tier colours. Keep in sync with the --tier-* tokens in index.css (Leaflet needs literal values).
// Text is never coloured by tier: a swatch carries the colour, a label carries the meaning.
export const TIERS = {
  below_typical: { label: 'Below typical', short: 'below', fill: '#4FB3AC' },
  typical: { label: 'Typical', short: 'typical', fill: '#7A8699' },
  above_typical: { label: 'Above typical', short: 'above', fill: '#E7A64E' },
  insufficient_data: { label: 'Insufficient data', short: 'with insufficient data', fill: '#A6B2C5', hatch: true },
  none: { label: 'Not enough history', short: 'without enough history', fill: '#33415C' },
}
export const LEGEND_ORDER = ['below_typical', 'typical', 'above_typical', 'insufficient_data']

// Id of the SVG hatch pattern used to fill "insufficient data" shapes (defined once in MapView).
export const HATCH_ID = 'nc-hatch'

export const MAP_STYLE = {
  fillOpacity: 0.78,
  hoverFillOpacity: 0.95,
  dimFillOpacity: 0.55,
  stroke: '#0E1726',
  strokeOpacity: 0.6,
  weight: 1,
  hoverStroke: '#EEF2F7',
  hoverWeight: 1.5,
  selectedStroke: '#EEF2F7',
  selectedWeight: 2.5,
}

export const LIMITATIONS =
  "This map shows counts of reported, founded incidents from the Vancouver Police Department's open data, grouped by neighbourhood and month; it is not a rating of any place or the people in it, and VPD advises against using this data to judge the safety of a specific location. Counts depend on what is reported and how it is recorded: some incidents are never reported, recent months can be revised as reports arrive late, and the location and time of offences against a person are withheld for privacy. Category definitions and recording practices change over time, and the 2020-21 pandemic period is unusual, so year-to-year comparisons should be read with care. Forecasts show relative activity compared with each neighbourhood's own history, with uncertainty, and very small areas such as Musqueam have too few incidents to forecast meaningfully. These figures are not comparable to Statistics Canada crime statistics, and this project is not affiliated with the Vancouver Police Department."
