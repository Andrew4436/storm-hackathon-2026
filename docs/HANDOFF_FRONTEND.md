# Frontend hand-off for James (and your assistant)

Written 2026-10-04, early morning, after the overnight integration. This is the catch-up for `crime-tracker/`.
Read it top to bottom once; the first section is what an assistant should keep in context.

## 1. Main points

- **`main` is the release.** Your `frontend-map` branch (the first prototype) is superseded. The app on `main` is a
  rewrite called **NeighbourCast** in `crime-tracker/`. Work from `main` from now on:
  `git checkout main && git pull && cd crime-tracker && npm install && npm run dev`. Do not rebase or force-push.
- **Same stack as your prototype:** Vite, React 19, react-leaflet 5, Leaflet, plain JSX (no TypeScript). Dark theme,
  Fraunces for display type, Public Sans for UI, loaded from Google Fonts with fallbacks.
- **The map is a full-screen choropleth of the 22 official City of Vancouver local-area polygons**, with Stanley Park
  and Musqueam drawn as circle markers (they have no polygon). VPD "Central Business District" maps to the polygon
  named "Downtown". The mapping lives in `src/areas.js`.
- **Colour is continuous, not tiered.** One teal-grey-amber scale (`src/scale.js`). Forecast mode: chance above
  minus chance below the area's level in the same month a year earlier. Historical mode: the realised deviation
  from the same month a year earlier, saturating at 30%. Insufficient data (Musqueam) is hatched.
- **Every number and label comes from the pipeline's `public/data/meta.json`.** Never hard-code a month, a
  threshold or an evaluation figure; read it from `meta` (with `META_DEFAULTS` in `src/config.js` as the fallback).
  To refresh data after the ML team regenerates outputs: `npm run sync-data` (copies `ml/outputs/*` into
  `public/data/`).
- **Hover cards are React-controlled.** There is no react-leaflet `<Tooltip>` anywhere, on purpose: Leaflet tooltips
  got stuck on screen when layers restyled. Do not reintroduce them. The single `HoverCard` follows the cursor and
  clears on mouseout.
- **Wording rule (hard):** never "crime risk", "safety score", "safe", "unsafe", "dangerous", "good/bad", "predict
  crime". The only allowed "safety" is inside VPD's verbatim caution sentence in the limitations paragraph.
- **Deploy:** `npm run build` for a root-path host; `VITE_BASE=/storm-hackathon-2026/ npm run build` for GitHub
  Pages (the `gh-pages` branch already holds that build; Andrew has to switch Pages on in the repo settings).

## 2. What is in the app now (component map)

```
main.jsx            document title/description from meta; ErrorBoundary around App
App.jsx             mode (historical | forecast), month, selected area, Play, URL state (?mode&month&area),
                    loading and error pages, Escape closes, focus return
MapStage.jsx        full-bleed stage: hover state, hatch pattern, measures the floating panels for the map fit
MapView.jsx         Esri dark basemap (+ OSM fallback), one GeoJSON layer (stable key, restyled via setStyle),
                    two circle markers, fade-in on load, FitToAreas (validated padding, waits for a sized container)
ControlBar.jsx      Historical | Forecast, month label (fixed-width column), How this works, area <select>,
                    Play months / Pause, previous / next, range slider
legend.jsx          gradient bar with a precise title ("Chance that October 2026 ends more than 10% above or below
                    this area's October 2025 level"), ends "Quieter" / "Busier", middle "Even odds" or "Same",
                    "Insufficient data" and conditional "No reference yet" swatches   (file name is lower case)
HoverCard.jsx       one floating card: name, chance line or deviation, figures, 12-month mini sparkline
Drawer.jsx          right drawer (desktop) / bottom sheet with sticky header (mobile); inert when closed
AreaDetail.jsx      area name, month, big number, incident estimate, range bar with baseline tick,
                    below/within/above chances bar + sentence, "Most likely: ...", 36-month Sparkline
HowItWorks.jsx      what it does / does not do, probabilities explainer, the performance block (from meta),
                    why September 2026 is excluded, the verbatim limitations paragraph, attribution
Sparkline.jsx, Swatch.jsx, Icons.jsx, ErrorBoundary.jsx
api.js              loads meta.json first, then history.json, forecast_<month>.json and the GeoJSON in parallel;
                    validates meta field by field; builds per-area series and lookup maps; VITE_API_URL support
areas.js            24 VPD names -> polygon name / marker coords / slug
scale.js            colourFor(v in [-1, 1]) in OKLab, fillFor(record), gradient for the legend
format.js           month labels, number formatting, reference-month helpers (same month a year earlier),
                    chance sentences, deviation text
config.js           FIRST_MONTH 2003-01, SLIDER_START 2004-01, META_DEFAULTS, SCALE, labels, LIMITATIONS text
```

Data files in `public/data/`: `meta.json`, `history.json` (6,840 rows), `forecast_2026-10.json` (24 rows),
`local-area-boundary.geojson` (22 polygons, City of Vancouver Open Data). `.nojekyll` is in `public/` so Pages
serves the `assets/` folder.

## 3. What changed versus your prototype

- The `//` comments inside JSX (they rendered as page text), the "Red = Bad / Green = Good" legend, the random
  polygon colours, the year-only slider, the hand-traced polygons and the test markers are all gone.
- Official boundaries replace `van_neighbourhood_polygon.json`; your centre coordinates were used for the two
  markers and then the file was removed.
- A month slider (January 2004 to August 2026, September 2026 excluded as a partial month) with Play, a forecast
  mode fixed to October 2026, a detail drawer, a How-this-works sheet, loading/error states, bookmarkable URLs,
  keyboard access (controls before the map in tab order, visible focus, Escape), reduced-motion support, 44px tap
  targets on phones, no horizontal scroll at 375px.
- Design: full-bleed dark harbour map with floating frosted panels; one radius for surfaces, one for chips; no
  gradients except the legend bar; no icon library (inline SVG).
- Several bugs fixed along the way: stuck tooltips (removed Leaflet tooltips), a NaN crash in `fitBounds` when the
  container had no size (now guarded, plus an ErrorBoundary), the selection effect replaying the load animation,
  focus lost when the drawer closed, the attribution bar clipped by the zoom-control gutter.

## 4. Data contract you consume

Forecast record (one per area): `neighbourhood, month, forecast_weighted_index, forecast_incident_count,
interval_low, interval_high, typical_weighted_index, pct_vs_typical, baseline_weighted_index, p_below, p_within,
p_above (sum to 1; null for insufficient_data), most_likely, relative_activity_tier (= most_likely; use only to
detect insufficient_data), data_through, horizon_months, model`. The reference level is the same month one year
earlier (meta: `tier_reference: "seasonal"`, `tier_window_months: 12`, band `tier_thresholds_pct: [-10, 10]`).

History record (one per area-month): `neighbourhood, month, weighted_index, incident_count, pct_vs_typical (null
where there is no reference, for the partial month, and for Musqueam), relative_activity_tier, is_partial`.

`meta.json`: `data_through, forecast_month, horizon_months, tier_* , interval_level, model, model_description,
evaluation {wape_pct, improvement_vs_mean_12_pct, interval_coverage_pct, tier_accuracy_pct,
tier_majority_baseline_pct, probabilistic {brier_above, brier_above_baseline, rps, rps_baseline, rps_hard_tier,
reliability_above[], reliability_below[], statement}}`. `api.js` validates each field and falls back per field.

Backend option: set `VITE_API_URL=http://localhost:8000` in `.env.local`; `api.js` then calls `/meta`, `/history`,
`/forecast`, `/boundaries` on `backend/app.py`, which return the same shapes.

## 5. Commands

```
npm install
npm run dev                                   # http://localhost:5173
npx eslint .
npm run build                                 # root-path build -> dist/
VITE_BASE=/storm-hackathon-2026/ npm run build # GitHub Pages build (vite.config.js normalises the Git Bash path mangling)
npm run sync-data                             # copy ../ml/outputs/{meta,history,forecast_<month>}.json into public/data
npm run preview                               # serve dist/
```

## 6. Known rough edges (none block the demo)

- The Stanley Park marker can touch the bottom of the control bar at some window sizes; the fit uses its centre,
  not its radius.
- The legend panel reserves two lines for its title in both modes so the map does not refit during Play; one-line
  historical titles leave a blank line.
- The calibration sentence in How this works comes verbatim from `meta.json` and still says "its usual level";
  everything else names the reference month. Changing it means a pipeline rerun.
- `meta.probability_method` is a sentence; the UI only maps the keys `kde`/`lognormal` to a friendly name, so the
  method line is simply omitted. Cosmetic.
- `legend.jsx` is lower case in git; its import matches. Keep it lower case or rename with `git mv` (Linux builds are
  case-sensitive).
- Basemap is Esri World Dark Gray (keyless). CARTO now needs a key. Attribution is in the map and in How this works.
- Placeholders left for you: `<app-url>` in `README.md` and `docs/DEVPOST.md`, and `docs/screenshot.png`.

## 7. Your checklist today

1. `git checkout main && git pull`, then run it and click through both modes, Play, the drawer, How this works, and
   the phone width (375px).
2. Take the screenshots for Devpost (desktop and phone) and save one as `docs/screenshot.png`.
3. Drive the demo laptop at judging: the bookmarked URL states are listed in `docs/PITCH.md`. Warm the app before
   each judge group and keep `npm run preview` ready as the offline fallback.
4. If anything in the UI must change, keep the wording rule and run `npx eslint . && npm run build` before pushing
   to `main`. Tell whoever deploys, because the `gh-pages` branch is a build artefact and has to be rebuilt.
