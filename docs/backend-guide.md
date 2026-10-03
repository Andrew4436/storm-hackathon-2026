# Guide: `backend-api` Branch

## Your mission

Own integration: database, API, model-output loading, deployment, and keeping the full app runnable. Hardware is optional and never blocks this mission.

You own `backend/` and infrastructure configuration. You are the API-contract coordinator and final integration lead.

## Before coding

1. Read `00-project-brief.md`.
2. Publish the agreed API schema in a short backend README before frontend/ML integration.
3. Confirm file locations/schema for processed historical data and forecast output.
4. Prefer a small, reliable API over a complicated infrastructure stack.

## Step-by-step work

### 1. Scaffold the service

- Create a minimal FastAPI service with health endpoint: `GET /health`.
- Add CORS for the local/deployed frontend.
- Provide a development command and environment-variable example.
- Return mock map data immediately so frontend can integrate early.

### 2. Set up data storage

- Create PostgreSQL/Tiger Data tables for monthly area aggregates and forecast results.
- Keep the schema small: area, month, count/category values, forecast fields.
- Write a repeatable loader from data/ML outputs into the database.
- For the hackathon, a preloaded snapshot is sufficient; real-time refresh is not required.

### 3. Implement read endpoints

Suggested endpoints:

```text
GET /health
GET /areas
GET /history?month=YYYY-MM
GET /forecast?month=YYYY-MM
GET /areas/{area}/summary?month=YYYY-MM
```

Return the exact shared schema. Validate parameters and return understandable errors.

### 4. Integrate real files

- First load the processed historical dataset.
- Then load the baseline forecast output.
- Later swap/add the ML forecast export without changing frontend fields.
- Keep a small fallback fixture so the demo can still run if a data service fails.

### 5. Test the whole path

- Test each endpoint locally.
- Pair with frontend owner to verify real map rendering.
- Make sure deployed frontend can reach deployed API.
- Confirm source/limitations text appears in the product.

### 6. Deployment and optional Gemini

- Deploy only once local integration works.
- Store keys in environment variables; never commit them.
- Add Gemini only after the core app is stable. It can explain API-provided tier/drivers and limitations; it must not generate unsupported safety advice.

## Push checkpoints

1. **Early push:** health endpoint, README, mock endpoint.
2. **Checkpoint 1:** stable API contract and frontend connected to mocks.
3. **Checkpoint 2:** database/data loader and real historical endpoint.
4. **Checkpoint 3:** forecast endpoint, deployment instructions, fallback behaviour.

## Definition of done

- Frontend receives predictable historical and forecast responses.
- A fresh teammate can start the service from the README.
- The app is deployed or has a robust local demo path.
- No API key or sensitive configuration is committed.
