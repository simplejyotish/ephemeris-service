# ephemeris-service: raw astronomy over HTTP (AGPL-3.0, public)

Read this first. This repo is **public**. Everything committed here is visible to anyone.

## What this repo is
A small, stateless HTTP service on Swiss Ephemeris (`pyswisseph`). It returns raw astronomy only:
planet longitudes and speeds, house cusps, ayanamsha, sunrise/sunset, and eclipse times. It is the only
place in the whole project that imports `swisseph`. The private backend (`simple-astro/chart-engine`)
calls it over HTTP and does all the astrology.

```
android / ios  -->  chart-engine (private backend)  --HTTP + X-Internal-Key-->  ephemeris-service (this repo)
```

## Which repo gets which code
| Code | Goes in | Never in |
|---|---|---|
| Swiss Ephemeris calls, raw positions/houses/rise-set/eclipses, auth, health/version | this repo | the backend |
| Astrology interpretation (signs, nakshatras, dasha, KP, vargas, panchang assembly, Lal Kitab, matchmaking) | `simple-astro/chart-engine` (private) | **this repo** |

## Hard rules
1. **No astrology logic here.** No sign names, nakshatras, dashas, houses-as-meaning, yogas, remedies.
   Return numbers (and the eclipse type string). If you are unsure whether something is interpretation,
   it belongs in the backend.
2. **Never copy code from the private backend into this repo.** This repo is public and AGPL; anything
   copied in becomes public. Do not paste backend files, tests, golden data or docs here.
3. **Push only to `https://github.com/simple-astro/ephemeris-service`.** Never push this code anywhere
   else, and never push backend code here. No force pushes, `--mirror`, `--all` or branch deletes. A hook
   in `.claude/` blocks these; do not work around it.
4. **No secrets in git, ever.** The shared key comes from `EPHEMERIS_API_KEY`; the AGPL source link from
   `SOURCE_URL`. Do not put real keys, URLs of private systems, customer data or business notes in code,
   tests, comments, commit messages or this file.
5. **Auth must fail closed.** Without `EPHEMERIS_API_KEY` the service refuses to start unless `ENV` is
   exactly `dev`, `development` or `test`. In production it also needs a real `SOURCE_URL`. Do not add
   any path that serves requests unauthenticated (only `/health` is open).
6. **AGPL section 13:** users of the service must be offered its source. Keep `/version` returning
   `source_url`, and keep the README's source offer correct.
7. **The wire format is a contract with the backend.** Endpoint paths and JSON shapes are consumed by
   `core/ephemeris_http.py` in the backend, which checks them strictly. Do not rename or reshape; add
   fields only if the backend is updated in the same change, and tell the owner.
8. **Keep the sidereal-mode lock.** `swe.set_sid_mode` is process-global; every set-then-calculate
   sequence runs under the lock in `swiss.py`. Do not remove it.
9. Do not change `LICENSE`. Pin `pyswisseph==2.10.3.2` unless the owner approves an upgrade.

## Commands
```bash
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
.venv/bin/python -m pytest -q
ENV=dev uvicorn ephemeris_service.main:app --port 8001      # local dev without a key
```

## Before you push
Run the tests. Re-read your diff for anything that should not be public. Ask the owner before changing
the API shape, the licence, or visibility.
