# NeighbourCast (frontend)

A map of Vancouver's 24 VPD neighbourhoods. **Historical** mode shows reported-incident activity for any complete
month from `FIRST_MONTH` (`src/config.js`) to the last complete month (`data_through` in `public/data/meta.json`);
**Forecast** mode shows the forecast for `forecast_month` from the same file, with an uncertainty range
(`interval_level`, 80% today). Areas are coloured on **one continuous scale** against each area's own comparison
level, never against other areas. With `tier_reference: "seasonal"` and `tier_window_months: 12` (today's
`meta.json`) the comparison level for any month is exactly that area's severity-weighted activity in the same calendar
month one year earlier: October 2025 for the October 2026 forecast, June 2023 for June 2024. The band around it is
`tier_thresholds_pct`, ±10%:

- **Forecast:** the colour is `p_above - p_below`, the balance of the chances that the month ends more than 10% above
  or more than 10% below the comparison level, so amber means above is likely, teal below is likely, grey even odds.
  The drawer shows all three chances.
- **Historical:** the colour is the month's actual deviation, `pct_vs_typical / 30` (30% either way is full colour).

Data: VPD GeoDASH open data. Not affiliated with the Vancouver Police Department.

**Where the numbers come from.** The performance block ("How well does it forecast?" in How this works) and every
label built from the pipeline (last complete month, forecast month, horizon, model name, the comparison month and
the band around it, the range level, the chances) come from `public/data/meta.json` and the forecast file. That file is a copy of `ml/outputs/meta.json`, made
by `npm run sync-data`; nothing in the app recomputes or hard-codes an evaluation figure. `META_DEFAULTS` in
`src/config.js` is a fallback used only when the file or a field is missing or invalid. One exception: the held-out
test period named in the performance block is `EVAL_FROM`..`EVAL_TO` in `src/config.js` (2025-01..2026-08), because
the current `evaluation.folds` lists fold objects, not months (see "meta.json" below).

Stack: Vite, React 19 (JSX), react-leaflet 5, Leaflet. No other runtime dependencies.

## Run

```bash
npm install
npm run sync-data  # copy the latest ML outputs into public/data/ (see below)
npm run dev        # http://localhost:5173
npm run build      # production build in dist/
npx eslint .       # lint
```

The view is kept in the URL query, so a demo can be bookmarked:
`/?mode=forecast&area=central-business-district` or `/?mode=historical&month=2024-06&area=kitsilano`.

## Using the app

- The **control bar** sits at the top left of the map (on phones, under the map). Its first row holds
  **Historical / Forecast**, the month being shown, **How this works** and the **neighbourhood list**; its second row
  holds **Play months**, the previous and next arrows and the month scrubber.
- The **legend** sits directly under the control bar, left-aligned with it. A title names exactly what the colour
  compares, then a 220 px gradient bar built from the same colour function as the map (`colourFor` in
  `src/scale.js`) with short labels at both ends and, on a small tick, under its middle:
  - Forecast: "Chance that October 2026 ends more than 10% above or below this area's October 2025 level", bar
    labelled **Quieter | Even odds | Busier** (the ends of the bar are about a 90% chance one way).
  - Historical: "Severity-weighted activity in June 2024 compared with June 2023" (the selected month and the same
    month a year earlier), bar labelled **Quieter | Same | Busier** (full colour at 30% lower or higher). In the
    record's first year the title says there is nothing to compare with yet.

  Every month and the 10% band come from `meta.json` (`forecast_month`, `tier_thresholds_pct`) and the month on
  show, through `referenceLabel()` and `bandPct()` in `src/format.js`. Next to the bar, a hatched swatch for
  **Insufficient data** and, only while some area in the view has nothing to compare with (the first 12 months of
  the record), a flat swatch for **No reference yet**. At desktop widths the title wraps to at most two lines
  (480 px) and always keeps room for two, so the legend keeps the same height in both modes and every month. On
  phones the title wraps to the panel width, the end labels sit above the ends of a full-width bar and the middle
  label under it. The map fits the city into the space the bar, the legend and the zoom control leave free.
- **Historical / Forecast** switch between past months and the forecast month. In Historical mode the scrubber and
  the arrows pick any complete month, and **Play months** steps forward one month at a time (`PLAY_INTERVAL_MS` in
  `src/config.js`) and stops at the last month. Playback is off in Forecast mode.
- Selecting an area on the map, or from the neighbourhood list in the control bar ("Choose from the list", the route
  for keyboard, touch and screen-reader users), opens the **drawer** on the right: its figures, how it compares with
  its own history, and a chart of recent months. On phones the drawer is a **bottom sheet**. **Close** or Escape closes
  it.
  - Forecast: the forecast number, the incident estimate, the range bar with the 12-month baseline, then the
    **chances**: a stacked bar (more than 10% below / within 10% / more than 10% above, teal / grey / amber,
    percentages inside wide segments, a key under it) and the sentence "56% chance that October 2026 ends more than
    10% above its October 2025 level, 19% chance more than 10% below, 25% chance within 10% of it." followed by
    "Most likely: more than 10% above October 2025 (56%)". The percentages are rounded to add up to 100; the months
    come from `forecast_month`, the band from `tier_thresholds_pct`, "most likely" from `most_likely`.
  - Historical: the month's figures and its actual deviation against the same month a year earlier ("15% above June
    2023", or "About the same as June 2023" within 1%). No chances.
  - Under the sentence: "The comparison level is this area's severity-weighted activity in the same month one year
    earlier." (with another `tier_reference` or window, a generic description of the comparison level instead).
  - Insufficient data: one sentence and the chart, no bar.
- **Hover card** (mouse only): the area, one line with its colour and either the largest chance ("56% chance above
  Oct 2025 level") or the month's deviation ("15% above Jun 2023"), the figures and a 12-month mini chart.
- **How this works** opens the same drawer with the method, the limitations, **How well does it forecast?** (the
  evaluation figures from `meta.json`) and the sources.

## Data source: static files or the backend

| Setting | Where the app reads from |
|---|---|
| `VITE_API_URL` unset (default) | `public/data/meta.json`, `public/data/history.json`, `public/data/forecast_<forecast_month>.json`, `public/data/local-area-boundary.geojson` |
| `VITE_API_URL=https://api.example` | `${VITE_API_URL}/meta`, `${VITE_API_URL}/history`, `${VITE_API_URL}/forecast`, `${VITE_API_URL}/boundaries` |

Set it in `.env.local` (for example `VITE_API_URL=http://localhost:8000`) or in the hosting provider's build settings.
The backend endpoints must return the same JSON shapes as the static files. Static files are fetched relative to the
build's base path (`import.meta.env.BASE_URL`), so they also load under `/storm-hackathon-2026/` on GitHub Pages.

## meta.json

Written by the ML pipeline as `ml/outputs/meta.json` (keys listed in `docs/ML_TEAM_CONTRACT.md`, section 7) and
copied to `public/data/meta.json` by `npm run sync-data`. The app loads it first (the forecast file is named after
its `forecast_month`) and uses it for:

| Key | Used for |
|---|---|
| `data_through`, `forecast_month`, `horizon_months` | Last month on the timeline, the forecast month and file name, "N months ahead", the month in the chances sentence |
| `tier_window_months`, `tier_thresholds_pct` `[lo, hi]`, `tier_reference` (`trailing_mean` or `seasonal`) | What each month is compared with and the band around it (legend title, area detail, hover card, How this works). `seasonal` with a 12-month window names the same month one year earlier ("October 2025"; `referenceLabel()` in `src/format.js`); any other combination falls back to a generic phrase ("its usual level for that time of year, from the previous N complete months", or "its average over the previous N complete months" for `trailing_mean`). The band is "more than 10% above / below" and "within 10% of" (`bandPct()`) |
| `interval_level` | "The range covers 80% of likely outcomes" |
| `model` | The model name in How this works (`MODEL_NAMES` in `src/config.js`; other ids are shown as written) |
| `tier_mode` | `"probabilistic"`: the forecast file carries chances. Informational; the app colours by the chances whenever a record has them |
| `probability_method` | How the chances were built (`kde` or `lognormal`), named in How this works via `PROBABILITY_METHODS` in `src/config.js`; other values are not shown |
| `evaluation` | How well does it forecast?: `wape_pct`, `improvement_vs_mean_12_pct`, `interval_coverage_pct`, `tier_accuracy_pct` vs `tier_majority_baseline_pct` (shown as "read as a single call ... right N% of the time") |
| `evaluation.probabilistic` | The scores of the chances: `statement` (shown as written), `brier_above` vs `brier_above_baseline` ("Brier score X vs Y for always using the base rate"), `rps` vs `rps_baseline` (and `rps_hard_tier` when present) ("ranked probability score X vs Y"). `brier_below*`, `reliability_above`, `reliability_below` (`[{bin, predicted, observed, n}]`) and `scored_on` are read and checked but not shown. A line whose fields are missing is left out |

The app ignores the other top-level keys (`app`, `model_description`, `weights_source`, `generated_from`, `notes`).

## Forecast and history records

Forecast records (`forecast_<forecast_month>.json`) are read for: `forecast_weighted_index`,
`forecast_incident_count`, `interval_low`, `interval_high`, `baseline_weighted_index` (the 12-month average tick),
`p_below`, `p_within`, `p_above` (floats that sum to 1, `null` for insufficient data; rescaled if they drift from 1)
and `most_likely` (`above_typical`, `below_typical`, `typical` or `insufficient_data`). `relative_activity_tier`,
`pct_vs_typical` and `typical_weighted_index` may be present; `relative_activity_tier` is read only to spot
`insufficient_data`. A forecast file without the three chances (an older pipeline) still works: each area is then
coloured by the forecast's own `pct_vs_typical`, like a past month, and the drawer shows that deviation instead of the
chances.

History records (`history.json`) are read for `weighted_index`, `incident_count`, `pct_vs_typical` (the change against
the same month one year earlier; `null` where there is nothing to compare with yet: shown as "No reference yet") and `relative_activity_tier` (only to spot `insufficient_data`,
shown hatched). `src/api.js` gives every record a `kind` (`value`, `insufficient_data` or `none`) and `v`, its place on
the scale; `src/scale.js` holds the mapping.

The file is optional. If it is missing or not valid JSON, or a field is missing or invalid, the app uses
`META_DEFAULTS` in `src/config.js` for it and logs a warning. The evaluation block is taken whole, from the file or
from the defaults, never mixed. The held-out period named in How this works is `EVAL_FROM` to `EVAL_TO` in
`src/config.js`, unless `evaluation.folds` is a list of `YYYY-MM` test months.

## Updating the data: `npm run sync-data`

`scripts/sync-data.mjs` (Node, no dependencies) copies the ML outputs from the repo's `ml/outputs/` (`../ml/outputs`
from this package) into `public/data/`:

1. reads `meta.json` and its `forecast_month`;
2. checks that `meta.json`, `history.json` and `forecast_<forecast_month>.json` exist and are valid JSON (nothing is
   copied if one is missing or broken, and the script exits with an error);
3. copies the three files into `public/data/` and deletes any other `forecast_*.json` there;
4. prints each file copied (with its size), each file removed, and the forecast month, last complete month and model.

`local-area-boundary.geojson` is not touched. To copy from another folder: `npm run sync-data -- path/to/outputs`.
After syncing, check one area in each mode against the JSON and run `npm run build`.

Where the files come from:

- `meta.json`, `history.json` and `forecast_<forecast_month>.json`: `ml/outputs/` (schema in
  `docs/ML_TEAM_CONTRACT.md`, section 7). Built from `data/processed/neighbourhood_monthly.csv`.
- `local-area-boundary.geojson`: City of Vancouver Open Data, "local-area-boundary" (22 polygons, `properties.name`).

Name join (see `src/areas.js`): VPD "Central Business District" is the polygon "Downtown"; Stanley Park and
Musqueam have no polygon and are drawn as circles. Musqueam is never merged into Dunbar-Southlands.

The partial month (`is_partial = 1`, and anything after `data_through`) is loaded but never shown on the timeline.
`PARTIAL_MONTH`, `EXTRACT_END` and `PARTIAL_SHARE_PCT` in `src/config.js` describe it in How this works; update them
when the VPD extract changes (that section is hidden once `PARTIAL_MONTH` is no longer after `data_through`).

## Deploying to GitHub Pages

The site is served from `https://<user>.github.io/storm-hackathon-2026/`, so build with that base path:

```bash
npm run sync-data
VITE_BASE=/storm-hackathon-2026/ npm run build
```

- `dist/` is the site: publish its contents (for example to a `gh-pages` branch, or with the Pages "upload
  artifact" action). Check that `dist/index.html` references `/storm-hackathon-2026/assets/...`.
- `dist/.nojekyll` must be there so Pages serves the files as they are; it comes from `public/.nojekyll`, which Vite
  copies into every build.
- The env prefix works in macOS and Linux shells and in Git Bash on Windows. (Git Bash rewrites
  `/storm-hackathon-2026/` into a Windows path under its install folder; `vite.config.js` takes that prefix off
  again.) In PowerShell: `$env:VITE_BASE='/storm-hackathon-2026/'; npm run build`.
- Without `VITE_BASE` the base is `/`, as in development. Run a plain `npm run build` afterwards if you need a
  root-path build again.
- The data files, the favicon and the URL state all follow the base path; the app only reads and writes the query
  string, so bookmarks such as `/storm-hackathon-2026/?mode=forecast&area=kitsilano` work.

## Code map

| File | Purpose |
|---|---|
| `src/config.js` | App name, fixed dates, `META_DEFAULTS` (fallbacks for `meta.json`), model and probability-method names, the colour scale's three stops (`SCALE`), `HIST_SATURATE_PCT`, the off-scale fills and labels, map styling, limitations text |
| `src/scale.js` | The continuous colour scale: `colourFor(v)` for v in [-1, 1] (OKLab between teal, grey and amber), the legend gradient, `fillFor(record)`, and how each record's fields become `v` |
| `src/index.css` | Design tokens (ink, fog, the scale stops and off-scale fills, type scale, radii) and base styles |
| `src/areas.js` | The 24 VPD names, polygon names, marker positions, URL slugs |
| `src/api.js` | Loads `meta.json` (checked field by field) and the three data files under the base path, and indexes them |
| `src/format.js` | Numbers, months, and the wording built from `meta.json` (the comparison month via `referenceLabel()`, the band via `bandPct()`, chances, range, model name, scores) |
| `src/App.jsx` | View state (mode, month, area, playback), URL sync, loading and error states, drawer |
| `src/MapStage.jsx` | The full-bleed map and the panels floating over it; owns hover state; measures what the fit avoids (control bar, legend, zoom control, drawer) |
| `src/MapView.jsx` | Leaflet map: one GeoJSON layer plus two circle markers, restyled with `setStyle`; panel- and drawer-aware fit |
| `src/HoverCard.jsx` | The single hover card, rendered from React state (no Leaflet tooltips) |
| `src/ControlBar.jsx`, `src/legend.jsx` | Mode and month controls with playback and the neighbourhood list; the gradient legend under them (the file name is lower case in git; `MapStage.jsx` imports it as such) |
| `src/Drawer.jsx`, `src/AreaDetail.jsx`, `src/HowItWorks.jsx` | Drawer (bottom sheet on phones), selected-area detail with the chances bar, "How this works" |
| `src/Sparkline.jsx`, `src/Swatch.jsx`, `src/Icons.jsx` | 36-month chart, colour swatch, inline icons |
| `src/ErrorBoundary.jsx` | Shows a reload message instead of a blank page if rendering fails |
| `scripts/sync-data.mjs` | `npm run sync-data`: copies the ML outputs into `public/data/` |
| `vite.config.js` | `base` from `VITE_BASE` (GitHub Pages) |

Basemap: Esri dark grey canvas (keyless CARTO tiles now return "API key required" placeholders), falling back to
OpenStreetMap tiles (darkened in CSS) if Esri fails.
