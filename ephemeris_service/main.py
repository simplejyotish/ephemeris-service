"""HTTP API over the Swiss Ephemeris wrapper. Pure astronomy; no interpretation."""
from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version as _pkg_version
from typing import Literal

import swisseph as swe
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ephemeris_service import swiss

try:
    SERVICE_VERSION = _pkg_version("ephemeris-service")
except PackageNotFoundError:  # pragma: no cover
    SERVICE_VERSION = "0.1.0"

DEFAULT_SOURCE_URL = "https://example.invalid/set-SOURCE_URL"
MAX_JDS = 2000

Ayanamsha = Literal["krishnamurti", "lahiri"]


class PositionsIn(BaseModel):
    jds: list[float] = Field(max_length=MAX_JDS)
    planets: list[str]
    ayanamsha: Ayanamsha

    @field_validator("planets")
    @classmethod
    def _known_planets(cls, v: list[str]) -> list[str]:
        bad = [p for p in v if p not in swiss.PLANETS]
        if bad:
            raise ValueError(f"unknown planet(s): {bad}")
        return v


class AyanamshaIn(BaseModel):
    jd: float
    ayanamsha: Ayanamsha


class HousesIn(BaseModel):
    jd: float
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    ayanamsha: Ayanamsha


class RiseSetIn(BaseModel):
    jd_start: float
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    event: Literal["sunrise", "sunset"]


class EclipseIn(BaseModel):
    jd_start: float
    kind: Literal["solar", "lunar"]


def create_app() -> FastAPI:
    env = os.environ.get("ENV", "").lower()
    prod = env in ("production", "prod")
    api_key = os.environ.get("EPHEMERIS_API_KEY") or None
    if prod and not api_key:
        raise RuntimeError("EPHEMERIS_API_KEY must be set when ENV=production")
    source_url = os.environ.get("SOURCE_URL") or DEFAULT_SOURCE_URL

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        swiss.configure_ephe_path(os.environ.get("SE_EPHE_PATH"))
        yield

    app = FastAPI(
        title="ephemeris-service",
        version=SERVICE_VERSION,
        description="Raw Swiss Ephemeris calculations. Source offered under AGPL-3.0 section 13.",
        lifespan=lifespan,
        docs_url=None if prod else "/docs",
        redoc_url=None if prod else "/redoc",
        openapi_url=None if prod else "/openapi.json",
    )

    def require_key(x_internal_key: str | None = Header(default=None)) -> None:
        if api_key is None:  # only reachable outside production
            return
        if x_internal_key is None or not secrets.compare_digest(
                x_internal_key.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail="invalid or missing X-Internal-Key")

    auth = [Depends(require_key)]

    @app.exception_handler(swe.Error)
    async def _swe_error(_: Request, exc: swe.Error) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def _value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/version", dependencies=auth)
    def version() -> dict:
        return {
            "service_version": SERVICE_VERSION,
            "swe_version": swiss.swe_version(),
            "ephemeris_mode": swiss.ephe_mode(),
            "source_url": source_url,
        }

    @app.post("/v1/positions", dependencies=auth)
    def positions(body: PositionsIn) -> dict:
        rows = swiss.positions(body.jds, body.planets, body.ayanamsha)
        return {"results": [
            {name: {"longitude": lon, "speed": spd} for name, (lon, spd) in row.items()}
            for row in rows]}

    @app.post("/v1/ayanamsha", dependencies=auth)
    def ayanamsha(body: AyanamshaIn) -> dict:
        return {"value": swiss.ayanamsha_value(body.jd, body.ayanamsha)}

    @app.post("/v1/houses", dependencies=auth)
    def houses(body: HousesIn) -> dict:
        cusps, asc, mc = swiss.houses(body.jd, body.lat, body.lon, body.ayanamsha)
        return {"cusps": cusps, "ascendant": asc, "midheaven": mc}

    @app.post("/v1/rise-set", dependencies=auth)
    def rise_set(body: RiseSetIn) -> dict:
        return {"jd": swiss.rise_set(body.jd_start, body.lat, body.lon, body.event)}

    @app.post("/v1/eclipses", dependencies=auth)
    def eclipses(body: EclipseIn) -> dict:
        peak, etype = swiss.next_eclipse(body.jd_start, body.kind)
        return {"peak_jd": peak, "eclipse_type": etype}

    return app


app = create_app()
