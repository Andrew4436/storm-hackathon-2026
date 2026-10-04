# backend/: NeighbourCast API

A small, read-only FastAPI service that serves the ML team's exported files and the neighbourhood boundaries to the
map. At startup it reads everything into memory; each request only filters what was loaded. Nothing is recomputed per
request and there is no database.

| Served from | File |
|---|---|
| `ML_OUTPUTS_DIR` (default `ml/outputs/`) | `forecast_YYYY-MM.json` (the latest one), `history.json`, `meta.json` (optional) |
| `backend/static/` | `local-area-boundary.geojson` (22 City of Vancouver local-area polygons) |

Response bodies have **the same shape as the static files** in the frontend's `public/data/`, so the frontend switches
between static files and this API by setting one variable (`VITE_API_URL`). Field definitions are in
[`docs/ML_TEAM_CONTRACT.md`](../docs/ML_TEAM_CONTRACT.md) section 7.

> The root `main.py` is a teammate's standalone CSV-to-JSON utility (documented in `backend_README.md`). It is not part
> of this API and nothing here imports it.

## Run it locally

From the **repo root** (Python 3.10+):

```bash
python -m venv backend/.venv
# Windows (Git Bash): source backend/.venv/Scripts/activate
# Windows (PowerShell): backend\.venv\Scripts\Activate.ps1
# macOS / Linux:        source backend/.venv/bin/activate
pip install -r backend/requirements.txt

uvicorn backend.app:app --reload --port 8000
```

Then open <http://localhost:8000/health> (or <http://localhost:8000/docs> for the interactive docs).

The server needs `ml/outputs/history.json` and `ml/outputs/forecast_2026-10.json`. Those are produced by the ML
pipeline (`ml/src/forecast.py`). If your checkout does not have them, point `ML_OUTPUTS_DIR` at a folder that does:

```bash
ML_OUTPUTS_DIR="/path/to/ml/outputs" uvicorn backend.app:app --reload --port 8000
# or: cp backend/.env.example backend/.env, edit it, then
uvicorn backend.app:app --reload --port 8000 --env-file backend/.env
```

Files are read once at startup. After regenerating the ML outputs, restart the server (`--reload` only watches `.py`
files).

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ML_OUTPUTS_DIR` | `<repo root>/ml/outputs` | Folder with the ML exports. Absolute, or relative to the repo root. |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact origins allowed by CORS (no trailing slash). |
| `ALLOWED_ORIGIN_REGEX` | `https://[A-Za-z0-9.-]+\.github\.io\|https://[A-Za-z0-9.-]+\.vercel\.app` | Extra origins (full match). The default allows any GitHub Pages or Vercel deployment. |

See [`.env.example`](.env.example). Never commit a real `.env` (it is gitignored).

## Routes

All routes are `GET`, return JSON, and are gzip-compressed when the client accepts it (`/history` is 1.2 MB raw,
about 77 KB gzipped). Interactive docs: `/docs`.

| Route | Query | Returns |
|---|---|---|
| `/health` | | `{status, data_through, forecast_month, loaded_at}`. HTTP 503 with `status: "degraded"` and a `problems` list if a data file is missing or unreadable. Also answers `HEAD`. |
| `/meta` | | `meta.json` verbatim if the ML team exported it; otherwise a minimal fallback (`"fallback": true`) built from the forecast and history files. |
| `/areas` | | The 24 VPD neighbourhoods: `name`, `slug`, `render` (`polygon` or `marker`), `polygon_name` (the boundary feature to join, or `null`), `coords` (`[lat, lon]` for markers, else `null`). |
| `/history` | `month=YYYY-MM`, `area=<name or slug>`, both optional | Rows of `history.json` (same objects, same order). No filter = the whole file (6,840 rows, 2003-01 to 2026-09). |
| `/forecast` | `area=<name or slug>`, optional | Rows of `forecast_YYYY-MM.json` (24 rows, or 1 with `area`). |
| `/boundaries` | | The GeoJSON FeatureCollection (22 features, `properties.name`), `application/geo+json`. |
| `/` | | The route list. |

`area` accepts the VPD name in any case (`West End`, `west end`), the slug (`west-end`), or the polygon name
(`Downtown` for Central Business District). Filtered responses are still lists.

**Errors**

| Status | When | Body |
|---|---|---|
| 404 | `area` is not one of the 24 areas | `{"detail": "Unknown area 'atlantis'. Use a name or slug from GET /areas, ..."}` |
| 422 | `month` is not `YYYY-MM` with a month 01-12 (e.g. `2026-8`) | FastAPI's validation error, `loc: ["query", "month"]` |
| 503 | a data file was not loaded at startup | `{"detail": {"message": "...", "problems": [...]}}` |

A well-formed month outside the data (e.g. `1999-01`) returns `[]`.

**History rows include the partial month.** `2026-09` is served with `is_partial: 1` and a `null` tier, exactly as in
`history.json`. The last complete month is `2026-08` (`data_through`). Do not show 2026-09 as a complete month.

### Example responses

`GET /health`

```json
{"status": "ok", "data_through": "2026-08", "forecast_month": "2026-10", "loaded_at": "2026-10-04T10:24:49+00:00"}
```

`GET /areas` (2 of 24)

```json
[
  {"name": "Central Business District", "slug": "central-business-district", "render": "polygon", "polygon_name": "Downtown", "coords": null},
  {"name": "Stanley Park", "slug": "stanley-park", "render": "marker", "polygon_name": null, "coords": [49.3017, -123.1417]}
]
```

`GET /history?month=2026-08&area=kitsilano`

```json
[{"neighbourhood": "Kitsilano", "month": "2026-08", "weighted_index": 3523, "incident_count": 98,
  "relative_activity_tier": "below_typical", "pct_vs_typical": -5.7, "is_partial": 0}]
```

`GET /forecast?area=west-end`

```json
[{"neighbourhood": "West End", "month": "2026-10", "mode": "forecast",
  "forecast_weighted_index": 8766, "forecast_incident_count": 234, "interval_low": 5764, "interval_high": 11972,
  "relative_activity_tier": "typical", "pct_vs_typical": 3.5, "baseline_weighted_index": 8473,
  "drivers": ["Last 3 months (Jun-Aug 2026) were 2% above this area's 12-month average",
              "August 2026 was 8% above the 12-month average",
              "October 2025 was 1% below the latest 12-month average"],
  "data_through": "2026-08", "horizon_months": 2, "model": "poisson_glm"}]
```

`GET /meta` (fallback, while there is no `meta.json`)

```json
{"fallback": true, "note": "meta.json was not found in ML_OUTPUTS_DIR; these fields come from the forecast and history files.",
 "forecast_file": "forecast_2026-10.json", "forecast_month": "2026-10", "data_through": "2026-08",
 "horizon_months": 2, "model": "poisson_glm", "neighbourhood_count": 24,
 "history_first_month": "2003-01", "history_last_month": "2026-09", "partial_months": ["2026-09"]}
```

`GET /boundaries`

```json
{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [...]},
  "properties": {"name": "Arbutus Ridge", "geo_point_2d": {"lon": -123.1617, "lat": 49.2468}}}, ...]}
```

## Point the frontend at it

The frontend (`src/api.js`) reads static files from `public/data/` unless `VITE_API_URL` is set, in which case it
fetches `${VITE_API_URL}/history`, `/forecast` and `/boundaries`. In the frontend folder:

```bash
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev        # restart the dev server after changing .env.local
```

For a deployed frontend, set `VITE_API_URL` to the deployed API URL at build time, and make sure the frontend's origin
is allowed by CORS (any `https://*.github.io` or `https://*.vercel.app` already is; anything else goes in
`ALLOWED_ORIGINS`). Leaving `VITE_API_URL` unset keeps the static-file path, which is the fallback if the API is down.

## Tests

```bash
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
```

The tests build a small fixture (24 areas x 3 months) in a temp folder, so they pass on a fresh clone. They cover
every route, the `month`/`area` filters, 404/422/503, the `meta.json` fallback, gzip and CORS. A further class checks
the real exports and runs only when they are found (in `ML_OUTPUTS_DIR` or `ml/outputs/`).

## Deploy

Any host that runs a Python web process works (Render, Railway, Fly.io). From the repo root:

- Build: `pip install -r backend/requirements.txt`
- Start: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health` (returns 503 if the data files did not load)
- Environment: `ALLOWED_ORIGINS` if the frontend is not on github.io or vercel.app; `ML_OUTPUTS_DIR` only if the
  exports are not in `ml/outputs/`.

**The ML exports must be in the deployed branch.** The root `.gitignore` currently ignores `history.json` and
`forecast_2026-10.json` by name, so they are not committed unless that is changed (or they are added with
`git add -f`). Without them the API starts but `/health` reports `degraded` and `/history`, `/forecast` and `/meta`
return 503.

## Data sources

- Reported incidents: Vancouver Police Department GeoDASH open data, cleaned in `data/` and modelled in `ml/`.
  This project is not affiliated with or endorsed by the VPD; see `legal_disclaimer.txt`.
- Boundaries: City of Vancouver Open Data, "Local area boundary" (22 local areas), Open Government Licence - Vancouver.
  VPD's 24 neighbourhoods join on name, except: Central Business District = polygon `Downtown`; Stanley Park has no
  polygon (marker); Musqueam lies inside Dunbar-Southlands but is kept separate (marker, shown as insufficient data).

Wording used throughout: "reported incidents", "severity-weighted activity", "relative to this area's own history",
"uncertainty range".
