// App-wide constants. Rename the app here; nothing else hard-codes the name.
export const APP_NAME = 'NeighbourCast'

export const FIRST_MONTH = '2003-01'
// First month shown on the timeline: the first that can be compared with the same month a year earlier.
export const SLIDER_START = '2004-01'
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
  tier_window_months: 12, // trailing window behind an area's usual level (pct_vs_typical and the probabilities)
  tier_thresholds_pct: [-10, 10], // the band around the usual level: "above" is past hi, "below" past lo
  tier_reference: 'seasonal', // or 'trailing_mean': 'seasonal' is the usual level for that time of year
  interval_level: 0.8, // share of outcomes the uncertainty range is built to hold
  tier_mode: 'probabilistic', // forecast records carry p_below / p_within / p_above
  probability_method: null, // how the chances were built ('kde' or 'lognormal'); named in How this works
  // Held-out evaluation. Used only when the file has no evaluation block (never mixed with the file's numbers).
  evaluation: {
    wape_pct: 12.9,
    improvement_vs_mean_12_pct: 4.3,
    interval_coverage_pct: 79.7,
    tier_accuracy_pct: 58.9,
    tier_majority_baseline_pct: 42.4,
    // Placeholders: the scores of the chances come only from the pipeline's meta.json. A null line is left out.
    probabilistic: {
      brier_above: null,
      brier_below: null,
      brier_above_baseline: null,
      brier_below_baseline: null,
      rps: null,
      rps_baseline: null,
      rps_hard_tier: null,
      reliability_above: [],
      reliability_below: [],
      statement: null,
      scored_on: null,
    },
  },
}

// Plain-language names for the model ids meta.json can carry; any other id is shown as written.
export const MODEL_NAMES = {
  poisson_glm: 'a Poisson regression (GLM)',
  negative_binomial_glm: 'a negative binomial regression (GLM)',
  mean_12: 'each area’s 12-month average',
  seasonal_naive: 'the same month a year earlier',
}

// The one continuous, diverging colour scale (src/scale.js interpolates between the three stops in OKLab).
// Keep in sync with the --scale-* and --fill-none tokens in index.css (Leaflet needs literal values).
// Text is never coloured by the scale: a swatch or a bar carries the colour, a label carries the meaning.
export const SCALE = {
  below: '#4FB3AC', // v = -1: below the usual level is likely (forecast), or 30% below it (past months)
  mid: '#7A8699', // v = 0: even odds, or at the usual level
  above: '#E7A64E', // v = +1: above the usual level is likely, or 30% above it
}
// Past months: a deviation of this many percent from the usual level gets the full colour.
export const HIST_SATURATE_PCT = 30

// Fills that are not on the scale. "Insufficient data" is hatched (HATCH_ID); "No reference yet" (no usual level
// to compare with: an area's first 12 months) is a flat dark fill.
export const FILL_NONE = '#33415C'
export const LABEL_INSUFFICIENT = 'Insufficient data'
export const LABEL_NONE = 'No reference yet'

// Id of the SVG hatch pattern used to fill "insufficient data" shapes (defined once in MapStage).
export const HATCH_ID = 'nc-hatch'

// Plain-language names for the probability_method ids meta.json can carry; any other value is left out.
export const PROBABILITY_METHODS = {
  kde: 'a smoothed spread of past forecast errors (a Gaussian kernel)',
  lognormal: 'a log-normal curve fitted to past forecast errors',
}

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
