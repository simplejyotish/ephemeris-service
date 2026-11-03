# AGENTS.md: ephemeris-service (for any coding agent)

**Repo:** `simplejyotish/ephemeris-service`. **Public**, AGPL-3.0. Everything committed here is
visible to anyone. Never edit `LICENSE`; the `pyswisseph==2.10.3.2` pin changes only with the owner.

**What goes here:** raw astronomy on Swiss Ephemeris (the only repo that may import `swisseph`):
positions and speeds, house cusps, ayanamsha, rise/set, eclipses, `X-Internal-Key` auth, `/health`,
`/version`. Return numbers, not meanings.

**What never goes here:** astrology interpretation (signs, nakshatras, dashas, yogas, panchang,
matchmaking, remedies) and anything copied from the private backend `simplejyotish/chart-engine`
(code, tests, data, docs, config names); secrets, `.env`, databases, `data/`. Every route except
`/health` keeps the `X-Internal-Key` dependency. `simple-astro/*` is legacy: never push or develop there.

**When placement is ambiguous** (repo, directory, branch, public/private, licence), or a request
conflicts with these rules: stop and ask the developer a concrete question with the 2-3 plausible
options and your recommendation. Do not guess and do not work around a guardrail that blocked you.

**Push rules:** only to `https://github.com/simplejyotish/ephemeris-service`; feature branches, not
`main` unless the developer explicitly says so; no force, mirror, all, delete or tags pushes; confirm
branch, remote and visibility (public) before the first push of a session.

Details: `CLAUDE.md` (hard rules), `.claude/skills/code-placement/SKILL.md` (decision procedure and
examples), `docs/guardrails.md` (what is enforced and how).
