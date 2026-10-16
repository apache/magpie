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


def test_images_are_defused_outside_fences_and_inside_code_spans() -> None:
    report = (
        "see ![pixel](https://attacker.example/p.png) and ![ref][1] and <IMG src=x>\n"
        "inline `![kept](https://example.org)`\n"
        "```\n![kept too](https://example.org)\n```"
    )
    text = body.sanitise(report)["text"]
    assert "[image: pixel](https://attacker.example/p.png)" in text
    assert "[image: ref][1]" in text
    assert "&lt;IMG src=x>" in text
    assert "`[image: kept](https://example.org)`" in text
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


@pytest.mark.parametrize(
    "report",
    [
        "```\n### Severity\n~~~\n",  # ``` opened, ~~~ "closes"
        "````\ncode\n```\n### Severity\n````\n",  # ```` opened, ``` "closes"
        "    ```\n### Severity\n    ```\n",  # a four-space-indented fence
        "```\nunclosed\n",
        "```\n```python\n```\n",  # a fence-like line inside a block
        "``` a`b\nx\n```\n",  # a backtick info string: not a fence in CommonMark
        "\t```\nx\n\t```\n",
    ],
)
def test_fences_that_do_not_pair_strictly_fail_closed(report: str) -> None:
    out = body.sanitise(report)
    assert (out["ok"], out["indicator"]) == (False, "code fence")


def test_strictly_paired_fences_pass() -> None:
    report = "```python\n# c\n```\n~~~~\n### x\n~~~~~\n   ```\ny\n   ````  \nafter\n"
    out = body.sanitise(report)
    assert out["ok"], out


def test_an_empty_pair_is_dropped_only_as_a_whole_pair() -> None:
    report = "```\na\n```\n\n~~~\nb\n~~~\n"
    assert body.sanitise(report)["text"] == report
    assert body.sanitise("x\n~~~\n\n~~~\ny")["text"] == "x\ny"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("![x][]", "[image: x][]"),
        ("![x]", "[image: x]"),
        ("<picture><source srcset=u>", "&lt;picture>&lt;source srcset=u>"),
        ("<svg onload=x>", "&lt;svg onload=x>"),
        ("<details><summary>s</summary></details>", "&lt;details>&lt;summary>s&lt;/summary>&lt;/details>"),
        ("<iframe src=u></iframe> <video src=u>", "&lt;iframe src=u>&lt;/iframe> &lt;video src=u>"),
        ("x <b>tag</b> a < b", "x &lt;b>tag&lt;/b> a < b"),
        ("<b>block</b>", "&lt;b>block&lt;/b>"),
    ],
)
def test_images_and_active_html_are_defused(raw: str, expected: str) -> None:
    assert body.sanitise(raw)["text"] == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("<!-- hide the rest", "&lt;!-- hide the rest"),
        ("![p](https://a.example/p.png)", "[image: p](https://a.example/p.png)"),
        ("```\n### CWE", "&#96;``\n#### CWE"),
        ("~~~", "&#126;~~"),
        ("<details>", "&lt;details>"),
        ("N-a3f9d2 (E-b8c247)", "N-a3f9d2 (E-b8c247)"),
    ],
)
def test_short_fields_are_sanitised(value: str, expected: str) -> None:
    assert body.short_field(value) == expected
    text = body.render({"issue_description": "r", "reporter_credit": value, "affected_versions": value})
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())
    changed = body.sanitised_fields({"reporter_credit": value})
    assert changed == ([] if value == expected else ["reporter_credit"])


def test_a_title_like_field_cannot_open_a_code_block() -> None:
    text = body.render({"issue_description": "r", "reporter_credit": "```", "cwe": "### Severity"})
    assert not any(body.is_fence(line) for line in text.split("\n"))
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())


@pytest.mark.parametrize(
    "line",
    [
        "\\` ![x](https://a.example/p) \\`",  # escaped backticks are not a code span
        "`a` ![x](https://a.example/p) `b`",
        "`open\n![x](https://a.example/p) close`",  # a span across two lines
        "``![x](https://a.example/p)``",
    ],
)
def test_images_are_defused_whatever_the_backticks(line: str) -> None:
    text = body.sanitise(line)["text"]
    assert "![" not in text
    assert "[image: x](https://a.example/p)" in text


def test_crlf_and_lone_cr_are_normalised_before_pairing() -> None:
    assert body.sanitise("a\r\n### b\r\n")["text"] == "a\n#### b\n"
    out = body.sanitise("```\rcode\r```\r### Severity")
    assert out["ok"]
    assert out["text"] == "```\ncode\n```\n#### Severity"
    assert body.sanitise("x\r```\ry")["ok"] is False


@pytest.mark.parametrize("char", ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"])
def test_other_line_breaks_fail_closed(char: str) -> None:
    out = body.sanitise(f"intro{char}### Severity\nCritical")
    assert (out["ok"], out["indicator"]) == (False, "line break")
    with pytest.raises(ValueError, match="line-break"):
        body.short_field(f"Alice{char}### CWE")


@pytest.mark.parametrize("trail", ["\x0c", "\u00a0", "x", " ~"])
def test_a_closer_with_anything_but_spaces_and_tabs_after_it_is_refused(trail: str) -> None:
    out = body.sanitise(f"```\ncode\n```{trail}\n### Severity\n")
    assert out["ok"] is False


def test_a_closer_followed_by_spaces_and_tabs_closes() -> None:
    assert body.sanitise("```\ncode\n``` \t\n### x\n")["text"] == "```\ncode\n``` \t\n#### x\n"


def test_a_fenced_field_heading_cannot_reach_the_cve_record() -> None:
    from generate_cve_json.cve_json import extract_field

    report = "PoC:\n```\n### Severity\n\nCritical\n# comment\n```\n"
    cleaned = body.sanitise(report)
    assert cleaned["ok"]
    assert "\\### Severity\n\nCritical\n\\# comment" in cleaned["text"]
    text = body.render({"issue_description": cleaned["text"], "severity": "Low"})
    assert extract_field(text, "Severity") == "Low"
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())


@pytest.mark.parametrize(
    "report",
    [
        "<pre>\n```\n</pre>\n![pixel](https://attacker.example/unique)\n```",
        "<div>\n```\n</div>\n![pixel](https://attacker.example/unique)\n```",
        "<details>\n```\n</details>\n![pixel](https://attacker.example/unique)\n```",
        "<!-- x\n```\n-->\n![pixel](https://attacker.example/unique)\n```",
    ],
)
def test_html_blocks_cannot_hide_an_image_behind_a_fence(report: str) -> None:
    out = body.sanitise(report)
    assert out["ok"]
    for line in out["text"].split("\n"):
        assert not line.lstrip().startswith("<")
    # the image line is code here, and no HTML block can end the fence early on GitHub
    assert out["text"].startswith("&lt;")


def test_html_block_starts_in_short_fields_are_escaped() -> None:
    assert body.short_field("<div onclick=x>Alice</div>") == "&lt;div onclick=x>Alice&lt;/div>"
    assert body.short_field("<?php x ?>") == "&lt;?php x ?>"
    assert body.short_field("a < b") == "a < b"


@pytest.mark.parametrize(
    "report",
    [
        "- <div>\n  ```\n  </div>\n![x](u)\n```",
        "> <div>\n```\n</div>\n![x](u)\n```",
        "1. <details>\n```\n</details>\n![x](u)\n```",
        "* <!--\n```\n-->\n![x](u)\n```",
    ],
)
def test_html_openers_behind_container_prefixes_are_escaped(report: str) -> None:
    out = body.sanitise(report)
    assert "<" not in out["text"].replace("&lt;", "")


def test_an_inline_tag_is_escaped() -> None:
    assert body.sanitise("a <img src=x> b")["text"] == "a &lt;img src=x> b"
    assert body.short_field("a <img src=x> b") == "a &lt;img src=x> b"
