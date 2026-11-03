"""File rules of .claude/hooks/guard.py (Write/Edit/MultiEdit/NotebookEdit) for the public service.

Names of private backend settings are assembled from parts so this public file does not spell them out.
"""
import pytest

from guard_helpers import OUTSIDE, ROOT, edit, fake_secrets, multi_edit, notebook, run_guard, write

PRIVATE_NAME = "ANTHROPIC" + "_API_KEY"
ADMIN_NAME = "ADMIN" + "_ACCESS_CODE"
BOT_NAME = "TELEGRAM" + "_BOT_TOKEN"
DB_NAME = "profiles" + ".db"
SIGNS = '["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo"]'
MAIN = "ephemeris_service/main.py"

# (case id, payload, expected decision, rule id that must be named in the reason)
CASES = [
    # S1 astrology interpretation -> ask
    ("nakshatra", write("ephemeris_service/lunar.py", "NAKSHATRA_SPAN = 13.333\n"), "ask", "S1"),
    ("dasha", edit("ephemeris_service/swiss.py", "<<x>>", "def vimshottari_dasha(jd):\n"), "ask", "S1"),
    ("rashi", write("ephemeris_service/signs.py", "def rashi_of(lon): ...\n"), "ask", "S1"),
    ("lagna", write("ephemeris_service/x.py", "lagna_lord = None\n"), "ask", "S1"),
    ("yoga", write("ephemeris_service/x.py", "def find_yogas(): ...\n"), "ask", "S1"),
    ("panchang", write("ephemeris_service/x.py", "# panchang assembly\n"), "ask", "S1"),
    ("tithi", write("ephemeris_service/x.py", "tithi = int(diff / 12)\n"), "ask", "S1"),
    ("karana", write("ephemeris_service/x.py", "KARANA_NAMES = []\n"), "ask", "S1"),
    ("muhurat", write("ephemeris_service/x.py", "def muhurat(): ...\n"), "ask", "S1"),
    ("matchmaking", write("ephemeris_service/x.py", "def matchmaking(): ...\n"), "ask", "S1"),
    ("kundli", write("ephemeris_service/x.py", "kundli = {}\n"), "ask", "S1"),
    ("remedies", write("ephemeris_service/x.py", "REMEDIES = {}\n"), "ask", "S1"),
    ("manglik", write("ephemeris_service/x.py", "is_manglik = False\n"), "ask", "S1"),
    ("sign-table", write("ephemeris_service/x.py", f"SIGNS = {SIGNS}\n"), "ask", "S1"),
    ("interp-in-tests", write("tests/test_x.py", "def test_nakshatra(): ...\n"), "ask", "S1"),
    ("interp-multiedit", multi_edit("ephemeris_service/x.py", ("a", "x = 1"), ("b", "dasha = 2")), "ask", "S1"),
    # S2 private backend code -> deny
    ("core-dir", write("core/chart.py", "x = 1\n"), "deny", "S2"),
    ("app-dir", write("app/main.py", "x = 1\n"), "deny", "S2"),
    ("from-core", write("ephemeris_service/x.py", "from core.chart import build\n"), "deny", "S2"),
    ("import-app", write("ephemeris_service/x.py", "import app.main\n"), "deny", "S2"),
    ("private-setting", write("ephemeris_service/x.py", f'os.environ["{PRIVATE_NAME}"]\n'), "deny", "S2"),
    ("admin-code", write("README.md", f"Set {ADMIN_NAME} first.\n"), "deny", "S2"),
    ("bot-token-name", write("tests/test_x.py", f"{BOT_NAME} = None\n"), "deny", "S2"),
    ("profiles-db", write("docs/x.md", f"Data lives in {DB_NAME}.\n"), "deny", "S2"),
    # S3 secrets and data files -> deny
    *[(f"secret-{name}", write("ephemeris_service/x.py", f'VALUE = "{value}"\n'), "deny", "S3")
      for name, value in fake_secrets().items()],
    ("env-file", write(".env", "X=1\n"), "deny", "S3"),
    ("db-file", write("ephemeris_service/cache.sqlite", ""), "deny", "S3"),
    ("data-dir", write("data/x.json", "{}\n"), "deny", "S3"),
    # S4 licence text -> deny
    ("licence", edit("LICENSE", "<<x>>", "MIT"), "deny", "S4"),
    # S5 pin / licence field -> ask
    ("pin-change", edit("pyproject.toml", '"pyswisseph==2.10.3.2",', '"pyswisseph==2.10.3.3",'), "ask", "S5"),
    ("pin-loosen", edit("pyproject.toml", '"pyswisseph==2.10.3.2",', '"pyswisseph",'), "ask", "S5"),
    ("licence-field", edit("pyproject.toml", 'license = { text = "AGPL-3.0-or-later" }',
                           'license = { text = "MIT" }'), "ask", "S5"),
    # S6 X-Internal-Key auth -> ask
    ("route-without-auth", edit(MAIN, "<<x>>", '    @app.post("/v1/open")\n    def open_(): ...\n'), "ask", "S6"),
    ("router-without-auth", edit(MAIN, "<<x>>", "    app.include_router(extra)\n"), "ask", "S6"),
    ("drop-route-auth", edit(MAIN, '@app.post("/v1/houses", dependencies=auth)', '@app.post("/v1/houses")'), "ask", "S6"),
    ("drop-require-key", edit(MAIN, "auth = [Depends(require_key)]", "auth = []"), "ask", "S6"),
    # S7 new top-level entries -> ask
    ("new-top-dir", write("scripts/x.py"), "ask", "S7"),
    ("new-top-file", write("notes.txt", "x\n"), "ask", "S7"),
    # S8 outside the project -> ask
    ("outside-abs", write(f"{OUTSIDE}/x.py"), "ask", "S8"),
    ("outside-sibling", write(str(ROOT.parent / "some-other-repo" / "x.py")), "ask", "S8"),
    # S9 guardrails protect themselves -> ask
    ("claude-settings", edit(".claude/settings.json", "<<x>>", "{}"), "ask", "S9"),
    ("claude-hook", write(".claude/hooks/guard.py", "print()\n"), "ask", "S9"),
    ("claude-skill", write(".claude/skills/code-placement/SKILL.md", "x\n"), "ask", "S9"),
]

ALLOWED = [
    ("service-endpoint", edit(MAIN, "<<x>>",
                              '    @app.post("/v1/sidereal-time", dependencies=auth)\n    def st(body: StIn) -> dict:\n'
                              '        return {"value": swiss.sidereal_time(body.jd)}\n')),
    ("health-route", edit(MAIN, "<<x>>", '    @app.get("/health")\n')),
    ("swiss-code", write("ephemeris_service/extra.py", "import swisseph as swe\nflags = swe.FLG_SWIEPH\n")),
    ("raw-test", write("tests/test_extra.py", "def test_sun_longitude():\n    assert 0 <= 280.4 < 360\n")),
    ("planet-names", write("ephemeris_service/x.py", 'PLANETS = ["sun", "moon", "mars"]\n')),
    ("readme", edit("README.md", "<<x>>", "Returns raw longitudes; the backend interprets them.\n")),
    ("pyproject-deps", edit("pyproject.toml", '    "fastapi",', '    "fastapi",\n    "orjson",')),
    ("agents-md", write("AGENTS.md", "# Agents\n")),
    ("docs", write("docs/guardrails.md", "# Guardrails\n")),
    ("temp-file", write("/tmp/guardrail-scratch.txt", "x\n")),
]


@pytest.mark.parametrize("case,payload,expected,rule", CASES, ids=[c[0] for c in CASES])
def test_rule_decision(case, payload, expected, rule):
    r = run_guard(payload)
    assert r.returncode == 0, r.stderr
    assert r.decision == expected, (r.decision, r.reason)
    assert f"[{rule} " in r.reason, r.reason
    assert "ephemeris-service guardrail" in r.reason


@pytest.mark.parametrize("case,payload", ALLOWED, ids=[c[0] for c in ALLOWED])
def test_legit_edits_are_allowed(case, payload):
    r = run_guard(payload)
    assert r.returncode == 0, r.stderr
    assert r.decision == "allow", r.reason
    assert r.stdout.strip() == ""


def test_deny_wins_over_ask_and_all_rules_are_named():
    r = run_guard(write("core/dasha.py", "x = 1\n"))   # S2 deny + S1? no (core/ is outside the S1 scope)
    assert r.decision == "deny" and "[S2 " in r.reason
    r = run_guard(write("ephemeris_service/x.py", "from core.dasha import x\n"))  # S2 deny + S1 ask
    assert r.decision == "deny" and "[S2 " in r.reason and "[S1 " in r.reason


@pytest.mark.parametrize("name,value", list(fake_secrets().items()))
def test_reason_never_contains_the_secret(name, value):
    r = run_guard(write("ephemeris_service/x.py", f'VALUE = "{value}"\n'))
    assert r.decision == "deny"
    assert value not in r.stdout and value not in r.stderr
    assert name in r.reason


def test_reason_never_contains_private_names_or_content():
    r = run_guard(write("ephemeris_service/x.py", f'KEY = os.environ["{PRIVATE_NAME}"]\n'))
    assert r.decision == "deny"
    assert PRIVATE_NAME not in r.stdout + r.stderr


def test_relative_path_is_resolved_against_cwd():
    payload = write("ephemeris_service/x.py")
    payload["tool_input"]["file_path"] = "../elsewhere-repo/x.py"
    r = run_guard(payload)
    assert r.decision == "ask" and "[S8 " in r.reason
