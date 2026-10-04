// App-wide constants. Rename the app here; nothing else hard-codes the name.
export const APP_NAME = 'NeighbourCast'

export const FIRST_MONTH = '2003-01'
export const DATA_THROUGH = '2026-08' // last complete month
// The month the VPD extract stops part-way through (is_partial = 1), or null if it ends on a month boundary.
export const PARTIAL_MONTH = '2026-09'
export const EXTRACT_END = '2026-09-25' // last day in the VPD extract
export const PARTIAL_SHARE_PCT = 70 // how much of a normal month the partial month holds
export const FORECAST_MONTH = '2026-10' // also names the static file: public/data/forecast_<FORECAST_MONTH>.json
export const HORIZON_MONTHS = 2
// Held-out evaluation behind "How well the forecast does" (from the ML team's evaluation report).
export const EVAL_FROM = '2025-01'
export const EVAL_TO = '2026-08'
export const EVAL_GAIN_PCT = 4 // error reduction of the shipped Poisson GLM against the 12-month average
export const SPARK_MONTHS = 36
export const MINI_SPARK_MONTHS = 12
// Trailing window behind an area's "typical level" (tiers and pct_vs_typical).
export const TIER_WINDOW_MONTHS = 36
// Playback speed for "Play months", in milliseconds per month.
export const PLAY_INTERVAL_MS = 350

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
