---
name: code-placement
description: Use before creating, moving or renaming files, splitting code across modules or repos, adding a dependency, committing, pushing or opening a pull request in the SimpleJyotish repos, and whenever the developer says where code should go or a guardrail hook denies or asks. Decides which repo, directory, branch, visibility and licence code belongs to, and requires asking the developer when that is ambiguous.
---

# Code placement (SimpleJyotish)

You are in **simplejyotish/ephemeris-service**: **PUBLIC**, AGPL-3.0. Everything committed here is
visible to anyone. Hard rules live in `CLAUDE.md`; this skill tells you where code goes and when to
stop and ask.

## 1. Repo map

| Repo | Visibility, licence | What belongs there | Must never be there |
|---|---|---|---|
| `simplejyotish/ephemeris-service` (this repo) | **public**, AGPL-3.0 | the ONLY place that may import `swisseph`/`pyswisseph`; raw astronomy only: positions and speeds, house cusps, ayanamsha, rise/set, eclipses; auth (`X-Internal-Key`), `/health`, `/version` | astrology interpretation (signs, nakshatras, dashas, yogas, panchang, matchmaking, remedies), anything copied from the private backend (code, tests, golden data, docs, config names), secrets, private URLs, business notes |
| `simplejyotish/chart-engine` | private, proprietary (licence undecided) | all astrology logic, the web app and `/v1` API, storage, `openapi.json` | Swiss Ephemeris imports or ported Swiss Ephemeris code |
| Android app, iOS app (future repos, not created yet) | private (expected) | mobile app code | this repo |
| `simple-astro/*` | LEGACY, private, fetch-only | nothing new | never push there, never develop there |

## 2. Where does this code belong?

Walk these in order and stop at the first match:

1. Does it call Swiss Ephemeris or compute raw astronomy and return **numbers** (plus the eclipse type
   string)? -> **this repo** (`ephemeris_service/swiss.py` for the calculation, `main.py` for the route,
   with `dependencies=auth`).
2. Does it name, classify or interpret those numbers (sign, nakshatra, dasha, house meaning, yoga,
   tithi, muhurat, compatibility, remedy)? -> **chart-engine** (private). Not here.
3. Is it product logic, storage, UI, the app API or mobile code? -> chart-engine or the mobile repos.
4. Is it the wire format between backend and service? -> the endpoint here **and**
   `core/ephemeris_http.py` in the backend, changed together; additive only; tell the developer.
5. Anything else, or more than one answer fits -> **ask** (section 3).

When in doubt whether something is interpretation, it is: it belongs in the backend.

## 3. The ambiguity protocol (mandatory)

Whenever the correct **repo, directory, branch, visibility (public/private) or licence** is not
unambiguous, or a request conflicts with these rules or `CLAUDE.md`:

- **STOP** before writing, moving, committing or pushing anything.
- **Ask the developer one concrete question.** Use the `AskUserQuestion` tool when it is available.
  Offer the 2-3 plausible locations as options, mark your **recommendation with the reason**, and add
  "something else". Without the tool, ask the same question in plain text and wait.
- **Do not guess.** Do not silently pick the "closest" place. Do not split the difference.
- **Do not work around a hook** that denied or asked (no renaming to dodge a pattern, no writing through
  Bash instead of Write, no editing `.claude/` to disable it).

## 4. Push rules

- Push only to this repo's own remote: `https://github.com/simplejyotish/ephemeris-service`.
  Never to `chart-engine`, never to `simple-astro/*`, never to a fork or mirror.
- Work on feature branches. Never push directly to `main`/`master` unless the developer explicitly says
  so **in this conversation** and the repo rules allow it.
- No force, `--mirror`, `--all`, `--delete`, `--tags` or `--prune` pushes. No `git -C <dir>` pushes.
- Before the **first push of a session**, confirm branch, remote and visibility with the developer
  ("Push branch X to simplejyotish/ephemeris-service, which is PUBLIC?"). Re-read the diff for anything
  that must not be public first.

## 5. When a hook denies or asks

The hook reason names the rule (for example `[S1 interpretation-in-service]`). Then:

1. Stop. Tell the developer what you tried, **quote the reason**, and say which rule fired.
2. Propose the compliant alternative (for example "return the raw longitude here; compute the
   nakshatra in chart-engine").
3. Ask how to proceed. An `ask` prompt is the developer's decision, not yours to argue past.
4. If you think the rule is wrong, say so; changing a rule needs the owner (`docs/guardrails.md`).

List the rules with `python3 .claude/hooks/guard.py --rules`.

## 6. Worked examples

| Request | What to do | Question to ask |
|---|---|---|
| "I need sunrise for X" | Raw astronomy: `/v1/rise-set` exists. Extend it additively if needed. | "Extend `/v1/rise-set` with `<field>` (additive, backend adapter updated in the same change; recommended), add a new endpoint, or something else?" |
| "Add a field to the chart JSON" | The chart JSON is the backend's API, not this service. | "The chart JSON lives in chart-engine (private). Make the change there and regenerate its `openapi.json` (recommended), or do you need a new raw value from this service first?" |
| "Copy this helper from the backend into the service" | Refuse: this repo is public; copying publishes proprietary code. | "This repo is public. Keep the helper in chart-engine and expose only the raw number it needs here (recommended), write a minimal raw-astronomy version from scratch, or something else?" |
| "Push my changes" while on `main` | Do not push. | "You are on `main` of a PUBLIC repo. Create branch `<name>` and push it for a PR (recommended), push to `main` directly (you confirm explicitly), or something else?" |
| "Return the nakshatra with each position" | Interpretation: hook S1 asks. | "Nakshatras are interpretation. Compute them in chart-engine from the longitude this service already returns (recommended), or something else?" |
| "Upgrade pyswisseph" | Pin change: hook S5 asks; owner approval needed. | "Upgrading `pyswisseph` from 2.10.3.2 can shift results the backend's golden tests check. Ask the owner first and run the backend golden tests against a branch (recommended), or keep the pin?" |
| "Add a quick debug endpoint" | Every route except `/health` needs `X-Internal-Key` (hook S6). | "Add it with `dependencies=auth` (recommended), keep it local only and do not commit it, or something else?" |
