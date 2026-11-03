"""Bash rules of .claude/hooks/guard.py: pushes, remotes, writes outside the project, self-protection."""
import pytest

from guard_helpers import OTHER_SLUG, OUTSIDE, ROOT, SLUG, bash, checkout, make_repo, run_guard

# Push cases run in a throwaway repo (copied hook, known remotes, branch "feature").
PUSH_CASES = [
    # allowed: this repo's own remote, feature branch
    ("plain-push", "git push", "allow", None),
    ("origin-feature", "git push origin feature", "allow", None),
    ("set-upstream", "git push -u origin feature", "allow", None),
    ("https-url", f"git push https://github.com/{SLUG}.git feature", "allow", None),
    ("ssh-url", f"git push git@github.com:{SLUG}.git feature", "allow", None),
    ("ssh-remote-name", "git push sshorigin feature", "allow", None),
    ("commit-allowed", 'git commit -m "Add a thing"', "allow", None),
    ("commit-mentions-push", 'git commit -m "push origin main later"', "allow", None),
    ("status", "git status && git log --oneline -3", "allow", None),
    # denied: other repos
    ("other-repo", "git push other feature", "deny", "P1"),
    ("legacy-org", "git push legacy feature", "deny", "P1"),
    ("other-org-url", "git push https://github.com/someone/ephemeris-service.git feature", "deny", "P1"),
    ("other-repo-url", f"git push https://github.com/{OTHER_SLUG}.git feature", "deny", "P1"),
    ("lookalike-url", "git push lookalike feature", "deny", "P1"),
    ("unknown-remote", "git push nosuchremote feature", "deny", "P1"),
    ("dash-c-config", "git -c core.askPass=x push other feature", "deny", "P1"),
    # denied: unsafe flags
    ("force", "git push --force origin feature", "deny", "P2"),
    ("force-short", "git push -f origin feature", "deny", "P2"),
    ("force-cluster", "git push -uf origin feature", "deny", "P2"),
    ("force-with-lease", "git push --force-with-lease origin feature", "deny", "P2"),
    ("plus-refspec", "git push origin +feature", "deny", "P2"),
    ("mirror", "git push --mirror origin", "deny", "P2"),
    ("all", "git push --all origin", "deny", "P2"),
    ("delete", "git push --delete origin feature", "deny", "P2"),
    ("delete-refspec", "git push origin :feature", "deny", "P2"),
    ("tags", "git push --tags origin", "deny", "P2"),
    ("prune", "git push --prune origin", "deny", "P2"),
    # denied: pushing from somewhere else
    ("dash-C", "git -C /some/other/repo push origin feature", "deny", "P3"),
    ("cd-elsewhere", f"cd {OUTSIDE} && git push origin feature", "deny", "P3"),
    # ask: main / master
    ("push-main", "git push origin main", "ask", "P4"),
    ("push-master", "git push origin master", "ask", "P4"),
    ("push-head-main", "git push origin HEAD:main", "ask", "P4"),
    ("push-refs-heads-main", "git push origin feature:refs/heads/main", "ask", "P4"),
    # ask: remote changes
    ("remote-add", "git remote add mirror https://github.com/someone/x.git", "ask", "P5"),
    ("remote-set-url", "git remote set-url origin https://github.com/someone/x.git", "ask", "P5"),
    ("config-remote-url", "git config remote.origin.pushurl https://github.com/someone/x.git", "ask", "P5"),
]


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return make_repo(tmp_path_factory.mktemp("push"))


@pytest.fixture(scope="module")
def repo_on_main(tmp_path_factory):
    r = make_repo(tmp_path_factory.mktemp("pushmain"), branch="main")
    return r


@pytest.mark.parametrize("case,cmd,expected,rule", PUSH_CASES, ids=[c[0] for c in PUSH_CASES])
def test_push_rules(repo, case, cmd, expected, rule):
    r = run_guard(bash(cmd, cwd=repo), guard=repo / ".claude/hooks/guard.py", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert r.decision == expected, (r.decision, r.reason)
    if rule:
        assert f"[{rule} " in r.reason, r.reason


@pytest.mark.parametrize("cmd", ["git push", "git push origin", "git push origin HEAD", "git push -u origin HEAD"])
def test_push_while_on_main_asks(repo_on_main, cmd):
    r = run_guard(bash(cmd, cwd=repo_on_main), guard=repo_on_main / ".claude/hooks/guard.py", cwd=repo_on_main)
    assert r.decision == "ask", r.reason
    assert "[P4 " in r.reason


def test_push_reason_does_not_print_remote_urls(repo):
    r = run_guard(bash("git push https://user:tok3n@github.com/someone/x.git feature", cwd=repo),
                  guard=repo / ".claude/hooks/guard.py", cwd=repo)
    assert r.decision == "deny"
    assert "tok3n" not in r.stdout + r.stderr


# Outside-the-project and self-protection cases run against the real hook (paths relative to ROOT).
OTHER_CASES = [
    ("redirect-outside", f"echo hi > {OUTSIDE}/x.txt", "ask", "P6"),
    ("append-outside", f"echo hi >> {OUTSIDE}/x.txt", "ask", "P6"),
    ("redirect-parent", "echo hi > ../other-repo/x.txt", "ask", "P6"),
    ("tee-outside", f"echo hi | tee -a {OUTSIDE}/x.txt", "ask", "P6"),
    ("cp-outside", f"cp ephemeris_service/swiss.py {OUTSIDE}/", "ask", "P6"),
    ("mv-parent", "mv notes.txt ../other-repo/", "ask", "P6"),
    ("git-C-commit", f"git -C {ROOT.parent}/other-repo commit -m x", "ask", "P6"),
    ("cd-then-write", f"cd {OUTSIDE} && echo hi > x.txt", "ask", "P6"),
    ("rm-hook", "rm .claude/hooks/guard.py", "ask", "P7"),
    ("rm-rf-claude", "rm -rf .claude", "ask", "P7"),
    ("sed-settings", "sed -i '' 's/guard/x/' .claude/settings.json", "ask", "P7"),
    ("checkout-claude", "git checkout -- .claude", "ask", "P7"),
    ("restore-claude", "git restore .claude/settings.json", "ask", "P7"),
    ("mv-skill", "mv .claude/skills/code-placement /tmp/x", "ask", "P7"),
    ("redirect-settings", "echo '{}' > .claude/settings.json", "ask", "P7"),
    ("chmod-hook", "chmod -x .claude/hooks/check-push.sh", "ask", "P7"),
]

OTHER_ALLOWED = [
    ("redirect-tmp", "echo hi > /tmp/x.txt"),
    ("devnull", "ls missing 2>/dev/null; ls >/dev/null 2>&1"),
    ("inside-redirect", "echo hi > docs/x.txt"),
    ("inside-cp", "cp ephemeris_service/swiss.py ephemeris_service/swiss_copy.py"),
    ("read-claude", "cat .claude/settings.json && python3 .claude/hooks/guard.py --rules"),
    ("git-C-status", f"git -C {ROOT.parent}/other-repo status"),
    ("git-C-log", f"git -C {ROOT.parent}/other-repo log --oneline -3"),
    ("pytest", "python -m pytest tests/guardrails -q"),
    ("cp-from-claude", "cp .claude/settings.json /tmp/settings-backup.json"),
    ("unbalanced-quote", "echo 'oops"),
]


@pytest.mark.parametrize("case,cmd,expected,rule", OTHER_CASES, ids=[c[0] for c in OTHER_CASES])
def test_other_bash_rules(case, cmd, expected, rule):
    r = run_guard(bash(cmd))
    assert r.returncode == 0, r.stderr
    assert r.decision == expected, (r.decision, r.reason)
    assert f"[{rule} " in r.reason, r.reason


@pytest.mark.parametrize("case,cmd", OTHER_ALLOWED, ids=[c[0] for c in OTHER_ALLOWED])
def test_other_bash_allowed(case, cmd):
    r = run_guard(bash(cmd))
    assert r.returncode == 0, r.stderr
    assert r.decision == "allow", r.reason
