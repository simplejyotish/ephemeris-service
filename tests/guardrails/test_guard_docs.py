"""The skill, AGENTS.md, CLAUDE.md pointer, docs and CI step that ship with the guardrails."""
import re

from guard_helpers import ROOT, SLUG

SKILL = ROOT / ".claude" / "skills" / "code-placement" / "SKILL.md"


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md needs YAML frontmatter"
    return dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)


def test_skill_frontmatter_and_content():
    text = SKILL.read_text(encoding="utf-8")
    fm = _frontmatter(text)
    assert fm["name"] == "code-placement"
    for trigger in ("creating", "moving", "dependency", "committing", "pushing", "pull request"):
        assert trigger in fm["description"]
    for needle in ("simplejyotish/chart-engine", "simplejyotish/ephemeris-service", "simple-astro",
                   "AskUserQuestion", "Do not guess", "recommendation", "something else",
                   "quote the reason", "openapi.json", "Worked examples"):
        assert needle in text, needle
    examples = text.split("## 6. Worked examples", 1)[1]
    assert len(re.findall(r"^\| \"", examples, re.M)) >= 6


def test_agents_md():
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert SLUG in text and "CLAUDE.md" in text and "code-placement/SKILL.md" in text
    assert "ask the developer" in text


def test_claude_md_points_to_the_skill():
    assert "code-placement" in (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_docs_list_every_rule_and_the_limits():
    text = (ROOT / "docs" / "guardrails.md").read_text(encoding="utf-8")
    for rule in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "P1", "P2", "P3", "P4", "P5", "P6", "P7"):
        assert f"| {rule} |" in text, rule
    assert "Limits" in text and "ruleset" in text and "CODEOWNERS" in text

