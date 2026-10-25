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
