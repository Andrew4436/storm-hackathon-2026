# NeighbourCast

NeighbourCast is a map of Vancouver's 24 VPD neighbourhoods that asks one question: is this month unusual for this neighbourhood? It shows reported incidents from Vancouver Police Department open data for every month from January 2003 to August 2026. Each area is coloured below typical, typical or above typical relative to this area's own history, never against other areas. It also forecasts October 2026, with an 80% uncertainty range and the simple baseline the forecast had to beat. Built at StormHacks 2026.

## The question it answers

> Is this month unusual for this neighbourhood, compared with its own past?

- Every colour compares an area only with its own trailing 36 complete months.
- The smallest unit is one neighbourhood in one month. No streets, addresses or people.
- It does not rank neighbourhoods and does not rate places to live or visit.

![NeighbourCast in forecast mode for October 2026, with the drawer open](docs/screenshot.png)
<!-- add docs/screenshot.png (1920x1080 capture of forecast mode with the drawer open) before submission -->

Live app: `<app-url>` · Demo video: `<video-url>` · Repo: https://github.com/Andrew4436/storm-hackathon-2026

## What the app does

- **Historical mode:** pick any complete month from 2003-01 to 2026-08 with the slider or arrows, or press **Play months**.
- **Forecast mode:** October 2026, forecast from data through August 2026 (a two-month horizon, because September 2026 is incomplete).
- **Drawer:** severity-weighted activity, the plain count of reported incidents, the uncertainty range, the 12-month average, and a 36-month sparkline.
- **How this works:** method, limitations, evaluation and sources, inside the app.
- **Shareable views:** the state lives in the URL, for example `/?mode=forecast&area=kitsilano`.
- **Small areas:** Stanley Park and Musqueam have no City boundary shape, so they are drawn as circles. Musqueam shows "insufficient data".

## Architecture

```text
VPD GeoDASH open data (CSV)                 City of Vancouver Open Data
all-years export + separate 2022 download   local-area-boundary (GeoJSON, 22 polygons)
            |                                              |
            v                                              |
data/stormhacks2026_data_cleaning.ipynb                    |
  962,117 rows -> 942,457 rows                             |
            |                                              |
            v                                              |
data/processed/neighbourhood_monthly.csv                   |
  24 neighbourhoods x 285 months = 6,840 rows              |
            |                                              |
            v                                              |
ml/src/build_features.py -> evaluate.py -> forecast.py     |
  baselines, Poisson GLM, Random Forest, backtest,         |
  80% ranges, tiers                                        |
            |                                              |
            +--> reports/evaluation.md                     |
            v                                              |
ml/outputs/history.json, forecast_2026-10.json             |
            |                                              |
     +------+-----------------------+                      |
     v                              v                      |
backend/ (FastAPI)          crime-tracker/public/data/ <---+
  /history /forecast          (static copy, the default)
  /boundaries                       |
     |                              |
     +-------------+----------------+
                   v
crime-tracker/ (Vite + React + Leaflet): the NeighbourCast map
```

Nothing is recomputed at request time. The backend and the static files serve the same JSON shapes.

## How to run each part

All paths are relative to the repo root. Data and ML were developed on Python 3.13. The frontend needs a current Node.js LTS.

### 1. Data notebook (optional: the output is committed)

```bash
cd data
pip install pandas numpy matplotlib jupyter ipykernel
python -m jupyter nbconvert --to notebook --execute --inplace stormhacks2026_data_cleaning.ipynb
```

- Input: `data/raw/vancouver_crime_data.csv`. Output: `data/processed/neighbourhood_monthly.csv`.
- The working directory must be `data/`. It takes about a minute.
- The last cell asserts the output sums to 942,457 incidents, overall and per type.
- Do not use the root file `crimedata_csv_AllNeighbourhoods_AllYears.csv`: it has no 2022.

### 2. ML pipeline

```bash
pip install -r ml/requirements.txt
python ml/src/build_features.py
python ml/src/evaluate.py
python ml/src/forecast.py
```

- Run the three commands in this order, from the repo root. The whole pipeline takes about 30 seconds and is deterministic.
- Outputs: `ml/outputs/history.json`, `ml/outputs/forecast_2026-10.json` and `reports/evaluation.md`.
- Every setting (weights, horizon, folds, tier window and thresholds) lives in `ml/config.py`.

### 3. Backend (optional: the app runs on static files without it)

```bash
# run from the repo root
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000
```

- Check http://localhost:8000/health. The app reads `/history`, `/forecast` and `/boundaries`.
- It serves the files from `ml/outputs/` as they are.

### 4. Frontend

```bash
cd crime-tracker
npm install
npm run dev        # http://localhost:5173
```

- By default it reads `crime-tracker/public/data/`. To use the backend, put `VITE_API_URL=http://localhost:8000` in `crime-tracker/.env.local`.
- After re-running the ML pipeline, copy the outputs into the app (PowerShell: `Copy-Item`):
  `cp ml/outputs/history.json ml/outputs/forecast_2026-10.json crime-tracker/public/data/`
- Production build: `npm run build`, then `npm run preview` (http://localhost:4173).
- Dates shown in the app come from `crime-tracker/src/config.js`.

## Branch map

| Branch | Owner | Holds |
|---|---|---|
| `main` | Andrew | The release: everything merged, this README, `docs/` |
| `data-pipeline` | Humberto | `data/`: raw CSV, cleaning notebook, processed CSV, data README |
| `ml-forecast` | Chibueze | `ml/` and `reports/evaluation.md` |
| `backend-contract` | Andrew | `backend/`: the FastAPI service |
| `frontend-contract` | James | `crime-tracker/`: the map app |

The team contract is `docs/ML_TEAM_CONTRACT.md`. Data rules are in `data/README.md`.

## Data provenance

- **Source:** VPD GeoDASH open data, https://geodash.vpd.ca/opendata/, downloaded 2026-10-03.
- **The missing year:** VPD's all-years export (927,794 rows) has no 2022. A separate 2022 download (34,323 rows) was merged in: 962,117 rows in total.
- **Coverage:** 2003-01-01 to 2026-09-25. September 2026 holds about 70% of a normal month, so it is flagged `is_partial` and never used for training, evaluation or display.
- **Cleaning:** 962,117 rows to 942,457. We dropped 106 rows with no neighbourhood, plus homicide and both vehicle collision types (collisions were recorded differently from 2014).
- **No de-duplication:** 42% of Offence Against a Person rows are exact copies because VPD redacts their time and location. They are separate incidents.
- **Targets:** a severity-weighted index (per-type weights following the Statistics Canada Crime Severity Index approach) and the plain count of reported incidents.
- **Map join:** VPD "Central Business District" is the City polygon "Downtown". Musqueam is never merged into Dunbar-Southlands.

## Disclaimer

- NeighbourCast is not affiliated with or endorsed by the Vancouver Police Department.
- VPD cautions against using this data to judge the safety of a specific location.
- The data shows reported, founded incidents. Some incidents are never reported, and recent months can be revised.
- VPD's full legal disclaimer is in `legal_disclaimer.txt`. The in-app limitations text is in `data/README.md`.
- Figures here are not comparable to Statistics Canada crime statistics.

## Evaluation summary

<!-- refresh from reports/evaluation.md -->
- **Shipped model:** a Poisson GLM, picked by a rule fixed before the final run: lower pooled MAE on the severity-weighted index (GLM 559.9, Random Forest 611.6) over 20 held-out months, 2025-01 to 2026-08.
- **Against a plain 12-month average (585.1):** only 4.3% lower error on the index (3.2% on the count), better in 14 of 24 areas, and worse in 2026-01 to 2026-08 (528.7 vs 494.8). The app shows that average beside every forecast.
- **Uncertainty:** the 80% range comes from backtest ratios. Using fold A ratios, it covered 79.7% of fold B outcomes. Tier accuracy is not presented as skill. Full tables are in `reports/evaluation.md`.

## Team

| Person | Role |
|---|---|
| Humberto | Data cleaning, integration, this release |
| Chibueze | ML: features, models, evaluation, uncertainty ranges |
| James | Frontend: the NeighbourCast map app |
| Andrew | Backend, deployment, repo owner |

## Attribution and licences

- **Incident data:** Vancouver Police Department, GeoDASH open data. Used under VPD's terms and disclaimer (`legal_disclaimer.txt`). No VPD logos are used.
- **Boundaries:** City of Vancouver Open Data, "local-area-boundary". Contains information licensed under the Open Government Licence – Vancouver.
- **Map data:** © OpenStreetMap contributors, available under the Open Database Licence (fallback basemap).
- **Basemap tiles:** Esri World Dark Gray Canvas, © Esri and its data providers.
- **Map library:** Leaflet (BSD 2-Clause licence), with react-leaflet.
- **Severity weights:** follow the Statistics Canada Crime Severity Index approach. NeighbourCast's index is not a Statistics Canada statistic.
