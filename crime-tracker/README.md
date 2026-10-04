# NeighbourCast (frontend)

A map of Vancouver's 24 VPD neighbourhoods. **Historical** mode shows reported-incident activity for any complete
month from January 2003 to August 2026; **Forecast** mode shows the October 2026 forecast with an 80% uncertainty
range. Every area is coloured below typical / typical / above typical relative to this area's own history, never
against other areas. Data: VPD GeoDASH open data. Not affiliated with the Vancouver Police Department.

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

## Data source: static files or the backend

| Setting | Where the app reads from |
|---|---|
| `VITE_API_URL` unset (default) | `public/data/history.json`, `public/data/forecast_2026-10.json`, `public/data/local-area-boundary.geojson` |
| `VITE_API_URL=https://api.example` | `${VITE_API_URL}/history`, `${VITE_API_URL}/forecast`, `${VITE_API_URL}/boundaries` |

Set it in `.env.local` (for example `VITE_API_URL=http://localhost:8000`) or in the hosting provider's build settings.
The backend endpoints must return the same JSON shapes as the static files.

## Where the data files come from

- `history.json` and `forecast_2026-10.json`: `ml/outputs/` on the `ml-forecast` branch (schema in
  `docs/ML_TEAM_CONTRACT.md`, section 7). Built from `data/processed/neighbourhood_monthly.csv`.
- `local-area-boundary.geojson`: City of Vancouver Open Data, "local-area-boundary" (22 polygons, `properties.name`).

Name join (see `src/areas.js`): VPD "Central Business District" is the polygon "Downtown"; Stanley Park and
Musqueam have no polygon and are drawn as circles. Musqueam is never merged into Dunbar-Southlands.

The partial month 2026-09 (`is_partial = 1`) is loaded but never shown on the timeline.

## Swapping in new forecast files

1. Copy the new `history.json` and `forecast_YYYY-MM.json` from `ml/outputs/` into `public/data/`.
2. If the forecast month or the last complete month changed, update `FORECAST_MONTH`, `DATA_THROUGH`,
   `PARTIAL_MONTH` and `TAGLINE`/`DATA_NOTE` in `src/config.js`, and the forecast file name in `src/api.js`.
3. Run `npm run build` and check one area in each mode against the JSON.

## Code map

| File | Purpose |
|---|---|
| `src/config.js` | App name, dates, tier labels and palette, limitations text |
| `src/areas.js` | The 24 VPD names, polygon names, marker positions, URL slugs |
| `src/api.js` | Loads and indexes the three files |
| `src/MapView.jsx` | Leaflet map, area shapes, tooltips |
| `src/DetailPanel.jsx`, `src/Sparkline.jsx` | Selected-area details and 36-month chart |
| `src/Controls.jsx`, `src/Legend.jsx`, `src/About.jsx` | Mode toggle and timeline, legend, About section |

Basemap: Esri light grey canvas (keyless CARTO tiles now return "API key required" placeholders), falling back to
OpenStreetMap tiles if Esri fails.
