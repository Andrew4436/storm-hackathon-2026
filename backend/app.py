"""NeighbourCast API: read-only access to the ML team's exported files.

Everything is read into memory once at startup:

- ``forecast_YYYY-MM.json``, ``history.json`` and (optional) ``meta.json`` from ``ML_OUTPUTS_DIR``
  (default: ``<repo root>/ml/outputs``), as specified in docs/ML_TEAM_CONTRACT.md section 7;
- ``backend/static/local-area-boundary.geojson`` (City of Vancouver local-area polygons).

Requests only filter what was loaded; nothing is recomputed per request. Response bodies have
the same shape as the static files, so the frontend switches between the two by setting
``VITE_API_URL``.

Run from the repo root:  uvicorn backend.app:app --reload --port 8000
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

log = logging.getLogger("uvicorn.error")

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
DEFAULT_OUTPUTS_DIR = REPO_ROOT / "ml" / "outputs"
BOUNDARIES_PATH = BACKEND_DIR / "static" / "local-area-boundary.geojson"

DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
# Any GitHub Pages or Vercel deployment of the frontend (matched against the whole Origin header).
DEFAULT_ALLOWED_ORIGIN_REGEX = r"https://[A-Za-z0-9.-]+\.github\.io|https://[A-Za-z0-9.-]+\.vercel\.app"

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
FORECAST_FILE_RE = re.compile(r"^forecast_\d{4}-(0[1-9]|1[0-2])\.json$")
JSON_TYPE = "application/json"
GEOJSON_TYPE = "application/geo+json"

# The 24 VPD neighbourhoods (data/README.md), in the order the data files use.
AREA_NAMES: tuple[str, ...] = (
    "Arbutus Ridge", "Central Business District", "Dunbar-Southlands", "Fairview",
    "Grandview-Woodland", "Hastings-Sunrise", "Kensington-Cedar Cottage", "Kerrisdale",
    "Killarney", "Kitsilano", "Marpole", "Mount Pleasant", "Musqueam", "Oakridge",
    "Renfrew-Collingwood", "Riley Park", "Shaughnessy", "South Cambie", "Stanley Park",
    "Strathcona", "Sunset", "Victoria-Fraserview", "West End", "West Point Grey",
)
# Map join (data/README.md "Map join notes"): 22 areas are City of Vancouver polygons.
# Stanley Park has no polygon; Musqueam lies inside Dunbar-Southlands but is a separate VPD
# area and is never merged into it. Both are drawn as markers at these [lat, lon] points
# (the same points as the frontend's src/areas.js).
MARKERS: dict[str, list[float]] = {
    "Stanley Park": [49.3017, -123.1417],
    "Musqueam": [49.225, -123.2],
}
POLYGON_RENAMES = {"Central Business District": "Downtown"}


def slugify(name: str) -> str:
    """'Central Business District' -> 'central-business-district' (same rule as the frontend)."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


AREAS: list[dict[str, Any]] = [
    {
        "name": name,
        "slug": slugify(name),
        "render": "marker" if name in MARKERS else "polygon",
        "polygon_name": None if name in MARKERS else POLYGON_RENAMES.get(name, name),
        "coords": MARKERS.get(name),
    }
    for name in AREA_NAMES
]

# Lookup keys for ?area=: the VPD name (any case), the slug, and the polygon name ("Downtown").
_AREA_KEYS: dict[str, str] = {}
for _a in AREAS:
    _AREA_KEYS[_a["name"].lower()] = _a["name"]
    _AREA_KEYS[_a["slug"]] = _a["name"]
    if _a["polygon_name"]:
        _AREA_KEYS[_a["polygon_name"].lower()] = _a["name"]


def resolve_area(value: str) -> str:
    """Return the VPD neighbourhood name for a name, slug or polygon name, or raise 404."""
    key = value.strip().lower()
    name = _AREA_KEYS.get(key) or _AREA_KEYS.get(slugify(key))
    if name is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown area {value!r}. Use a name or slug from GET /areas, e.g. 'West End' or 'west-end'.",
        )
    return name


# --------------------------------------------------------------------------------------------
# Loading (startup only)
# --------------------------------------------------------------------------------------------


def _replace_non_finite(obj: Any) -> Any:
    """NaN/Infinity are not valid JSON for browsers; serve them as null."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, list):
        return [_replace_non_finite(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _replace_non_finite(v) for k, v in obj.items()}
    return obj


def dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    try:
        dumps(data)
    except ValueError:
        log.warning("%s contains NaN or Infinity; serving those values as null.", path.name)
        data = _replace_non_finite(data)
    return data


def _rows_ok(data: Any, keys: tuple[str, ...]) -> bool:
    return isinstance(data, list) and all(isinstance(r, dict) and all(k in r for k in keys) for r in data)


def find_forecast_file(outputs_dir: Path) -> Path | None:
    """The latest forecast_YYYY-MM.json in the outputs folder, or None."""
    if not outputs_dir.is_dir():
        return None
    files = sorted(p for p in outputs_dir.iterdir() if FORECAST_FILE_RE.match(p.name))
    return files[-1] if files else None


def resolve_outputs_dir(explicit: str | Path | None = None) -> Path:
    raw = explicit if explicit is not None else os.environ.get("ML_OUTPUTS_DIR", "").strip()
    if not raw:
        return DEFAULT_OUTPUTS_DIR
    path = Path(raw).expanduser()
    # A relative ML_OUTPUTS_DIR is read from the repo root, wherever the server is started.
    return (path if path.is_absolute() else REPO_ROOT / path).resolve()


@dataclass
class Store:
    """Everything the routes serve, read once at startup."""

    outputs_dir: Path
    loaded_at: str
    problems: list[str] = field(default_factory=list)
    forecast_file: str | None = None
    forecast: list[dict[str, Any]] | None = None
    forecast_bytes: bytes = b""
    forecast_by_area: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    history: list[dict[str, Any]] | None = None
    history_bytes: bytes = b""
    history_by_area: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    history_by_month: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    meta_bytes: bytes | None = None
    meta_is_fallback: bool = True
    boundaries_bytes: bytes | None = None
    data_through: str | None = None
    forecast_month: str | None = None


def build_fallback_meta(store: Store) -> dict[str, Any]:
    """A minimal /meta body used when the ML team has not exported meta.json."""
    first = store.forecast[0] if store.forecast else {}
    months = sorted(store.history_by_month)
    partial = sorted({r["month"] for r in store.history or [] if r.get("is_partial") == 1})
    return {
        "fallback": True,
        "note": "meta.json was not found in ML_OUTPUTS_DIR; these fields come from the forecast and history files.",
        "forecast_file": store.forecast_file,
        "forecast_month": first.get("month"),
        "data_through": first.get("data_through"),
        "horizon_months": first.get("horizon_months"),
        "model": first.get("model"),
        "neighbourhood_count": len(store.forecast_by_area),
        "history_first_month": months[0] if months else None,
        "history_last_month": months[-1] if months else None,
        "partial_months": partial,
    }


def load_store(outputs_dir: Path, boundaries_path: Path = BOUNDARIES_PATH) -> Store:
    store = Store(outputs_dir=outputs_dir, loaded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))

    # Forecast: one object per neighbourhood (docs/ML_TEAM_CONTRACT.md section 7).
    path = find_forecast_file(outputs_dir)
    if path is None:
        store.problems.append(f"No forecast_YYYY-MM.json found in {outputs_dir}")
    else:
        try:
            data = _read_json(path)
        except (OSError, ValueError) as e:
            store.problems.append(f"{path.name} could not be read: {e}")
        else:
            if not data or not _rows_ok(data, ("neighbourhood", "month")):
                store.problems.append(f"{path.name} is not a non-empty list of objects with 'neighbourhood' and 'month'")
            else:
                store.forecast_file = path.name
                store.forecast = data
                store.forecast_bytes = dumps(data)
                for row in data:
                    store.forecast_by_area.setdefault(row["neighbourhood"], []).append(row)
                store.forecast_month = data[0].get("month")
                store.data_through = data[0].get("data_through")
                if len({(r.get("month"), r.get("data_through")) for r in data}) > 1:
                    log.warning("%s rows disagree on month/data_through; reporting the first row's.", path.name)

    # History: one object per neighbourhood-month, including the partial month (is_partial = 1).
    path = outputs_dir / "history.json"
    if not path.is_file():
        store.problems.append(f"history.json not found in {outputs_dir}")
    else:
        try:
            data = _read_json(path)
        except (OSError, ValueError) as e:
            store.problems.append(f"history.json could not be read: {e}")
        else:
            if not _rows_ok(data, ("neighbourhood", "month")):
                store.problems.append("history.json is not a list of objects with 'neighbourhood' and 'month'")
            else:
                store.history = data
                store.history_bytes = dumps(data)
                for row in data:
                    store.history_by_area.setdefault(row["neighbourhood"], []).append(row)
                    store.history_by_month.setdefault(row["month"], []).append(row)

    unknown = (set(store.forecast_by_area) | set(store.history_by_area)) - set(AREA_NAMES)
    if unknown:
        log.warning("Data names not in the 24 VPD neighbourhoods (not reachable via ?area=): %s", sorted(unknown))

    # Meta: optional. Served verbatim when present, otherwise a fallback built from the files above.
    path = outputs_dir / "meta.json"
    if path.is_file():
        try:
            meta = _read_json(path)
            if not isinstance(meta, dict):
                raise ValueError("expected a JSON object")
        except (OSError, ValueError) as e:
            log.warning("meta.json ignored (%s); serving the fallback.", e)
        else:
            store.meta_bytes = dumps(meta)
            store.meta_is_fallback = False
    if store.meta_bytes is None and store.forecast is not None:
        store.meta_bytes = dumps(build_fallback_meta(store))

    # Boundaries: shipped with the backend, served as-is.
    try:
        geo = json.loads(Path(boundaries_path).read_text(encoding="utf-8-sig"))
        if not isinstance(geo, dict) or not isinstance(geo.get("features"), list):
            raise ValueError("not a GeoJSON FeatureCollection")
    except (OSError, ValueError) as e:
        store.problems.append(f"{Path(boundaries_path).name} could not be read: {e}")
    else:
        store.boundaries_bytes = dumps(geo)

    for p in store.problems:
        log.error("Data problem: %s", p)
    log.info(
        "Loaded %s history rows and %s forecast rows from %s (meta: %s)",
        len(store.history or []),
        len(store.forecast or []),
        outputs_dir,
        "none" if store.meta_bytes is None else "fallback" if store.meta_is_fallback else "meta.json",
    )
    return store


# --------------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------------

router = APIRouter()


def _store(request: Request) -> Store:
    return request.app.state.store


def _unavailable(what: str, store: Store) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"message": f"The {what} is not loaded. See GET /health.", "problems": store.problems},
    )


def _json(body: bytes | list | dict) -> Response:
    return Response(content=body if isinstance(body, bytes) else dumps(body), media_type=JSON_TYPE)


@router.get("/", summary="List the routes")
def index() -> dict[str, Any]:
    return {
        "name": "NeighbourCast API",
        "docs": "/docs",
        "routes": ["/health", "/meta", "/areas", "/history", "/forecast", "/boundaries"],
    }


@router.api_route("/health", methods=["GET", "HEAD"], summary="Service status and the data snapshot it serves")
def health(request: Request) -> JSONResponse:
    store = _store(request)
    body: dict[str, Any] = {
        "status": "degraded" if store.problems else "ok",
        "data_through": store.data_through,
        "forecast_month": store.forecast_month,
        "loaded_at": store.loaded_at,
    }
    if store.problems:
        body["problems"] = store.problems
    return JSONResponse(body, status_code=503 if store.problems else 200)


@router.get("/meta", summary="meta.json, or a minimal fallback built from the forecast file")
def meta(request: Request) -> Response:
    store = _store(request)
    if store.meta_bytes is None:
        raise _unavailable("meta file (and the forecast file it falls back to)", store)
    return _json(store.meta_bytes)


@router.get("/areas", summary="The 24 VPD neighbourhoods with a slug and how the map draws each")
def areas() -> list[dict[str, Any]]:
    return AREAS


@router.get("/history", summary="Monthly history rows (history.json), optionally filtered")
def history(
    request: Request,
    month: Annotated[str | None, Query(pattern=MONTH_PATTERN, description="YYYY-MM, e.g. 2026-08")] = None,
    area: Annotated[str | None, Query(description="Name or slug from /areas, e.g. 'Kitsilano' or 'kitsilano'")] = None,
) -> Response:
    store = _store(request)
    name = resolve_area(area) if area is not None else None
    if store.history is None:
        raise _unavailable("history file", store)
    if name is None and month is None:
        return _json(store.history_bytes)
    if name is None:
        return _json(store.history_by_month.get(month, []))
    rows = store.history_by_area.get(name, [])
    return _json(rows if month is None else [r for r in rows if r["month"] == month])


@router.get("/forecast", summary="Forecast rows (forecast_YYYY-MM.json), optionally for one area")
def forecast(
    request: Request,
    area: Annotated[str | None, Query(description="Name or slug from /areas, e.g. 'West End' or 'west-end'")] = None,
) -> Response:
    store = _store(request)
    name = resolve_area(area) if area is not None else None
    if store.forecast is None:
        raise _unavailable("forecast file", store)
    if name is None:
        return _json(store.forecast_bytes)
    return _json(store.forecast_by_area.get(name, []))


@router.get("/boundaries", summary="City of Vancouver local-area polygons (GeoJSON, 22 features)")
def boundaries(request: Request) -> Response:
    store = _store(request)
    if store.boundaries_bytes is None:
        raise _unavailable("boundaries file", store)
    return Response(content=store.boundaries_bytes, media_type=GEOJSON_TYPE)


# --------------------------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------------------------


def _split_origins(value: str) -> list[str]:
    return [o.strip().rstrip("/") for o in value.split(",") if o.strip()]


def create_app(
    outputs_dir: str | Path | None = None,
    boundaries_path: str | Path | None = None,
    allowed_origins: list[str] | None = None,
    allowed_origin_regex: str | None = None,
) -> FastAPI:
    """Build the app. Arguments override the environment variables (the tests use them)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = load_store(
            resolve_outputs_dir(outputs_dir),
            Path(boundaries_path) if boundaries_path is not None else BOUNDARIES_PATH,
        )
        yield

    app = FastAPI(
        title="NeighbourCast API",
        version="1.0.0",
        description=(
            "Read-only reported-incident history and the forecast month for Vancouver's 24 VPD "
            "neighbourhoods, each relative to that area's own history. Data: VPD GeoDASH open data; "
            "boundaries: City of Vancouver open data. Not affiliated with the Vancouver Police Department."
        ),
        lifespan=lifespan,
    )

    origins = allowed_origins
    if origins is None:
        origins = _split_origins(os.environ.get("ALLOWED_ORIGINS") or DEFAULT_ALLOWED_ORIGINS)
    regex = allowed_origin_regex
    if regex is None:
        regex = os.environ.get("ALLOWED_ORIGIN_REGEX") or DEFAULT_ALLOWED_ORIGIN_REGEX
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=regex or None,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
