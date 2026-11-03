#!/usr/bin/env python3
"""Claude Code guardrail hook: code placement, secrets, licence and push safety (stdlib only, offline).

Registered in .claude/settings.json for PreToolUse (Write|Edit|MultiEdit|NotebookEdit and Bash) and
SessionStart. Reads the hook JSON on stdin and prints either nothing (allow) or a PreToolUse decision:
    {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"|"ask",
                            "permissionDecisionReason": "..."}}
Reasons name the rule and the path only; file contents and matched values are never printed.
On its own internal errors it warns on stderr and allows (fail-open). A rule that matched is always
reported, even if a later rule crashed.

    python3 .claude/hooks/guard.py --rules       # list the rules
    python3 .claude/hooks/guard.py --self-test   # run the built-in checks

To change a rule: edit the REPO SECTION below, update tests/guardrails/, get the owner's approval
(docs/guardrails.md). The ENGINE part is identical in chart-engine and ephemeris-service.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, NamedTuple, Optional

DENY, ASK = "deny", "ask"
ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.path.expanduser("~"))
SKILL = ".claude/skills/code-placement/SKILL.md"


class Change(NamedTuple):
    """A proposed file change: the path and the lines it adds or removes."""
    path: Path                 # absolute, resolved
    rel: Optional[str]         # posix path relative to ROOT, None when outside the project
    exists: bool
    before: str
    after: str
    added: list
    removed: list


class Rule(NamedTuple):
    id: str
    name: str
    decision: str
    check: Callable            # (Change) -> Optional[str]: a short detail (never content) when it matches
    advice: str


# ============================================================================================
# ENGINE helpers shared by both repos
# ============================================================================================

SECRET_PATTERNS = [
    ("private-key-block", re.compile("-----BEGIN " + r"[A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("api-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("telegram-bot-token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")),
]
SECRET_FILES = [
    ("env-file", re.compile(r"(^|/)\.env(\.(?!example$)[^/]*)?$")),
    ("database-file", re.compile(r"\.(db|sqlite|sqlite3)(-journal|-wal|-shm)?$")),
    ("data-directory", re.compile(r"(^|/)data/")),
    ("private-key-file", re.compile(r"(\.pem|\.p12|\.pfx|\.key|(^|/)id_(rsa|ed25519|ecdsa))$")),
]
GUARDED = re.compile(r"^\.claude(/(settings[^/]*\.json|hooks|skills)(/|$)|$)")
COMMENT_STRIPPED = re.compile(r"(\.(py|sh|bash|toml|ya?ml|cfg|ini|txt)|(^|/)Dockerfile[^/]*)$")
DOC_FILE = re.compile(r"\.(md|markdown|rst)$")


def temp_dirs() -> list:
    dirs = ["/tmp", "/private/tmp", "/var/folders", "/private/var/folders", "/dev"]
    if os.environ.get("TMPDIR"):
        dirs.append(os.environ["TMPDIR"])
    dirs += [str(HOME / ".claude" / "projects"), str(HOME / ".claude" / "plans")]
    out = []
    for d in dirs:
        try:
            out.append(Path(d).resolve())
        except OSError:
            pass
    return out


def is_within(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


def resolve(path: str, cwd: Path) -> Path:
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def relpath(p: Path) -> Optional[str]:
    return p.relative_to(ROOT).as_posix() if is_within(p, ROOT) else None


def code_lines(ch: Change) -> list:
    """Added lines with '#' comments removed for file types that use them."""
    if ch.rel and COMMENT_STRIPPED.search(ch.rel):
        return [line.split("#", 1)[0] for line in ch.added]
    return list(ch.added)


def is_doc(rel: str) -> bool:
    return bool(DOC_FILE.search(rel)) or rel.startswith("docs/")


def check_secrets(ch: Change) -> Optional[str]:
    target = ch.rel if ch.rel is not None else ch.path.as_posix()
    for name, rx in SECRET_FILES:
        if rx.search(target):
            return f"{name} must never be written into a repository"
    text = "\n".join(ch.added)
    for name, rx in SECRET_PATTERNS:
        if rx.search(text):
            return f"content matches the secret pattern '{name}'"
    return None


def check_outside(ch: Change) -> Optional[str]:
    if ch.rel is not None or any(is_within(ch.path, d) for d in temp_dirs()):
        return None
    return f"{ch.path} is outside this project ({ROOT})"


def check_guardrails(ch: Change) -> Optional[str]:
    if ch.rel is not None and GUARDED.match(ch.rel):
        return f"{ch.rel} is part of the guardrails"
    return None


def check_top_level(ch: Change) -> Optional[str]:
    if ch.rel is None or ch.rel in ("", "."):
        return None
    top = ch.rel.split("/", 1)[0]
    if top in TOP_LEVEL_ALLOW or (ROOT / top).exists():
        return None
    return f"'{top}' would be a new top-level entry"


# ============================================================================================
# REPO SECTION: simplejyotish/ephemeris-service (PUBLIC, AGPL). Differs per repo.
# ============================================================================================

REPO_SLUG = "simplejyotish/ephemeris-service"
REPO_NAME = "ephemeris-service"
VISIBILITY = "PUBLIC"
LICENCE = "AGPL-3.0-or-later (never edit LICENSE); everything committed here is public"
LOCATION_RULE = ("raw astronomy on Swiss Ephemeris (positions, houses, ayanamsha, rise/set, eclipses, auth, "
                 "health) -> this repo; astrology interpretation, product, storage, UI and the app API -> "
                 "simplejyotish/chart-engine (private); simple-astro/* is legacy (never push or develop there).")
TOP_LEVEL_ALLOW = {
    "ephemeris_service", "tests", "docs", ".github", ".claude",
    "README.md", "CLAUDE.md", "AGENTS.md", "LICENSE", "LICENSES.md", "pyproject.toml", "Dockerfile",
    ".dockerignore", ".gitignore", "railway.json",
}

_INTERP = re.compile(r"(?<![a-z])(nakshatra|dasha|vimshottari|rashi|rasi|lagna|yogas?|panchang|panchanga|tithi|karana|"
                     r"muhurat|muhurta|matchmaking|kundli|kundali|remed(y|ies)|mangal|manglik|guna milan|"
                     r"ashtakoota)\w*", re.I)
_SIGNS = ("aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius",
          "capricorn", "aquarius", "pisces")


def check_interpretation(ch: Change) -> Optional[str]:
    if ch.rel is None or not ch.rel.startswith(("ephemeris_service/", "tests/")):
        return None
    text = "\n".join(ch.added)
    m = _INTERP.search(text)
    if m:
        return f"{ch.rel} would add astrology interpretation ('{m.group(1).lower()}')"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & set(_SIGNS)) >= 3:
        return f"{ch.rel} would add a zodiac sign-name table"
    return None


_PRIVATE_MARKERS = [
    re.compile(r"^\s*(from|import)\s+(core|app)(\.|\s|$)"),
    re.compile(r"ANTHROPIC_API_KEY|ADMIN_ACCESS_CODE|TELEGRAM_[A-Z_]+|profiles\.db"),
]


def check_private_code(ch: Change) -> Optional[str]:
    if ch.rel is None or ch.rel.startswith(".claude/"):
        return None
    if ch.rel.split("/", 1)[0] in ("core", "app"):
        return f"{ch.rel} would create the backend's {ch.rel.split('/', 1)[0]}/ package here"
    for line in ch.added:
        if any(rx.search(line) for rx in _PRIVATE_MARKERS):
            return f"{ch.rel} looks like code or config from the private backend"
    return None


def check_licence(ch: Change) -> Optional[str]:
    if ch.rel in ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"):
        return f"{ch.rel} is the AGPL licence text"
    return None


_LICENCE_LINE = re.compile(r"^\s*(license(-files)?\s*=|\[project\.license\])|License ::", re.I)


def check_owner_approval(ch: Change) -> Optional[str]:
    if ch.rel is None:
        return None
    deps = ch.rel in ("pyproject.toml", "Dockerfile") or re.match(r"requirements[^/]*\.txt$", ch.rel)
    if deps:
        old = sorted(l.strip() for l in ch.before.splitlines() if "pyswisseph" in l.lower())
        new = sorted(l.strip() for l in ch.after.splitlines() if "pyswisseph" in l.lower())
        if old != new:
            return f"the pyswisseph pin in {ch.rel} would change"
    if ch.rel == "pyproject.toml" and any(_LICENCE_LINE.search(l) for l in ch.added + ch.removed):
        return "the licence field of pyproject.toml would change"
    return None


_ROUTE = re.compile(r"@\w+\.(get|post|put|patch|delete|api_route|websocket)\(|\.(add_api_route|include_router)\(")
_AUTH_MARKERS = ("dependencies=auth", "Depends(require_key)", "X-Internal-Key", "def require_key")


def check_auth(ch: Change) -> Optional[str]:
    if ch.rel is None or not (ch.rel.startswith("ephemeris_service/") and ch.rel.endswith(".py")):
        return None
    for marker in _AUTH_MARKERS:
        if ch.after.count(marker) < ch.before.count(marker):
            return f"{ch.rel} would remove X-Internal-Key auth ('{marker}')"
    for line in ch.added:
        if _ROUTE.search(line) and "dependencies" not in line and '"/health"' not in line:
            return f"{ch.rel} would add a route without the X-Internal-Key dependency"
    return None


RULES = [
    Rule("S1", "interpretation-in-service", ASK, check_interpretation,
         "the service is raw astronomy (numbers only); interpretation belongs in the private backend "
         "simplejyotish/chart-engine"),
    Rule("S2", "private-code-in-public-repo", DENY, check_private_code,
         "this repo is PUBLIC: do not copy private backend code, config or names here"),
    Rule("S3", "secrets-and-data", DENY, check_secrets,
         "no secrets, .env files, databases or data/ in a public repo; keys come from environment "
         "variables"),
    Rule("S4", "licence-text", DENY, check_licence,
         "LICENSE is the AGPL text and must not change"),
    Rule("S5", "owner-approval", ASK, check_owner_approval,
         "the pyswisseph pin (2.10.3.2) and the licence field change only with the owner's approval"),
    Rule("S6", "auth-required", ASK, check_auth,
         "every route except /health must keep the X-Internal-Key dependency (auth fails closed)"),
    Rule("S7", "new-top-level-entry", ASK, check_top_level,
         "new top-level files or directories need the developer's agreement (everything here is public)"),
    Rule("S8", "outside-project", ASK, check_outside,
         "this session works in ephemeris-service; confirm with the developer before writing elsewhere"),
    Rule("S9", "guardrails-self-protection", ASK, check_guardrails,
         "the guardrails (.claude/settings*.json, hooks, skills) may only change with the "
         "developer's explicit approval"),
]

SELF_TEST = [
    ("service code", {"tool_name": "Write", "tool_input": {"file_path": "ephemeris_service/x.py", "content": "x = 1\n"}}, "allow"),
    ("interpretation", {"tool_name": "Write", "tool_input": {"file_path": "ephemeris_service/x.py", "content": "NAKSHATRAS = []\n"}}, ASK),
    ("backend import", {"tool_name": "Write", "tool_input": {"file_path": "ephemeris_service/x.py", "content": "from core.chart import x\n"}}, DENY),
    ("licence", {"tool_name": "Edit", "tool_input": {"file_path": "LICENSE", "old_string": "a", "new_string": "b"}}, DENY),
    ("open route", {"tool_name": "Edit", "tool_input": {"file_path": "ephemeris_service/main.py", "old_string": "zz", "new_string": '@app.get("/open")'}}, ASK),
    (".env file", {"tool_name": "Write", "tool_input": {"file_path": ".env", "content": "A=1"}}, DENY),
    ("guard settings", {"tool_name": "Edit", "tool_input": {"file_path": ".claude/settings.json", "old_string": "a", "new_string": "b"}}, ASK),
    ("force push", {"tool_name": "Bash", "tool_input": {"command": "git push --force origin x"}}, DENY),
    ("push main", {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}, ASK),
    ("commit", {"tool_name": "Bash", "tool_input": {"command": "git commit -m 'x'"}}, "allow"),
]

# ============================================================================================
# ENGINE: file changes
# ============================================================================================

MAX_READ = 5_000_000


def read_text(p: Path) -> str:
    try:
        if p.is_file() and p.stat().st_size <= MAX_READ:
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return ""


def diff_lines(before: str, after: str):
    b, a = Counter(before.splitlines()), Counter(after.splitlines())
    return list((a - b).elements()), list((b - a).elements())


def build_change(tool: str, ti: dict, cwd: Path) -> Optional[Change]:
    raw = ti.get("notebook_path") if tool == "NotebookEdit" else ti.get("file_path")
    if not isinstance(raw, str) or not raw:
        return None
    path = resolve(raw, cwd)
    current = read_text(path)
    if tool == "Write":
        before, after = current, str(ti.get("content") or "")
    elif tool == "Edit":
        before, after = apply_edits(current, [ti])
    elif tool == "MultiEdit":
        edits = ti.get("edits") if isinstance(ti.get("edits"), list) else []
        before, after = apply_edits(current, [e for e in edits if isinstance(e, dict)])
    else:  # NotebookEdit: the cell source is the added content
        before, after = "", str(ti.get("new_source") or "")
    added, removed = diff_lines(before, after)
    return Change(path, relpath(path), path.exists(), before, after, added, removed)


def apply_edits(current: str, edits: list):
    """Simulate the edits on the current file; fall back to the edit strings alone."""
    text = current
    for e in edits:
        old, new = str(e.get("old_string") or ""), str(e.get("new_string") or "")
        if old and old in text:
            text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
        else:
            olds = "\n".join(str(x.get("old_string") or "") for x in edits)
            news = "\n".join(str(x.get("new_string") or "") for x in edits)
            return olds, news
    return current, text


def file_findings(tool: str, ti: dict, cwd: Path) -> list:
    ch = build_change(tool, ti, cwd)
    if ch is None:
        return []
    shown = ch.rel if ch.rel is not None else str(ch.path)
    findings = []
    for rule in RULES:
        try:
            detail = rule.check(ch)
        except Exception as exc:  # a broken rule must not hide the others
            warn(f"rule {rule.id} failed: {type(exc).__name__}")
            continue
        if detail:
            findings.append((rule, detail or shown))
    return findings


# ============================================================================================
# ENGINE: Bash commands
# ============================================================================================

PUSH_RULES = {
    "P1": Rule("P1", "push-foreign-remote", DENY, None,
               f"push only to https://github.com/{REPO_SLUG}; never to another repo or org "
               "(simple-astro/* is legacy and fetch-only)"),
    "P2": Rule("P2", "push-unsafe-flags", DENY, None,
               "force, mirror, all, delete, tags and prune pushes are not allowed"),
    "P3": Rule("P3", "push-from-elsewhere", DENY, None,
               "run the push from inside this repo, without 'git -C' or a 'cd' to another directory"),
    "P4": Rule("P4", "push-to-main", ASK, None,
               "pushing to main/master needs the developer's explicit go-ahead; use a feature branch "
               "and a pull request"),
    "P5": Rule("P5", "remote-change", ASK, None,
               "changing remotes can redirect pushes to another repo; confirm with the developer"),
    "P6": Rule("P6", "write-outside-project", ASK, None,
               "the command writes outside this project; confirm the target with the developer"),
    "P7": Rule("P7", "guardrails-self-protection", ASK, None,
               "the command touches the guardrails (.claude/settings*.json, hooks, skills); "
               "only with the developer's explicit approval"),
}
CONTROL = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "\n"}
WRAPPERS = {"sudo", "env", "command", "nohup", "time", "exec", "builtin", "nice"}
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
GIT_READ_ONLY = {"status", "log", "diff", "show", "rev-parse", "ls-files", "ls-tree", "cat-file",
                 "blame", "grep", "describe", "shortlog", "reflog", "fetch", "rev-list", "for-each-ref",
                 "show-ref", "help", "version", "worktree"}
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
WRITE_CMDS = {"cp", "mv", "install", "rsync", "ln"}
TOUCH_CMDS = {"rm", "rmdir", "mkdir", "touch", "truncate", "unlink", "tee", "chmod", "chown"}


def tokenize(cmd: str) -> list:
    try:
        lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|<>()")
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:
        return cmd.replace("\n", " ; ").split()


def segments(tokens: list):
    """Split into simple commands; return (words, redirect targets) per command."""
    out, words, targets, i = [], [], [], 0
    while i < len(tokens):
        t = tokens[i]
        if t in CONTROL:
            out.append((words, targets))
            words, targets = [], []
        elif t and set(t) <= set("<>&|") and ">" in t:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if not (t.endswith("&") and (nxt.isdigit() or nxt == "-")):
                targets.append(nxt)
            if words and words[-1].isdigit():
                words.pop()
            i += 1
        elif t == "<" or t == "<<" or t == "<<<":
            i += 1
        else:
            words.append(t)
        i += 1
    out.append((words, targets))
    return [(w, t) for w, t in out if w or t]


def strip_prefix(words: list) -> list:
    i = 0
    while i < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]) or words[i] in WRAPPERS):
        i += 1
    return words[i:]


def path_outside(word: str, cwd: Path) -> Optional[Path]:
    if not word or "$" in word or "`" in word or word.startswith("-") or "://" in word:
        return None
    try:
        p = resolve(word, cwd)
    except (OSError, RuntimeError):
        return None
    if is_within(p, ROOT) or any(is_within(p, d) for d in temp_dirs()):
        return None
    return p


def guarded_word(word: str, cwd: Path) -> bool:
    if ".claude" not in word:
        return False
    try:
        rel = relpath(resolve(word.rstrip("*").rstrip("/") or ".", cwd))
    except (OSError, RuntimeError):
        return False
    return rel is not None and bool(GUARDED.match(rel))


def git(*args: str) -> str:
    try:
        p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=3)
        return p.stdout.strip() if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def url_ok(url: str) -> bool:
    u = url.strip().rstrip("/")
    u = u[:-4] if u.endswith(".git") else u
    pat = r"^(https://([^@/\s]+@)?(www\.)?github\.com/|git@github\.com:|ssh://git@github\.com/)" + re.escape(REPO_SLUG) + "$"
    return bool(re.match(pat, u, re.I))


def current_branch() -> str:
    return git("symbolic-ref", "--short", "-q", "HEAD")


def push_findings(args: list, ctx_outside: bool, dash_c: bool) -> list:
    found = []
    if dash_c or ctx_outside:
        found.append(("P3", "the push would run against another directory"))
    positional, i, remote_opt = [], 0, None
    while i < len(args):
        a = args[i]
        if a in PUSH_OPTS_WITH_VALUE:
            if a == "--repo" and i + 1 < len(args):
                remote_opt = args[i + 1]
            i += 2
            continue
        if a.startswith("--repo="):
            remote_opt = a.split("=", 1)[1]
        elif a.startswith("--"):
            if re.match(r"^--(force|force-with-lease|force-if-includes|mirror|all|branches|delete|tags|prune)(=|$)", a):
                found.append(("P2", f"option {a.split('=')[0]}"))
        elif a.startswith("-") and len(a) > 1:
            if set(a[1:]) & {"f", "d"}:
                found.append(("P2", f"option {a}"))
        else:
            positional.append(a)
        i += 1
    remote = remote_opt or (positional[0] if positional else "")
    refspecs = positional[1:] if not remote_opt else positional
    branch = current_branch()
    if not remote:
        remote = (git("config", f"branch.{branch}.pushRemote") or git("config", "remote.pushDefault")
                  or git("config", f"branch.{branch}.remote") or "origin")
    inline = "://" in remote or bool(re.match(r"^[^/\s]+@[^:\s]+:", remote))
    url = remote if inline else git("remote", "get-url", "--push", remote)
    if not url_ok(url):
        shown = "an inline URL" if inline else f"remote '{remote}'"
        found.append(("P1", f"{shown} is not {REPO_SLUG}" if url else f"{shown} is unknown"))
    targets = []
    for spec in refspecs:
        if spec.startswith("+"):
            found.append(("P2", "a '+' (force) refspec"))
            spec = spec[1:]
        if spec.startswith(":"):
            found.append(("P2", "a delete refspec"))
            continue
        dst = spec.split(":", 1)[-1]
        targets.append(branch if dst == "HEAD" else dst)
    if not refspecs:
        targets.append(branch)
    for t in targets:
        if re.sub(r"^refs/heads/", "", t) in ("main", "master"):
            found.append(("P4", f"target branch '{re.sub(r'^refs/heads/', '', t)}'"))
            break
    return found


def bash_findings(cmd: str, cwd: Path, found: list) -> list:
    """Append (rule id, detail) findings to `found` (kept even if a later segment fails to parse)."""
    sim_cwd, cwd_outside = cwd, not is_within(cwd, ROOT)
    for words, targets in segments(tokenize(cmd)):
        for t in targets:
            if guarded_word(t, sim_cwd):
                found.append(("P7", f"redirect into {t}"))
            elif path_outside(t, sim_cwd):
                found.append(("P6", f"redirect to {path_outside(t, sim_cwd)}"))
        w = strip_prefix(words)
        if not w:
            continue
        name = os.path.basename(w[0])
        args = w[1:]
        if name in ("cd", "pushd") and args:
            try:
                sim_cwd = resolve(args[-1], sim_cwd) if "$" not in args[-1] else sim_cwd
            except (OSError, RuntimeError):
                pass
            cwd_outside = not is_within(sim_cwd, ROOT)
            continue
        if name == "git":
            found += git_findings(args, sim_cwd, cwd_outside)
            continue
        plain = [a for a in args if not a.startswith("-")]
        if name in WRITE_CMDS and len(plain) >= 2:
            dests = [plain[-1]]
            if "-t" in args and args.index("-t") + 1 < len(args):
                dests = [args[args.index("-t") + 1]]
            checked = plain if name == "mv" else dests
            if any(guarded_word(a, sim_cwd) for a in checked):
                found.append(("P7", f"{name} on .claude"))
            for d in dests:
                if path_outside(d, sim_cwd):
                    found.append(("P6", f"{name} to {path_outside(d, sim_cwd)}"))
        elif name in TOUCH_CMDS:
            if any(guarded_word(a, sim_cwd) for a in plain):
                found.append(("P7", f"{name} on .claude"))
            for a in plain:
                if path_outside(a, sim_cwd):
                    found.append(("P6", f"{name} on {path_outside(a, sim_cwd)}"))
        elif name in ("sed", "perl", "ruby") and any(a.startswith("-i") or a == "--in-place" for a in args):
            if any(guarded_word(a, sim_cwd) for a in plain):
                found.append(("P7", f"{name} -i on .claude"))
            for a in plain:
                if path_outside(a, sim_cwd) and os.path.exists(a):
                    found.append(("P6", f"{name} -i on {path_outside(a, sim_cwd)}"))
    return found


def git_findings(args: list, cwd: Path, cwd_outside: bool) -> list:
    found, i, dash_c, gcwd = [], 0, False, cwd
    while i < len(args) and args[i].startswith("-"):
        a = args[i]
        if a in GIT_OPTS_WITH_VALUE:
            if a in ("-C", "--git-dir", "--work-tree") and i + 1 < len(args):
                dash_c = True
                if a == "-C":
                    try:
                        gcwd = resolve(args[i + 1], cwd)
                    except (OSError, RuntimeError):
                        pass
            i += 2
            continue
        if a.startswith(("--git-dir=", "--work-tree=")):
            dash_c = True
        i += 1
    if i >= len(args):
        return found
    sub, rest = args[i], args[i + 1:]
    if sub == "push":
        return push_findings(rest, cwd_outside, dash_c)
    if sub == "remote" and rest and rest[0] in ("add", "set-url", "rename", "remove", "rm"):
        found.append(("P5", f"git remote {rest[0]}"))
    if sub == "config" and any(re.match(r"^remote\..+\.(push)?url$|^url\..+\.(push)?insteadof$", a, re.I) for a in rest):
        found.append(("P5", "git config of a remote URL"))
    if sub in ("checkout", "restore", "rm", "mv", "clean") and any(guarded_word(a, gcwd) for a in rest):
        found.append(("P7", f"git {sub} on .claude"))
    outside = cwd_outside or not is_within(gcwd, ROOT)
    if outside and sub not in GIT_READ_ONLY and not any(is_within(gcwd, d) for d in temp_dirs()):
        found.append(("P6", f"git {sub} in {gcwd}"))
    return found


# ============================================================================================
# ENGINE: decisions, output, entry points
# ============================================================================================

def warn(msg: str) -> None:
    print(f"[{REPO_NAME} guardrail] warning: {msg} (allowing)", file=sys.stderr)


def evaluate(payload: dict):
    """Return (decision, reason) for a hook payload; decision is 'allow', 'ask' or 'deny'."""
    if not isinstance(payload, dict):
        return "allow", ""
    tool = payload.get("tool_name")
    ti = payload.get("tool_input")
    if not isinstance(ti, dict):
        return "allow", ""
    cwd_raw = payload.get("cwd")
    cwd = Path(cwd_raw).resolve() if isinstance(cwd_raw, str) and cwd_raw else ROOT
    findings = []
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        findings = file_findings(tool, ti, cwd)
    elif tool == "Bash" and isinstance(ti.get("command"), str):
        raw = []
        try:
            bash_findings(ti["command"], cwd, raw)
        except Exception as exc:  # keep what matched before the failure
            warn(f"bash rules failed: {type(exc).__name__}")
        findings = [(PUSH_RULES[rid], d) for rid, d in raw]
    if not findings:
        return "allow", ""
    decision = DENY if any(r.decision == DENY for r, _ in findings) else ASK
    seen, parts = set(), []
    for r, detail in sorted(findings, key=lambda f: (f[0].decision != DENY, f[0].id)):
        if r.id in seen:
            continue
        seen.add(r.id)
        parts.append(f"[{r.id} {r.name}] {r.decision.upper()}: {detail}. {r.advice}.")
    reason = (f"{REPO_NAME} guardrail: " + " ".join(parts) +
              f" See {SKILL} and CLAUDE.md. Do not work around this hook: explain it to the developer"
              " and ask how to proceed.")
    return decision, reason


def session_context() -> str:
    branch = current_branch() or "unknown"
    on_main = " (this is main: use a feature branch unless the developer says otherwise)" if branch in ("main", "master") else ""
    lines = [
        f"[{REPO_NAME} guardrails] This repo is {REPO_SLUG}: {VISIBILITY}, licence: {LICENCE}.",
        f"Current branch: {branch}{on_main}.",
        f"Location rule: {LOCATION_RULE}",
        "When the right repo, directory, branch, visibility or licence is ambiguous, STOP and ask the developer "
        "a concrete question (AskUserQuestion when available). Do not guess or pick the 'closest' place.",
        "Never work around a guardrail hook that denied or asked: quote its reason to the developer and ask.",
        f"Push only to https://github.com/{REPO_SLUG}, on a feature branch, never force; confirm branch, remote "
        "and visibility with the developer before the first push of a session.",
        f"Before creating/moving files, adding dependencies, committing, pushing or opening a PR, use the "
        f"code-placement skill ({SKILL}). Hard rules: CLAUDE.md and AGENTS.md.",
    ]
    return "\n".join(lines)


def emit_pre_tool(decision: str, reason: str) -> None:
    if decision in (DENY, ASK):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": decision,
                                                 "permissionDecisionReason": reason}}))


def list_rules() -> None:
    print(f"{REPO_NAME} guardrail rules ({REPO_SLUG}, {VISIBILITY})")
    for r in RULES + list(PUSH_RULES.values()):
        print(f"  {r.id:3} {r.decision:4} {r.name}: {r.advice}")


def self_test() -> int:
    failed = 0
    for name, payload, want in SELF_TEST:
        p = dict(payload, hook_event_name="PreToolUse", cwd=str(ROOT))
        ti = dict(p["tool_input"])
        if "file_path" in ti and not ti["file_path"].startswith("/"):
            ti["file_path"] = str(ROOT / ti["file_path"])
        p["tool_input"] = ti
        got, _ = evaluate(p)
        ok = got == want
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}: expected {want}, got {got}")
    print(f"{len(SELF_TEST) - failed}/{len(SELF_TEST)} passed")
    return 1 if failed else 0


def main(argv: list) -> int:
    if "--rules" in argv:
        list_rules()
        return 0
    if "--self-test" in argv:
        return self_test()
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except (ValueError, OSError):
        warn("hook input is not JSON")
        return 0
    if not isinstance(payload, dict):
        warn("hook input is not a JSON object")
        return 0
    event = payload.get("hook_event_name")
    if event == "SessionStart":
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                 "additionalContext": session_context()}}))
    elif event == "PreToolUse":
        decision, reason = evaluate(payload)
        emit_pre_tool(decision, reason)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # fail-open on internal errors, never silently
        warn(f"internal error {type(exc).__name__}")
        sys.exit(0)
