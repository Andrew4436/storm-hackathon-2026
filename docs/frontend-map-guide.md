# Guide: `frontend-map` Branch

## Your mission

Build a clear, responsive web interface that turns approved historical and forecast data into an understandable map experience.

You own `frontend/`. Begin with mock data so you are never blocked by the backend or model.

## Before coding

1. Read `00-project-brief.md`.
2. Agree on the API response schema and endpoint names with the backend owner.
3. Decide on one map library: Leaflet or Mapbox GL JS. Do not switch later.
4. Use wording approved in the project brief: relative activity, forecast, and uncertainty.

## Step-by-step work

### 1. Scaffold the core app

- Set up a minimal React/Next.js TypeScript app.
- Create a single main map page.
- Add a small mock data file matching the shared API schema.
- Ensure it starts with one documented command.

### 2. Build the required map experience

- Show Vancouver neighbourhood boundaries or an agreed area layer.
- Colour each area by historical activity or forecast tier.
- Add an accessible legend and clear selected-state style.
- On click, open an area panel with area name, value, month, tier, confidence, and drivers.

### 3. Add the historical timeline

- Implement a monthly slider/select control.
- Historical mode updates the map and detail panel.
- Forecast mode defaults to the next forecast month and clearly says it is a forecast.

### 4. Connect the API

- Replace mock fetches with the agreed backend endpoints.
- Preserve loading, empty, and error states.
- Do not hard-code backend URLs; use environment configuration.
- Verify your UI still works with the representative rows supplied by backend.

### 5. Add trust and clarity

- Include a concise information panel: what this tool does and does not do.
- Present source/limitation text supplied by ML/data owners.
- Avoid red-alert language and labels such as `dangerous`.
- Make mobile layout readable; a native app is not required.

### 6. Stretch work only after integration

- Gemini explanation panel, using only data delivered by backend.
- Category filters.
- Three-month outlook.

## Push checkpoints

1. **Early push:** app loads, mock map/data panel exists.
2. **Checkpoint 1:** historical timeline and forecast toggle work with mocks.
3. **Checkpoint 2:** API-connected map with loading/error states.
4. **Final push:** visual polish and accessibility/wording pass.

## Definition of done

- A user can select an area, view historical activity, switch to forecast, and understand the uncertainty.
- The interface never implies an individual or address is being scored.
- It runs on a phone-sized viewport and uses real API data.
