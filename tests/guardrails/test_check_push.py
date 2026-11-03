"""The original push guard (.claude/hooks/check-push.sh): the 20 cases it was written against, kept as a test."""
import json
import shutil
import subprocess

import pytest

from guard_helpers import CHECK_PUSH, OTHER_SLUG, SLUG, make_repo

pytestmark = pytest.mark.skipif(shutil.which("jq") is None or shutil.which("bash") is None,
                                reason="check-push.sh needs bash and jq")

CASES = [
    ("git push", 0),
    ("git push origin feature", 0),
    ("git push -u origin feature", 0),
    (f"git push https://github.com/{SLUG}.git feature", 0),
    (f"git push git@github.com:{SLUG}.git feature", 0),
    ("git push sshorigin feature", 0),
    ("git status", 0),
    ("ls -la", 0),
    ("git push other feature", 2),
    ("git push legacy feature", 2),
    ("git push https://github.com/someone/ephemeris-service.git feature", 2),
    (f"git push https://github.com/{OTHER_SLUG}.git feature", 2),
    ("git push nosuchremote feature", 2),
    ("git push --force origin feature", 2),
    ("git push -f origin feature", 2),
    ("git push --force-with-lease origin feature", 2),
    ("git push --mirror origin", 2),
    ("git push --all origin", 2),
    ("git push --delete origin feature", 2),
    ("git push --tags origin", 2),
    ("git push --prune origin", 2),
    ("git -C /some/other/repo push origin feature", 2),
    ("git -c core.askPass=x push other feature", 2),
]


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    return make_repo(tmp_path_factory.mktemp("checkpush"))


@pytest.mark.parametrize("cmd,code", CASES, ids=[c[0] for c in CASES])
def test_check_push(repo, cmd, code):
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                          "tool_input": {"command": cmd}})
    p = subprocess.run(["bash", str(repo / ".claude/hooks/check-push.sh")], input=payload,
                       capture_output=True, text=True, cwd=repo, timeout=20)
    assert p.returncode == code, p.stderr
    if code == 2:
        assert "BLOCKED" in p.stderr


def test_check_push_syntax():
    p = subprocess.run(["bash", "-n", str(CHECK_PUSH)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
