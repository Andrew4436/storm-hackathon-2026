// App-wide constants. Rename the app here; nothing else hard-codes the name.
export const APP_NAME = 'NeighbourCast'
export const TAGLINE =
  "Reported-incident activity in Vancouver's 24 police neighbourhoods, month by month, with a forecast for October 2026."
export const DATA_NOTE = 'VPD GeoDASH open data through Aug 2026 · not affiliated with VPD'

export const FIRST_MONTH = '2003-01'
export const DATA_THROUGH = '2026-08' // last complete month; 2026-09 is partial
export const PARTIAL_MONTH = '2026-09'
export const FORECAST_MONTH = '2026-10'
export const HORIZON_MONTHS = 2
export const SPARK_MONTHS = 36
// Trailing window behind an area's "typical level" (tiers and pct_vs_typical).
export const TIER_WINDOW_MONTHS = 36

// Diverging two-hue palette with a neutral midpoint. Colour-blind friendly, no red.
// Text is never coloured by tier: a swatch carries the colour, a label carries the meaning.
export const TIERS = {
  below_typical: { label: 'Below typical', fill: '#4C78A8' },
  typical: { label: 'Typical', fill: '#BFBFBF' },
  above_typical: { label: 'Above typical', fill: '#E0863C' },
  insufficient_data: { label: 'Insufficient data', fill: '#EDEDED', stroke: '#8A8A8A', dashed: true },
  none: { label: 'Not enough history', fill: '#F4F4F4', stroke: '#B8B8B8' },
}
export const LEGEND_ORDER = ['below_typical', 'typical', 'above_typical', 'insufficient_data']

export const MAP_STYLE = {
  fillOpacity: 0.72,
  stroke: '#FFFFFF',
  weight: 1.25,
  selectedStroke: '#1F2933',
  selectedWeight: 2.5,
  hoverWeight: 2,
}

export const LIMITATIONS =
  "This map shows counts of reported, founded incidents from the Vancouver Police Department's open data, grouped by neighbourhood and month; it is not a rating of any place or the people in it, and VPD advises against using this data to judge the safety of a specific location. Counts depend on what is reported and how it is recorded: some incidents are never reported, recent months can be revised as reports arrive late, and the location and time of offences against a person are withheld for privacy. Category definitions and recording practices change over time, and the 2020-21 pandemic period is unusual, so year-to-year comparisons should be read with care. Forecasts show relative activity compared with each neighbourhood's own history, with uncertainty, and very small areas such as Musqueam have too few incidents to forecast meaningfully. These figures are not comparable to Statistics Canada crime statistics, and this project is not affiliated with the Vancouver Police Department."
