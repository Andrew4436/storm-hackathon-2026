# Backend and integration hand-off for Andrew (and your assistant)

Written 2026-10-04, early morning, after the overnight integration. This covers `backend/`, the repo state, and
the two things only the repository owner can do. Read it top to bottom once; the first section is what an
assistant should keep in context.

## 1. Main points

- **`main` is the release.** It contains the cleaned data, the ML pipeline and its outputs, the FastAPI backend,
  the NeighbourCast frontend with data bundled, and all documents. Work from `main`:
  `git checkout main && git pull`. Do not rebase, squash or force-push `main`; the commit history is the evidence
  that all code was written inside the hackathon window.
- **Two things need the repository owner, which is you:**
  1. **Enable GitHub Pages.** Settings -> Pages -> "Build and deployment" -> Source "Deploy from a branch" ->
     Branch `gh-pages`, folder `/ (root)` -> Save. The site then appears at
     `https://andrew4436.github.io/storm-hackathon-2026/` within a minute or two. The `gh-pages` branch is already
     built from `main` with that base path. Nobody else has admin rights, and the API refused it for everyone else.
  2. **Confirm the Devpost submission** has all four members, hardware set to No, the repo link, the video link,
     and every track opt-in (list in `docs/DEVPOST.md`). Final deadline 12:00 PM today; aim for 11:40.
- **The backend is a thin FastAPI app in `backend/app.py`** that serves the ML output files unchanged: `/health`,
  `/meta`, `/areas`, `/history`, `/forecast`, `/boundaries`, plus `/docs`. It loads `ml/outputs/*.json` once at
  startup, gzips responses, and allows CORS for localhost:5173, `*.github.io` and `*.vercel.app`. 53 tests pass.
- **The demo does not depend on the backend.** The frontend ships the same JSON in `crime-tracker/public/data/`
  and switches to the API only when `VITE_API_URL` is set. Deploying the API is optional; it makes the
  architecture diagram true and is worth doing if you have 20 minutes.
- **Your CSV-to-JSON converter (`main.py` at the repo root, with `backend_README.md`) is untouched.** It is not on
  the data path, because the pipeline writes JSON directly. Keep it as a utility or move it under `tools/`; your
  call, but do not wire it between `ml/outputs` and the frontend (it would flatten list fields).
- **Branch map:** `main` (release), `data-pipeline`, `ml-forecast`, `backend-contract`, `frontend-contract`,
  `release-prep` (all merged into `main`), `gh-pages` (build artefact), and the original `backend-api` /
  `frontend-map` (superseded, keep as history).

## 2. The backend

Files: `backend/app.py`, `backend/__init__.py`, `backend/requirements.txt`, `backend/requirements-dev.txt`,
`backend/.env.example`, `backend/README.md`, `backend/static/local-area-boundary.geojson`, `backend/tests/`.

Run from the repo root:

```
pip install -r backend/requirements.txt          # fastapi, uvicorn
python -m uvicorn backend.app:app --reload --port 8000
python -m pytest backend/tests -q                # 53 passed (4 need ML_OUTPUTS_DIR to find real outputs)
curl http://localhost:8000/health
```

Environment: `ML_OUTPUTS_DIR` (default `<repo root>/ml/outputs`), `ALLOWED_ORIGINS` (comma-separated; default
`http://localhost:5173,http://127.0.0.1:5173`), `ALLOWED_ORIGIN_REGEX` (default matches github.io and vercel.app).

Routes and behaviour:

| Route | Query | Returns |
|---|---|---|
| `GET /health` (also HEAD) | | `{status, data_through, forecast_month, loaded_at}`; 503 with `problems` if a file is missing |
| `GET /meta` | | `ml/outputs/meta.json` as is |
| `GET /areas` | | 24 `{name, slug, render: polygon or marker, polygon_name, coords}` |
| `GET /history` | `month=YYYY-MM`, `area` (name, slug or "Downtown") | rows of `history.json`; 404 unknown area, 422 bad month, `[]` for a valid month outside the data |
| `GET /forecast` | `area` | rows of `forecast_2026-10.json` |
| `GET /boundaries` | | the GeoJSON, `application/geo+json` |

Files are read once at startup: restart after the ML team regenerates `ml/outputs`. `--reload` only watches `.py`.

Deploy (optional): start command `uvicorn backend.app:app --host 0.0.0.0 --port $PORT` from the repo root; health
check `/health`; Python 3.13; no database. Render's free tier sleeps after 15 minutes, so hit `/health` before each
judging slot if you use it. Then set `VITE_API_URL` on the frontend build (a rebuild is required; Vite bakes it in).

## 3. Data the backend serves (contract)

`ml/outputs/meta.json` (every number the app shows), `ml/outputs/history.json` (6,840 area-months with
`weighted_index`, `incident_count`, `pct_vs_typical`, `relative_activity_tier`, `is_partial`),
`ml/outputs/forecast_2026-10.json` (24 areas with the forecast, 80% range, `p_below / p_within / p_above`,
`most_likely`, `pct_vs_typical`, `typical_weighted_index`, `baseline_weighted_index`). Full field list in
`docs/ML_TEAM_CONTRACT.md` section 7 and `docs/HANDOFF_ML.md` section 4.

## 4. Repo housekeeping that was done tonight

- `git.ignore` renamed to `.gitignore` with fixed patterns (it had ignored nothing, and the old patterns would have
  hidden raw data).
- The 85 MB root `crimedata_csv_AllNeighbourhoods_AllYears.csv` (missing 2022) was removed from the tree; the
  source of truth is `data/raw/vancouver_crime_data.csv` (with 2022). Both blobs remain in history; that is fine.
- The empty root `00-project-debrief.md`, a stray root `package.json`/`package-lock.json` and a committed
  `node_modules/` folder (from the first frontend commit) were removed.
- `backend-api` got `main` merged into it earlier by you; `backend-contract` was cut from it and merged back into
  `main`, so nothing of yours was lost.
- Humberto's local `ml-forecast` branch received the integration merges by accident; it is a superset of `main` and
  harmless. Everyone should still work from `main`.

## 5. Known rough edges (none block the demo)

- The backend is startup-loaded; there is no file watcher. Restart after data changes.
- `meta.probability_method` is a sentence rather than a key; the frontend omits that one line. Cosmetic.
- No LICENSE file for the code. Data attributions are in the README (VPD GeoDASH, City of Vancouver Open
  Government Licence, OpenStreetMap, Esri tiles, Leaflet, Statistics Canada for the weights).
- `<app-url>` and `<api-url>` placeholders in `README.md` and `docs/DEVPOST.md` are yours to fill once Pages (and
  optionally the API) is live.

## 6. Your checklist today

1. **Enable GitHub Pages** (section 1). Open the URL on your phone and confirm the map loads.
2. `git checkout main && git pull`; run the backend tests; optionally deploy the API and set `VITE_API_URL`.
3. Fill `<app-url>` (and `<api-url>` if deployed) in `README.md` and `docs/DEVPOST.md`, commit to `main`.
4. **Freeze `main` at 9:30 AM.** After that only demo-breaking fixes, and whoever pushes must rebuild `gh-pages`
   (`cd crime-tracker && VITE_BASE=/storm-hackathon-2026/ npm run build`, copy `dist/` into the `gh-pages`
   branch, push).
5. Keep time during the pitch (roles in `docs/PITCH.md`) and warm the app before each judge group.
