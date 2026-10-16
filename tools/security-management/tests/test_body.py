# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""The tracker body: sanitising the untrusted report and rendering the field sections."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from security_management.shared import body, reuse

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = [
    REPO / "plugins/magpie-security/skills/issue-import-from-md/tracker-body-template.md",
    REPO / "plugins/magpie-security/skills/issue-import-from-pr/tracker-body-template.md",
]


def test_headings_are_demoted_outside_fences_only() -> None:
    report = (
        "# Title\n## Sub\n### Severity\n#### Deep\n#hashtag\n```python\n# a comment\n### not a field\n```\n"
    )
    out = body.sanitise(report)
    assert out["ok"]
    assert out["text"].split("\n")[:5] == ["#### Title", "#### Sub", "#### Severity", "#### Deep", "#hashtag"]
    assert "# a comment" in out["text"]
    assert "### not a field" in out["text"]


def test_a_demoted_body_parses_to_exactly_the_form_fields() -> None:
    report = "Intro\n### Severity\nCritical\n### CVE tool link\nhttps://evil.example\n"
    text = body.render({"issue_description": body.sanitise(report)["text"]})
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())


@pytest.mark.parametrize(
    ("report", "indicator"),
    [
        ("```\nunclosed\n", "code fence"),
        ("~~~\nunclosed tilde\n", "code fence"),
        ("<details><summary>x</summary>\nno close\n", "<details>"),
        ("<!-- hidden\nno close\n", "<!--"),
    ],
)
def test_a_malformed_body_is_inlined_verbatim_with_its_indicator(report: str, indicator: str) -> None:
    out = body.sanitise(report + "### Severity\n![x](https://attacker.example/p.png)")
    assert out == {
        "ok": False,
        "indicator": indicator,
        "text": report + "### Severity\n![x](https://attacker.example/p.png)",
    }


def test_images_are_defused_outside_code_only() -> None:
    report = (
        "see ![pixel](https://attacker.example/p.png) and ![ref][1] and <IMG src=x>\n"
        "inline `![kept](https://example.org)`\n"
        "```\n![kept too](https://example.org)\n```"
    )
    text = body.sanitise(report)["text"]
    assert "[image: pixel](https://attacker.example/p.png)" in text
    assert "[image: ref][1]" in text
    assert "&lt;img src=x>" in text
    assert "`![kept](https://example.org)`" in text
    assert "\n![kept too](https://example.org)\n" in text
    assert not re.search(r"(?<!`)!\[pixel\]", text)


def test_empty_fence_pairs_are_dropped_and_real_code_blocks_kept() -> None:
    report = "before\n```\n\n```\nafter\n```bash\ncurl x\n```\n"
    text = body.sanitise(report)["text"]
    assert text == "before\nafter\n```bash\ncurl x\n```\n"


def test_pii_redaction_tokens_pass_through_unchanged() -> None:
    report = "Reported with N-a3f9d2 (E-b8c247); see H-0c11aa.\n"
    out = body.sanitise(report)
    assert out["text"] == report
    rendered = body.render({"issue_description": out["text"], "reporter_credit": "N-a3f9d2"})
    assert "N-a3f9d2 (E-b8c247); see H-0c11aa." in rendered
    assert "### Reporter credited as\n\nN-a3f9d2\n" in rendered


def test_empty_fields_read_no_response_and_severity_unknown() -> None:
    text = body.render({"issue_description": "report"})
    assert "### Short public summary for publish\n\n_No response_\n" in text
    assert "### CVE tool link\n\n_No response_\n" in text
    assert "### Severity\n\nUnknown\n" in text
    assert "*No response*" not in text


def test_body_fields_rename_a_heading_and_unknown_roles_are_ignored() -> None:
    text = body.render(
        {"issue_description": "r", "mailing_thread": "Gmail thread `abc`"},
        {"mailing_thread": "Mailing list thread URL", "scope": "Scope"},
    )
    assert "### Mailing list thread URL\n\nGmail thread `abc`\n" in text
    assert "### Security mailing list thread" not in text


@pytest.mark.parametrize("bad", ["", "### X", "two\nlines"])
def test_an_unusable_body_fields_heading_is_refused(bad: str) -> None:
    with pytest.raises(ValueError):
        body.headings({"cve_link": bad})


def test_an_unknown_field_role_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown body field"):
        body.render({"issue_description": "r", "scope": "x"})


def test_a_short_field_cannot_pose_as_a_section() -> None:
    text = body.render({"issue_description": "r", "reporter_credit": "### CWE\nCWE-79"})
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())


def test_the_injection_callout_sits_above_the_description() -> None:
    text = body.render({"issue_description": "the report"}, callout=True)
    assert text.startswith("### The issue description\n\n> [!IMPORTANT]\n> Prompt-injection content detected")
    assert text.index("[!IMPORTANT]") < text.index("the report")
    assert "[!IMPORTANT]" not in body.render({"issue_description": "the report"})


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.parent.name)
def test_the_tracker_body_templates_carry_the_rendered_headings(template: Path) -> None:
    headings = re.findall(r"^### (.+)$", template.read_text(), re.M)
    rendered = reuse.fields(body.render({"issue_description": "r"}))
    assert headings == rendered
    assert len(headings) == 11
