"""Helpers for the guardrail tests: run the hook scripts as Claude Code would (offline, no service).

Fake secrets are built at runtime from pieces so that no file in the repo matches a secret pattern.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
GUARD = HOOKS / "guard.py"
CHECK_PUSH = HOOKS / "check-push.sh"
SLUG = "simplejyotish/ephemeris-service"
OTHER_SLUG = "simplejyotish/chart-engine"
LEGACY_SLUG = "simple-astro/ephemeris-service"
OUTSIDE = "/opt/not-this-repo"          # an absolute path outside the project and outside temp dirs


@dataclass
class Result:
    returncode: int
    output: dict | None
    stdout: str
    stderr: str
    elapsed: float

    @property
    def decision(self) -> str:
        if not self.output:
            return "allow"
        return self.output.get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    @property
    def reason(self) -> str:
        if not self.output:
            return ""
        return self.output.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")


def run_guard(payload: dict | None = None, *, raw: str | None = None, guard: Path = GUARD,
              cwd: Path | None = None, args: list[str] | None = None) -> Result:
    data = raw if raw is not None else json.dumps(payload)
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, str(guard), *(args or [])], input=data,
                          capture_output=True, text=True, cwd=str(cwd or ROOT), timeout=30)
    elapsed = time.perf_counter() - start
    out = None
    if proc.stdout.strip() and not args:
        out = json.loads(proc.stdout)
    return Result(proc.returncode, out, proc.stdout, proc.stderr, elapsed)


def pre(tool: str, cwd: Path | None = None, **tool_input) -> dict:
    return {
        "session_id": "test-session",
        "transcript_path": "/dev/null",
        "cwd": str(cwd or ROOT),
        "permission_mode": "default",
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    }


def _abs(path: str) -> str:
    return path if path.startswith("/") else str(ROOT / path)


def write(path: str, content: str = "x = 1\n") -> dict:
    return pre("Write", file_path=_abs(path), content=content)


def edit(path: str, old: str, new: str) -> dict:
    return pre("Edit", file_path=_abs(path), old_string=old, new_string=new)


def multi_edit(path: str, *pairs: tuple[str, str]) -> dict:
    return pre("MultiEdit", file_path=_abs(path),
               edits=[{"old_string": o, "new_string": n} for o, n in pairs])


def notebook(path: str, source: str) -> dict:
    return pre("NotebookEdit", notebook_path=_abs(path), new_source=source, edit_mode="replace")


def bash(command: str, cwd: Path | None = None) -> dict:
    return pre("Bash", cwd=cwd, command=command, description="test")


def fake_secrets() -> dict[str, str]:
    """Obviously fake values in the shape of real secrets, assembled at runtime."""
    return {
        "aws-access-key": "AK" + "IA" + "FAKE" * 4,
        "api-key": "s" + "k-" + "fake" * 6,
        "slack-token": "xo" + "xb-" + "0" * 12,
        "github-token": "gh" + "p_" + "Fake" * 9,
        "telegram-bot-token": "1234" + "56789:" + "F" * 35,
        "private-key-block": "-----BEGIN " + "RSA PRIVATE" + " KEY-----",
    }


def make_repo(base: Path, branch: str = "feature") -> Path:
    """A throwaway git repo with this repo's hooks copied in and a set of remotes."""
    repo = base / "repo"
    (repo / ".claude" / "hooks").mkdir(parents=True)
    for f in (GUARD, CHECK_PUSH):
        shutil.copy2(f, repo / ".claude" / "hooks" / f.name)

    def git(*a: str) -> None:
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", branch)
    git("remote", "add", "origin", f"https://github.com/{SLUG}.git")
    git("remote", "add", "sshorigin", f"git@github.com:{SLUG}.git")
    git("remote", "add", "other", f"https://github.com/{OTHER_SLUG}.git")
    git("remote", "add", "legacy", f"https://github.com/{LEGACY_SLUG}.git")
    git("remote", "add", "lookalike", f"https://example.com/github.com/{SLUG}.git")
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-q", "--allow-empty", "--no-verify", "-m", "init")
    return repo


def checkout(repo: Path, branch: str) -> None:
    subprocess.run(["git", "checkout", "-q", "-b", branch], cwd=repo, check=True, capture_output=True)
