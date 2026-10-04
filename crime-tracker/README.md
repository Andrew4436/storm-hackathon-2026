# NeighbourCast (frontend)

A map of Vancouver's 24 VPD neighbourhoods. **Historical** mode shows reported-incident activity for any complete
month from `FIRST_MONTH` (`src/config.js`) to the last complete month (`data_through` in `public/data/meta.json`);
**Forecast** mode shows the forecast for `forecast_month` from the same file, with an uncertainty range
(`interval_level`, 80% today). Every area is coloured below typical / typical / above typical relative to this area's
own history, never against other areas. Data: VPD GeoDASH open data. Not affiliated with the Vancouver Police
Department.

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
- The **legend** is one row directly under the control bar, left-aligned with it: Below typical, Typical, Above
  typical, Insufficient data (plus Not enough history in the earliest months). On phones it may wrap to two lines.
  The map fits the city into the space the bar, the legend and the zoom control leave free.
- **Historical / Forecast** switch between past months and the forecast month. In Historical mode the scrubber and
  the arrows pick any complete month, and **Play months** steps forward one month at a time (`PLAY_INTERVAL_MS` in
  `src/config.js`) and stops at the last month. Playback is off in Forecast mode.
- Selecting an area on the map, or from the neighbourhood list in the control bar ("Choose from the list", the route
  for keyboard, touch and screen-reader users), opens the **drawer** on the right: its figures, how it compares with
  its own history, and a chart of recent months. On phones the drawer is a **bottom sheet**. **Close** or Escape closes
  it.
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

Written by the ML pipeline next to the other outputs. The app loads it first (the forecast file is named after its
`forecast_month`) and uses it for:

| Key | Used for |
|---|---|
| `data_through`, `forecast_month`, `horizon_months` | Last month on the timeline, the forecast month and file name, "N months ahead" |
| `tier_window_months`, `tier_thresholds_pct` `[lo, hi]`, `tier_reference` (`trailing_mean` or `seasonal`) | How the typical level and the colour thresholds are described (area detail, How this works) |
| `interval_level` | "The range covers 80% of likely outcomes" |
| `model` | The model name in How this works (`MODEL_NAMES` in `src/config.js`; other ids are shown as written) |
| `evaluation` | How well does it forecast?: `wape_pct`, `improvement_vs_mean_12_pct`, `interval_coverage_pct`, `tier_accuracy_pct` vs `tier_majority_baseline_pct` |

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
| `src/config.js` | App name, fixed dates, `META_DEFAULTS` (fallbacks for `meta.json`), model names, tier labels and palette, map styling, limitations text |
| `src/index.css` | Design tokens (ink, fog, tier colours, type scale, radii) and base styles |
| `src/areas.js` | The 24 VPD names, polygon names, marker positions, URL slugs |
| `src/api.js` | Loads `meta.json` (checked field by field) and the three data files under the base path, and indexes them |
| `src/format.js` | Numbers, months, and the wording built from `meta.json` (typical level, thresholds, range, model name) |
| `src/App.jsx` | View state (mode, month, area, playback), URL sync, loading and error states, drawer |
| `src/MapStage.jsx` | The full-bleed map and the panels floating over it; owns hover state; measures what the fit avoids (control bar, legend, zoom control, drawer) |
| `src/MapView.jsx` | Leaflet map: one GeoJSON layer plus two circle markers, restyled with `setStyle`; panel- and drawer-aware fit |
| `src/HoverCard.jsx` | The single hover card, rendered from React state (no Leaflet tooltips) |
| `src/ControlBar.jsx`, `src/Legend.jsx` | Mode and month controls with playback and the neighbourhood list; the legend row under them |
| `src/Drawer.jsx`, `src/AreaDetail.jsx`, `src/HowItWorks.jsx` | Drawer (bottom sheet on phones), selected-area detail, "How this works" |
| `src/Sparkline.jsx`, `src/Swatch.jsx`, `src/Icons.jsx` | 36-month chart, tier swatch and chip, inline icons |
| `src/ErrorBoundary.jsx` | Shows a reload message instead of a blank page if rendering fails |
| `scripts/sync-data.mjs` | `npm run sync-data`: copies the ML outputs into `public/data/` |
| `vite.config.js` | `base` from `VITE_BASE` (GitHub Pages) |

Basemap: Esri dark grey canvas (keyless CARTO tiles now return "API key required" placeholders), falling back to
OpenStreetMap tiles (darkened in CSS) if Esri fails.
