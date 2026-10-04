# Vancouver Safety Forecast Map — Project Brief

## The product

Build a responsive Vancouver web app that lets people explore **historical reported-incident activity** and see an **area-level forecast for the next month**. It is intended for travellers and prospective residents who want context before visiting or moving to an area.

The central experience is an interactive Vancouver map: choose a historical month with a timeline slider, or switch to a forecast layer for the next month. Selecting a neighbourhood shows historical activity, a forecast tier, uncertainty, and a plain-language explanation.

## The claim we can honestly make

The app forecasts patterns in *reported incidents at neighbourhood level*. It does not predict individual behaviour, identify people or properties, label neighbourhoods as safe/unsafe, or make recommendations for law enforcement.

Use language such as **"relative reported-incident activity"**, **"forecast tier"**, and **"uncertainty"**. Always show that reported data can be delayed, revised, incomplete, and affected by reporting practices.

## MVP: required by demo time

- Vancouver neighbourhood map with a historical monthly layer.
- Timeline control to inspect historical months.
- One-month forecast layer for every neighbourhood.
- One baseline forecast and one simple ML forecast (or a clearly documented baseline if ML does not outperform it).
- A time-based evaluation result.
- Risk tier, uncertainty, and 1–2 explanation drivers on area selection.
- A responsive deployed web app or a reliable local demo.

## Not required for MVP

- Native mobile app.
- Street/address-level scores.
- Live data ingestion.
- Three-month forecasting (stretch only; label it lower confidence).
- Weather, transit, and infrastructure features (stretch only).
- Hardware.
- Gemini chat. Add it only after the map and forecast work; it may explain approved model outputs, not invent risk claims.

## Data and model contract

Source: VPD GeoDASH downloadable open data. Do not scrape monthly PDFs. The data pipeline aggregates incidents by `neighbourhood × month × selected category`.

Prediction target: next month’s count of selected reported incidents for a neighbourhood. The UI converts the forecast to a **relative tier** based on the neighbourhood’s own historic distribution, not a universal safety label.

Minimum API response:

```json
{
  "area": "Kitsilano",
  "month": "2026-11",
  "historical_count": 42,
  "forecast_count": 47,
  "risk_tier": "moderate",
  "confidence": "medium",
  "drivers": ["Recent 3-month trend above baseline", "Seasonal pattern"]
}
```

## Repository boundaries

| Branch | Folder ownership | Owner |
|---|---|---|
| `data-pipeline` | `data/raw`, `data/processed`, `data/README.md` | Data/feature owner |
| `ml-forecast` | `ml`, `reports` | ML/model owner |
| `frontend-map` | `frontend` | Frontend owner |
| `backend-api` | `backend`, infrastructure configuration | Backend/integration owner |

Do not edit another owner’s primary folder without asking them first. Shared changes (root README, API schema) are agreed in chat before editing.

## Team rhythm

1. **First 45 minutes:** agree on neighbourhood list, included incident categories, target month format, API schema, and demo story.
2. **Hour 4 integration checkpoint:** map consumes the API, even if the API returns mocked data.
3. **Hour 7 integration checkpoint:** API serves real historical data and baseline forecast output.
4. **Final hours:** evaluate, polish, deploy, rehearse. Do not start a core feature late.

## Git rules

- `main` should always be runnable.
- Make small commits with one purpose each.
- Push after each completed, testable milestone—not one enormous final push.
- Before starting a task, pull/rebase from `main`; before merging, verify the app still runs.
- Open a pull request or ask the integration owner to review before merging a feature branch.
- The backend/integration owner coordinates API-contract changes and final merges.
