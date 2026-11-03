# Guardrails: keeping code in the right repo

These guardrails stop people and coding agents from putting code in the wrong SimpleJyotish repo (this
one is public), and make agents ask the developer when placement is ambiguous. They ship inside the repo.

## What is enforced where

| Layer | File | Binds | What it does |
|---|---|---|---|
| Instructions | `CLAUDE.md`, `AGENTS.md` | any agent that reads them | repo identity, hard rules, ask protocol |
| Skill | `.claude/skills/code-placement/SKILL.md` | Claude Code | repo map, decision procedure, ambiguity protocol, push rules, examples |
| Hooks | `.claude/hooks/guard.py` via `.claude/settings.json` | Claude Code sessions in this repo | deny/ask before file writes and shell commands; reminder at session start |
| Push guard | `.claude/hooks/check-push.sh` | Claude Code | the original guard: pushes only to this repo's remote, no force/mirror/all/delete/tags/prune |
| Permissions | `.claude/settings.json` `permissions` | Claude Code | deny force/mirror/delete pushes, ask before remote changes |
| Tests and CI | `tests/guardrails/`, `.github/workflows/ci.yml` (job `guardrails`) | every push and PR | the hooks behave as documented |

Rules (`python3 .claude/hooks/guard.py --rules` prints the current list):

| Id | Decision | Rule |
|---|---|---|
| S1 | ask | astrology interpretation in `ephemeris_service/**` or `tests/**` (nakshatra, dasha, rashi, lagna, yoga, panchang, tithi, karana, muhurat, matchmaking, kundli, remedies, manglik, sign-name tables) |
| S2 | deny | code that looks copied from the private backend: a `core/` or `app/` package, `from core.`/`from app.` imports, the backend's private setting names or database file |
| S3 | deny | secrets (key formats, private keys, bot tokens), `.env*`, databases, `data/` |
| S4 | deny | editing `LICENSE` |
| S5 | ask | changing the `pyswisseph` pin or the licence field in `pyproject.toml` |
| S6 | ask | removing the `X-Internal-Key` dependency, or adding a route without it (other than `/health`) |
| S7 | ask | a new top-level file or directory outside the allowlist |
| S8 | ask | writing a file outside the project (temp dirs exempt) |
| S9 | ask | changing the guardrails: `.claude/settings*.json`, `.claude/hooks/*`, `.claude/skills/*` |
| P1 | deny | pushing to any remote other than `github.com/simplejyotish/ephemeris-service` |
| P2 | deny | force, `+refspec`, mirror, all, delete (`:branch`), tags, prune pushes |
| P3 | deny | pushing via `git -C`/`--git-dir` or after `cd` to another directory |
| P4 | ask | pushing to `main`/`master` (refspec or current branch) |
| P5 | ask | `git remote add/set-url/rename/remove`, `git config remote.*.url` |
| P6 | ask | shell writes outside the project (redirects, `tee`, `cp`/`mv`, `rm`, `git -C <other repo>` with a writing subcommand) |
| P7 | ask | shell commands that change the guardrails (`rm`, `mv`, `sed -i`, redirects, `git checkout/restore -- .claude`) |

A deny blocks the tool call. An ask shows the developer a permission prompt with the reason. Reasons
name the rule and the path, never file contents or matched values.

## Install (per developer)

1. Clone the repo and open it in Claude Code (`claude` in the repo root).
2. Accept the prompt to trust the project's settings and hooks.
3. Verify: run `/hooks` in Claude Code and check `SessionStart`, `PreToolUse` `Bash` and
   `PreToolUse` `Write|Edit|MultiEdit|NotebookEdit` list `guard.py` (and `check-push.sh` for Bash).
4. Self-test: `python3 .claude/hooks/guard.py --self-test` (needs only `python3`; `check-push.sh` needs `jq`).

Other agents (Codex, Cursor and similar) read `AGENTS.md`; they do not run these hooks.

## Seeing why something was blocked

The reason appears in the Claude Code transcript and the permission prompt, for example
`ephemeris-service guardrail: [S1 interpretation-in-service] ASK: ephemeris_service/x.py would add
astrology interpretation ('nakshatra') ...`. Look up the id above or with `--rules`. To reproduce, pipe
the hook JSON into the script: `echo '{"hook_event_name":"PreToolUse","tool_name":"Write","tool_input":{"file_path":"ephemeris_service/x.py","content":"NAKSHATRA = 1"}}' | python3 .claude/hooks/guard.py`.

## Updating or changing a rule

1. Edit the REPO SECTION (`RULES`, `TOP_LEVEL_ALLOW`) of `.claude/hooks/guard.py`; the ENGINE part is
   identical in both repos, so port engine fixes to the other repo too.
2. Add or change the table-driven cases in `tests/guardrails/` (a deny/ask case and an allowed control).
3. Run `python -m pytest tests/guardrails -q -p no:cacheprovider --confcutdir=tests/guardrails`.
4. Get the owner's approval in the pull request. The hook itself asks before any edit to `.claude/`.

Developers get the update with the next pull; Claude Code picks up hook changes at the next session.

## Limits (honest)

- Hooks bind Claude Code only. A human pushing from a terminal, another agent, or Claude Code with hooks
  disabled is not stopped. The shell checks read the command text (best effort): they do not see
  writes made inside scripts (`python -c`), paths built from variables, or pushes from another tool.
- The interpretation check is a word list: it can miss interpretation written without those words and
  it asks (never denies) on false positives.
- The backstop is GitHub. Recommended for the owner (not enabled by these changes): a branch ruleset on
  `main` requiring a pull request and the `CI` checks (`test`, `guardrails`), blocking force pushes and
  deletion; `CODEOWNERS` entries for `.claude/**`, `LICENSE`, `pyproject.toml`, `AGENTS.md` and
  `CLAUDE.md` with required code-owner review; secret scanning and push protection (free for public repos).
