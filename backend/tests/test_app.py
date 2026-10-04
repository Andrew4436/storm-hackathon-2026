"""Tests for backend/app.py.

Run from the repo root:  python -m pytest backend/tests -q

Most tests use a small fixture written to a temp folder (24 areas x 3 months), so they pass on
a fresh clone. The last class runs against the real ML outputs when they are present
(ML_OUTPUTS_DIR, or <repo root>/ml/outputs) and is skipped otherwise.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import AREA_NAMES, BOUNDARIES_PATH, create_app, find_forecast_file, resolve_outputs_dir

MONTHS = ("2026-07", "2026-08", "2026-09")  # 2026-09 is the partial month


def forecast_row(name: str) -> dict:
    return {
        "neighbourhood": name,
        "month": "2026-10",
        "mode": "forecast",
        "forecast_weighted_index": 2140,
        "forecast_incident_count": 97,
        "interval_low": 1700,
        "interval_high": 2650,
        "relative_activity_tier": "insufficient_data" if name == "Musqueam" else "typical",
        "pct_vs_typical": None if name == "Musqueam" else 1.5,
        "baseline_weighted_index": 1980,
        "drivers": ["Last 3 months were 11% above this area's 12-month average"],
        "data_through": "2026-08",
        "horizon_months": 2,
        "model": "poisson_glm",
    }


def history_row(name: str, i: int, month: str) -> dict:
    partial = month == "2026-09"
    return {
        "neighbourhood": name,
        "month": month,
        "weighted_index": 1000 + 10 * i,
        "incident_count": 40 + i,
        "relative_activity_tier": None if partial else "typical",
        "pct_vs_typical": None if partial else -2.0,
        "is_partial": 1 if partial else 0,
    }


FORECAST = [forecast_row(n) for n in AREA_NAMES]
HISTORY = [history_row(n, i, m) for i, n in enumerate(AREA_NAMES) for m in MONTHS]


def write_outputs(folder: Path, meta: dict | None = None) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "forecast_2026-10.json").write_text(json.dumps(FORECAST), encoding="utf-8")
    (folder / "history.json").write_text(json.dumps(HISTORY), encoding="utf-8")
    if meta is not None:
        (folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return folder


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    folder = write_outputs(tmp_path_factory.mktemp("outputs"))
    with TestClient(create_app(outputs_dir=folder)) as c:
        yield c


# ---------------------------------------------------------------------------------- basics


def test_index_lists_routes(client):
    r = client.get("/")
    assert r.status_code == 200
    assert set(r.json()["routes"]) == {"/health", "/meta", "/areas", "/history", "/forecast", "/boundaries"}


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["data_through"] == "2026-08"
    assert body["forecast_month"] == "2026-10"
    assert datetime.fromisoformat(body["loaded_at"]).tzinfo is not None
    assert "problems" not in body


def test_health_head(client):
    assert client.head("/health").status_code == 200


# ---------------------------------------------------------------------------------- /areas


def test_areas(client):
    r = client.get("/areas")
    assert r.status_code == 200
    areas = r.json()
    assert [a["name"] for a in areas] == list(AREA_NAMES)
    assert len({a["slug"] for a in areas}) == 24
    by_name = {a["name"]: a for a in areas}
    assert by_name["Kensington-Cedar Cottage"]["slug"] == "kensington-cedar-cottage"
    assert by_name["Central Business District"]["polygon_name"] == "Downtown"
    for name in ("Stanley Park", "Musqueam"):
        assert by_name[name]["render"] == "marker"
        assert by_name[name]["polygon_name"] is None
        assert len(by_name[name]["coords"]) == 2
    polygons = [a for a in areas if a["render"] == "polygon"]
    assert len(polygons) == 22
    assert all(a["coords"] is None for a in polygons)


def test_area_polygon_names_match_boundaries(client):
    """Every polygon area joins to exactly one boundary feature, and vice versa."""
    polygon_names = {a["polygon_name"] for a in client.get("/areas").json() if a["render"] == "polygon"}
    feature_names = {f["properties"]["name"] for f in client.get("/boundaries").json()["features"]}
    assert polygon_names == feature_names


# ---------------------------------------------------------------------------------- /history


def test_history_all_matches_file(client):
    r = client.get("/history")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == HISTORY


def test_history_by_month(client):
    rows = client.get("/history", params={"month": "2026-08"}).json()
    assert len(rows) == 24
    assert {r["month"] for r in rows} == {"2026-08"}


def test_history_partial_month_is_served_flagged(client):
    rows = client.get("/history", params={"month": "2026-09"}).json()
    assert len(rows) == 24
    assert all(r["is_partial"] == 1 for r in rows)


@pytest.mark.parametrize("area", ["kitsilano", "Kitsilano", "KITSILANO", " kitsilano "])
def test_history_by_area_name_or_slug(client, area):
    rows = client.get("/history", params={"area": area}).json()
    assert [r["month"] for r in rows] == list(MONTHS)
    assert {r["neighbourhood"] for r in rows} == {"Kitsilano"}


@pytest.mark.parametrize("area", ["Central Business District", "central-business-district", "Downtown"])
def test_history_area_aliases(client, area):
    rows = client.get("/history", params={"area": area}).json()
    assert {r["neighbourhood"] for r in rows} == {"Central Business District"}


def test_history_by_month_and_area(client):
    rows = client.get("/history", params={"month": "2026-08", "area": "kitsilano"}).json()
    expected = [r for r in HISTORY if r["neighbourhood"] == "Kitsilano" and r["month"] == "2026-08"]
    assert rows == expected and len(rows) == 1


def test_history_month_outside_data_is_empty(client):
    r = client.get("/history", params={"month": "1999-01"})
    assert r.status_code == 200
    assert r.json() == []


def test_history_unknown_area_404(client):
    r = client.get("/history", params={"area": "atlantis"})
    assert r.status_code == 404
    assert "/areas" in r.json()["detail"]


@pytest.mark.parametrize("month", ["2026-8", "2026-13", "2026-00", "202608", "2026/08", "Aug-2026", ""])
def test_history_bad_month_422(client, month):
    r = client.get("/history", params={"month": month})
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["query", "month"]


# ---------------------------------------------------------------------------------- /forecast


def test_forecast_all_matches_file(client):
    r = client.get("/forecast")
    assert r.status_code == 200
    assert r.json() == FORECAST


@pytest.mark.parametrize("area", ["west-end", "West End", "west end"])
def test_forecast_by_area(client, area):
    rows = client.get("/forecast", params={"area": area}).json()
    assert len(rows) == 1
    assert rows[0]["neighbourhood"] == "West End"
    assert rows[0] == forecast_row("West End")


def test_forecast_unknown_area_404(client):
    assert client.get("/forecast", params={"area": "nowhere"}).status_code == 404


# ---------------------------------------------------------------------------------- /boundaries


def test_boundaries(client):
    r = client.get("/boundaries")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    geo = r.json()
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) == 22
    assert geo == json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------- /meta


def test_meta_fallback_without_meta_file(client):
    r = client.get("/meta")
    assert r.status_code == 200
    meta = r.json()
    assert meta["fallback"] is True
    assert meta["forecast_file"] == "forecast_2026-10.json"
    assert meta["forecast_month"] == "2026-10"
    assert meta["data_through"] == "2026-08"
    assert meta["horizon_months"] == 2
    assert meta["model"] == "poisson_glm"
    assert meta["neighbourhood_count"] == 24
    assert meta["history_first_month"] == "2026-07"
    assert meta["history_last_month"] == "2026-09"
    assert meta["partial_months"] == ["2026-09"]


def test_meta_file_served_verbatim(tmp_path):
    meta = {"data_through": "2026-08", "forecast_month": "2026-10", "weights_source": "StatCan CSI", "nested": {"a": [1, 2]}}
    with TestClient(create_app(outputs_dir=write_outputs(tmp_path, meta=meta))) as c:
        assert c.get("/meta").json() == meta


def test_invalid_meta_file_falls_back(tmp_path):
    folder = write_outputs(tmp_path)
    (folder / "meta.json").write_text("{not json", encoding="utf-8")
    with TestClient(create_app(outputs_dir=folder)) as c:
        assert c.get("/meta").json()["fallback"] is True
        assert c.get("/health").json()["status"] == "ok"


# ---------------------------------------------------------------------------------- loading


def test_latest_forecast_file_is_used(tmp_path):
    folder = write_outputs(tmp_path)
    (folder / "forecast_2026-07.json").write_text("[]", encoding="utf-8")
    (folder / "forecast_notes.json").write_text("{}", encoding="utf-8")
    assert find_forecast_file(folder).name == "forecast_2026-10.json"


def test_ml_outputs_dir_env(tmp_path, monkeypatch):
    folder = write_outputs(tmp_path / "custom")
    monkeypatch.setenv("ML_OUTPUTS_DIR", str(folder))
    assert resolve_outputs_dir() == folder.resolve()
    with TestClient(create_app()) as c:
        assert c.get("/history").json() == HISTORY


def test_missing_outputs_degrade_cleanly(tmp_path):
    with TestClient(create_app(outputs_dir=tmp_path / "does-not-exist")) as c:
        r = c.get("/health")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"
        assert len(body["problems"]) == 2  # forecast and history
        for path in ("/history", "/forecast", "/meta"):
            r = c.get(path)
            assert r.status_code == 503, path
            assert r.json()["detail"]["problems"]
        # Routes that do not depend on the ML outputs still work.
        assert c.get("/areas").status_code == 200
        assert c.get("/boundaries").status_code == 200


def test_nan_values_are_served_as_null(tmp_path):
    folder = write_outputs(tmp_path)
    (folder / "history.json").write_text(
        '[{"neighbourhood": "Kitsilano", "month": "2026-08", "pct_vs_typical": NaN, "is_partial": 0}]',
        encoding="utf-8",
    )
    with TestClient(create_app(outputs_dir=folder)) as c:
        r = c.get("/history")
        assert r.status_code == 200
        assert "NaN" not in r.text
        assert r.json()[0]["pct_vs_typical"] is None


def test_large_responses_are_gzipped(client):
    r = client.get("/boundaries", headers={"Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip"
    r = client.get("/boundaries", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in r.headers


# ---------------------------------------------------------------------------------- CORS


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://storm-team.github.io",
        "https://neighbourcast-git-main-team.vercel.app",
    ],
)
def test_cors_allowed_origins(client, origin):
    r = client.get("/health", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_preflight(client):
    r = client.options(
        "/history",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:3000", "https://example.com", "http://team.github.io", "https://github.io.example.com"],
)
def test_cors_other_origins_get_no_header(client, origin):
    r = client.get("/health", headers={"Origin": origin})
    assert "access-control-allow-origin" not in r.headers


def test_cors_allowed_origins_env(tmp_path, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://demo.example.org, http://localhost:4173/")
    with TestClient(create_app(outputs_dir=write_outputs(tmp_path))) as c:
        for origin in ("https://demo.example.org", "http://localhost:4173"):
            assert c.get("/health", headers={"Origin": origin}).headers.get("access-control-allow-origin") == origin
        r = c.get("/health", headers={"Origin": "http://localhost:5173"})
        assert "access-control-allow-origin" not in r.headers


# ---------------------------------------------------------------------------------- real outputs

REAL_DIR = resolve_outputs_dir()
HAVE_REAL = (REAL_DIR / "history.json").is_file() and find_forecast_file(REAL_DIR) is not None


@pytest.fixture(scope="module")
def real():
    with TestClient(create_app(outputs_dir=REAL_DIR)) as c:
        yield c


@pytest.mark.skipif(not HAVE_REAL, reason=f"real ML outputs not found in {REAL_DIR} (set ML_OUTPUTS_DIR)")
class TestRealOutputs:
    def test_health(self, real):
        body = real.get("/health").json()
        assert body["status"] == "ok"
        assert body["data_through"] == "2026-08"
        assert body["forecast_month"] == "2026-10"

    def test_forecast_covers_the_24_areas(self, real):
        rows = real.get("/forecast").json()
        assert sorted(r["neighbourhood"] for r in rows) == sorted(AREA_NAMES)
        assert rows == json.loads(find_forecast_file(REAL_DIR).read_text(encoding="utf-8"))

    def test_history_matches_file(self, real):
        rows = real.get("/history").json()
        assert len(rows) == 24 * 285
        assert {r["neighbourhood"] for r in rows} == set(AREA_NAMES)
        assert rows == json.loads((REAL_DIR / "history.json").read_text(encoding="utf-8"))

    def test_history_filter(self, real):
        rows = real.get("/history", params={"month": "2026-08", "area": "kitsilano"}).json()
        assert len(rows) == 1 and rows[0]["neighbourhood"] == "Kitsilano"
