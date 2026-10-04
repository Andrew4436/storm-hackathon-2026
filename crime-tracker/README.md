# NeighbourCast (frontend)

A map of Vancouver's 24 VPD neighbourhoods. **Historical** mode shows reported-incident activity for any complete
month in the range set in `src/config.js` (`FIRST_MONTH` to `DATA_THROUGH`); **Forecast** mode shows the forecast for
the month named by `FORECAST_MONTH` in the same file, with an 80% uncertainty range. Every area is coloured below
typical / typical / above typical relative to this area's own history, never against other areas. Data: VPD GeoDASH
open data. Not affiliated with the Vancouver Police Department.

Stack: Vite, React 19 (JSX), react-leaflet 5, Leaflet. No other runtime dependencies.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build in dist/
npx eslint .       # lint
```

The view is kept in the URL, so a demo can be bookmarked:
`/?mode=forecast&area=central-business-district` or `/?mode=historical&month=2024-06&area=kitsilano`.

## Using the app

- The **control bar** sits at the top left of the map (on phones, under the map). Its first row holds
  **Historical / Forecast**, the month being shown, **How this works** and the **neighbourhood list**; its second row
  holds **Play months**, the previous and next arrows and the month scrubber.
- **Historical / Forecast** switch between past months and the forecast month. In Historical mode the scrubber and
  the arrows pick any complete month, and **Play months** steps forward one month at a time (`PLAY_INTERVAL_MS` in
  `src/config.js`) and stops at the last month. Playback is off in Forecast mode.
- The **legend** at the bottom left names the four colours; every area is compared with its own history.
- Selecting an area on the map, or from the neighbourhood list in the control bar ("Choose from the list", the route
  for keyboard, touch and screen-reader users), opens the **drawer** on the right: its figures, how it compares with
  its own history, and a chart of recent months. On phones the drawer is a **bottom sheet**. **Close** or Escape closes
  it.
- **How this works** opens the same drawer with the method, the limitations, the evaluation and the sources.

## Data source: static files or the backend

| Setting | Where the app reads from |
|---|---|
| `VITE_API_URL` unset (default) | `public/data/history.json`, `public/data/forecast_<FORECAST_MONTH>.json`, `public/data/local-area-boundary.geojson` |
| `VITE_API_URL=https://api.example` | `${VITE_API_URL}/history`, `${VITE_API_URL}/forecast`, `${VITE_API_URL}/boundaries` |

Set it in `.env.local` (for example `VITE_API_URL=http://localhost:8000`) or in the hosting provider's build settings.
The backend endpoints must return the same JSON shapes as the static files.

## Where the data files come from

- `history.json` and `forecast_<FORECAST_MONTH>.json`: `ml/outputs/` on the `ml-forecast` branch (schema in
  `docs/ML_TEAM_CONTRACT.md`, section 7). Built from `data/processed/neighbourhood_monthly.csv`.
- `local-area-boundary.geojson`: City of Vancouver Open Data, "local-area-boundary" (22 polygons, `properties.name`).

Name join (see `src/areas.js`): VPD "Central Business District" is the polygon "Downtown"; Stanley Park and
Musqueam have no polygon and are drawn as circles. Musqueam is never merged into Dunbar-Southlands.

The partial month (`PARTIAL_MONTH` in `src/config.js`, `is_partial = 1`) is loaded but never shown on the timeline.

## Swapping in new forecast files

1. Copy the new `history.json` and `forecast_YYYY-MM.json` from `ml/outputs/` into `public/data/`.
2. If the forecast month or the last complete month changed, update the dates in `src/config.js`:
   `FORECAST_MONTH` (it also names the static forecast file), `DATA_THROUGH`, `PARTIAL_MONTH` (or `null`),
   `EXTRACT_END` and `PARTIAL_SHARE_PCT`, plus `EVAL_FROM`, `EVAL_TO` and `EVAL_GAIN_PCT` if the evaluation was
   re-run. Every date shown in the app and in "How this works" is built from these.
3. Run `npm run build` and check one area in each mode against the JSON.

## Code map

| File | Purpose |
|---|---|
| `src/config.js` | App name, dates, tier labels and palette, map styling, limitations text |
| `src/index.css` | Design tokens (ink, fog, tier colours, type scale, radii) and base styles |
| `src/areas.js` | The 24 VPD names, polygon names, marker positions, URL slugs |
| `src/api.js` | Loads and indexes the three files |
| `src/App.jsx` | View state (mode, month, area, playback), URL sync, loading and error states, drawer |
| `src/MapStage.jsx` | The full-bleed map and the panels floating over it; owns hover state; measures what the fit avoids (control bar, legend, zoom control, drawer) |
| `src/MapView.jsx` | Leaflet map: one GeoJSON layer plus two circle markers, restyled with `setStyle`; panel- and drawer-aware fit |
| `src/HoverCard.jsx` | The single hover card, rendered from React state (no Leaflet tooltips) |
| `src/ControlBar.jsx`, `src/Legend.jsx` | Mode and month controls with playback and the neighbourhood list; legend |
| `src/Drawer.jsx`, `src/AreaDetail.jsx`, `src/HowItWorks.jsx` | Drawer (bottom sheet on phones), selected-area detail, "How this works" |
| `src/Sparkline.jsx`, `src/Swatch.jsx`, `src/Icons.jsx` | 36-month chart, tier swatch and chip, inline icons |
| `src/ErrorBoundary.jsx` | Shows a reload message instead of a blank page if rendering fails |

Basemap: Esri dark grey canvas (keyless CARTO tiles now return "API key required" placeholders), falling back to
OpenStreetMap tiles (darkened in CSS) if Esri fails.
