"""Wiring, SessionStart output, fail-safe behaviour and speed of the guardrail hook."""
import json
import re
import subprocess
import sys

import pytest

from guard_helpers import GUARD, ROOT, SLUG, bash, edit, pre, run_guard, write

SETTINGS = ROOT / ".claude" / "settings.json"
FILE_MATCHER = "Write|Edit|MultiEdit|NotebookEdit"


def _hooks():
    return json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]


def _commands(entries, matcher):
    return [h["command"] for e in entries if e.get("matcher") == matcher for h in e["hooks"]]


def test_settings_is_valid_json_and_keeps_permissions():
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert "Bash(git push --force *)" in data["permissions"]["deny"]
    assert "Bash(git remote add *)" in data["permissions"]["ask"]


def test_settings_registers_hooks_with_correct_matchers():
    hooks = _hooks()
    bash_cmds = _commands(hooks["PreToolUse"], "Bash")
    assert any("check-push.sh" in c for c in bash_cmds), "existing push guard must stay registered"
    assert any("guard.py" in c for c in bash_cmds)
    assert any("guard.py" in c for c in _commands(hooks["PreToolUse"], FILE_MATCHER))
    session = [h["command"] for e in hooks["SessionStart"] for h in e["hooks"]]
    assert any("guard.py" in c for c in session)
    for entries in hooks.values():
        for e in entries:
            for h in e["hooks"]:
                assert h["type"] == "command"
                assert "$CLAUDE_PROJECT_DIR" in h["command"]
                assert 0 < h.get("timeout", 60) <= 30


def test_matchers_are_valid_regexes_that_match_the_tools():
    for e in _hooks()["PreToolUse"]:
        rx = re.compile("^(?:" + e["matcher"] + ")$")
        assert any(rx.match(t) for t in ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"))
    rx = re.compile("^(?:" + FILE_MATCHER + ")$")
    assert all(rx.match(t) for t in ("Write", "Edit", "MultiEdit", "NotebookEdit")) and not rx.match("Bash")


def test_session_start_output():
    payload = {"session_id": "s", "transcript_path": "/dev/null", "cwd": str(ROOT),
               "hook_event_name": "SessionStart", "source": "startup"}
    r = run_guard(payload)
    assert r.returncode == 0, r.stderr
    out = r.output["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    ctx = out["additionalContext"]
    assert SLUG in ctx and "PUBLIC" in ctx
    assert "ask the developer" in ctx.lower()
    assert "code-placement" in ctx and "CLAUDE.md" in ctx
    assert 6 <= len(ctx.strip().splitlines()) <= 10


@pytest.mark.parametrize("raw", ["", "not json", "{", "[]", "null", '{"tool_input": 5}',
                                 '{"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {}}'])
def test_fails_safe_on_bad_input(raw):
    r = run_guard(raw=raw)
    assert r.returncode == 0
    assert r.decision == "allow"
    assert "Traceback" not in r.stderr


def test_unknown_tool_and_event_are_allowed():
    assert run_guard(pre("Read", file_path=str(ROOT / ".env"))).decision == "allow"
    assert run_guard({"hook_event_name": "Stop"}).stdout == ""


@pytest.mark.parametrize("payload", [
    write("ephemeris_service/x.py", "NAKSHATRA = 1\n"),
    write("ephemeris_service/x.py", "x = 1\n" * 2000),
    edit("pyproject.toml", "dependencies = [", "dependencies = ["),
    bash("git status && echo hi > /tmp/x"),
    bash("git push origin main"),
])
def test_each_invocation_is_fast(payload):
    best = min(run_guard(payload).elapsed for _ in range(3))
    assert best < 0.3, f"{best:.3f}s"


def test_self_test_and_rules_listing():
    p = subprocess.run([sys.executable, str(GUARD), "--self-test"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "FAIL" not in p.stdout
    p = subprocess.run([sys.executable, str(GUARD), "--rules"], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0
    for rule in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        assert rule in p.stdout


def test_guard_is_stdlib_only():
    text = GUARD.read_text(encoding="utf-8")
    imported = set(re.findall(r"^(?:from|import)\s+([A-Za-z_]+)", text, re.M))
    assert imported <= {"__future__", "json", "os", "re", "shlex", "subprocess", "sys", "collections",
                        "pathlib", "typing", "fnmatch"}, imported
