#!/usr/bin/env bash
# PreToolUse hook for the Bash tool: only let `git push` through when it targets THIS repo's own
# GitHub remote. Exit 2 blocks the command and shows the message on stderr to Claude.
# Limits: this checks the command text and the remote's URL; it cannot see a push made from
# another shell or tool. GitHub branch protection is the real backstop.
set -u

EXPECTED="simple-astro/ephemeris-service"

cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null) || exit 0

# Only look at commands that run `git push` (also `git -C dir push`, `git -c k=v push`).
printf '%s' "$cmd" | grep -Eq '(^|[;&|[:space:]])git([[:space:]]+(-C|-c)[[:space:]]+[^[:space:]]+)*[[:space:]]+push([[:space:]]|$)' || exit 0

block() {
  echo "BLOCKED: $1" >&2
  echo "This repo ($EXPECTED) may only push to https://github.com/$EXPECTED. See CLAUDE.md." >&2
  exit 2
}

printf '%s' "$cmd" | grep -Eq 'git[[:space:]]+-C[[:space:]]' \
  && block "do not use 'git -C' to push; run git push from inside this repo."
printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(--force|-f|--force-with-lease|--mirror|--all|--delete|--tags|--prune)([[:space:]=]|$)' \
  && block "force, mirror, all, delete, tags and prune pushes are not allowed here."

# First non-option word after `git push` is the remote (name or URL). None means the default remote.
args=$(printf '%s' "$cmd" | sed -E 's/.*git[[:space:]]+push[[:space:]]*//; s/[;&|].*$//')
remote=""
for w in $args; do
  case "$w" in -*) continue ;; esac
  remote="$w"
  break
done

if [ -z "$remote" ]; then
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  remote=$(git config "branch.${branch}.remote" 2>/dev/null || echo "origin")
fi

case "$remote" in
  *://*|*@*:*) url="$remote" ;;
  *) url=$(git remote get-url --push "$remote" 2>/dev/null || echo "") ;;
esac

case "$url" in
  *"github.com/$EXPECTED"|*"github.com/$EXPECTED.git"|*"github.com:$EXPECTED"|*"github.com:$EXPECTED.git") exit 0 ;;
  "") block "unknown remote '$remote'." ;;
  *) block "remote '$remote' points to '$url', not $EXPECTED." ;;
esac
