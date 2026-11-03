# ephemeris-service

A small stateless service exposing raw Swiss Ephemeris calculations: sidereal planetary
longitudes, latitudes and speeds (sidereal, tropical or equatorial frame; Sun to Pluto and
the lunar nodes), ayanamsha values (krishnamurti, lahiri, pushya, raman, fagan, tropical), Placidus house cusps, sunrise/sunset and
eclipse search. It contains no astrological interpretation.

## Run

    uv venv --python 3.11 .venv
    uv pip install --python .venv/bin/python -e ".[dev]"
    .venv/bin/python -m pytest -q

## License and source offer (AGPL-3.0)

This program is licensed under the GNU Affero General Public License v3.0 (see
`LICENSE`). Swiss Ephemeris is used under AGPL-3.0. Per AGPL section 13, users
interacting with this service over a network may obtain the complete corresponding
source at the URL configured as `SOURCE_URL` and reported by `GET /version`. The
service refuses to start with `ENV=production` unless `SOURCE_URL` is set to a real
public URL (the built-in `https://example.invalid/...` placeholder is rejected), so a
production deployment always advertises where its source can be obtained. Outside
production the placeholder default is used.

## HTTP API and configuration

All `/v1/*` endpoints and `/version` require header `X-Internal-Key` equal to
`EPHEMERIS_API_KEY`; `/health` is open. Swiss Ephemeris errors are returned as HTTP 422
with `{"detail": "<swisseph message>"}`.

`POST /v1/positions` takes an optional `frame` (`sidereal` default, `tropical`, `equatorial`); each
planet returns `longitude`, `speed` and `latitude`. In the equatorial frame `longitude` is right
ascension and `latitude` is declination. `ayanamsha` is ignored outside the sidereal frame.

`POST /v1/rise-set` takes `jd_start`, `lat`, `lon` and `event` (`sunrise` or `sunset`), plus optional
`body` (`Sun` default, or `Moon`) and `hindu_rising` (default `false`). With `hindu_rising=true` the
centre of the disc is on the horizon with no refraction (`BIT_HINDU_RISING`), so sunrise is later and
sunset earlier than the standard upper-limb event. Defaults return exactly what they did before.

`POST /v1/rise-set-batch` (`{"items": [<rise-set request>, ...]}` -> `{"results": [jd, ...]}`) and
`POST /v1/houses-batch` (`{"items": [<houses request>, ...]}` -> `{"results": [{cusps, ascendant,
midheaven}, ...]}`) take up to 2000 items each; result `i` is exactly what the single endpoint returns
for item `i`. The first Swiss Ephemeris error fails the whole batch with HTTP 422 and that item's own
message, the same text the single endpoint gives.

Note: `ayanamsha="tropical"` (sidereal frame) reproduces the legacy app's user-defined zero
ayanamsha exactly, quirks included: its `speed` carries a 360000 deg/day offset (about 360001
for the Sun) and its longitude is about 0.0039 deg off true tropical at J2000. For genuine
tropical longitudes and speeds use `frame="tropical"`.

| Env | Meaning |
| --- | --- |
| `EPHEMERIS_API_KEY` | Shared secret. Required (startup fails otherwise) unless `ENV` is explicitly `dev`, `development` or `test`; only then may it be unset, which skips auth. |
| `SOURCE_URL` | Public URL of the source (AGPL section 13), reported by `/version`. Required with `ENV=production` (unset or the `example.invalid` placeholder fails startup); elsewhere defaults to a placeholder. |
| `SE_EPHE_PATH` | Optional directory of Swiss Ephemeris data files; otherwise Moshier is used. |
| `ENV` | Read stripped and case-insensitively. `production`/`prod` disables `/docs`, `/redoc`, `/openapi.json` and requires `SOURCE_URL`; `dev`/`development`/`test` allow running without a key. The Docker image defaults to `production`. |
| `PORT` | Listen port (default 8001; Railway sets it). |
