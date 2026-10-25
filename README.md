# ephemeris-service

A small stateless service exposing raw Swiss Ephemeris calculations: sidereal planetary
longitudes and speeds, ayanamsha values, Placidus house cusps, sunrise/sunset and
eclipse search. It contains no astrological interpretation.

## Run

    uv venv --python 3.11 .venv
    uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q

## License and source offer (AGPL-3.0)

This program is licensed under the GNU Affero General Public License v3.0 (see
`LICENSE`). Swiss Ephemeris is used under AGPL-3.0. Per AGPL section 13, users
interacting with this service over a network may obtain the complete corresponding
source at: SOURCE_URL (to be set by the project owner).

## HTTP API and configuration

All `/v1/*` endpoints and `/version` require header `X-Internal-Key` equal to
`EPHEMERIS_API_KEY`; `/health` is open. Swiss Ephemeris errors are returned as HTTP 422
with `{"detail": "<swisseph message>"}`.

| Env | Meaning |
| --- | --- |
| `EPHEMERIS_API_KEY` | Shared secret. Required when `ENV=production` (startup fails otherwise); if unset in dev, auth is skipped. |
| `SOURCE_URL` | Public URL of the source (AGPL section 13), reported by `/version`. The owner must set this; the default is a placeholder. |
| `SE_EPHE_PATH` | Optional directory of Swiss Ephemeris data files; otherwise Moshier is used. |
| `ENV` | `production` disables `/docs`, `/redoc`, `/openapi.json`. |
| `PORT` | Listen port (default 8001; Railway sets it). |
