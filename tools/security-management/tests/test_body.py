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
"""The tracker body: the untrusted report as an inert block, the field sections."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from github_body_field.parser import fence_roles, loose_heading_name
from github_body_field.parser import normalise as normalise_fields

from security_management.shared import body, reuse

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = [
    REPO / "plugins/magpie-security/skills/issue-import-from-md/tracker-body-template.md",
    REPO / "plugins/magpie-security/skills/issue-import-from-pr/tracker-body-template.md",
]


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


def test_html_block_starts_in_short_fields_are_escaped() -> None:
    assert body.short_field("<div onclick=x>Alice</div>") == "&lt;div onclick=x>Alice&lt;/div>"
    assert body.short_field("<?php x ?>") == "&lt;?php x ?>"
    assert body.short_field("a < b") == "a < b"


def test_an_inline_tag_is_escaped_in_a_short_field() -> None:
    assert body.short_field("a <img src=x> b") == "a &lt;img src=x> b"


# ---------------------------------------------------------------------------
# The report as an inert block
# ---------------------------------------------------------------------------

HOSTILE = [
    "# Title\n### Severity\nCritical\n### CVE tool link\nhttps://evil.example\n",
    "PoC:\n```\n### Severity\n\nCritical\n```\n",
    "````\n```\n### CWE\n```\n````\n~~~\n### Severity\n",
    "```\nunclosed\n### Severity\n",
    "![pixel](https://attacker.example/p.png) <img src=x> <!-- hide\n<details><summary>x",
    "<pre>\n```\n</pre>\n![pixel](https://attacker.example/unique)\n```",
    "- <div>\n  ```\n  </div>\n![x](u)\n```\n   ### Severity\n> ### CWE\n",
    "`a` `` b `` ```` c ````` d\n``````\n### Severity\n",
    "    ```\n### Severity\n\t```\n``` a`b\n",
]


def _block_roles(text: str) -> list[str]:
    """The fence roles of the description section's lines, opener to closer."""
    lines = text.split("\n")
    start = next(i for i, line in enumerate(lines) if line.endswith("text") and line.startswith("```"))
    roles = fence_roles(lines)
    end = roles.index("close", start)
    return roles[start : end + 1]


@pytest.mark.parametrize("report", HOSTILE)
def test_the_report_renders_as_one_inert_block(report: str) -> None:
    block = body.inert_block(report)
    assert block["ok"]
    fence = body.fence_for(report)
    lines = report.rstrip("\n").split("\n")
    # Every line that would end a field (and every such line behind markers),
    # whatever its name, and every machine-marker line.
    expected_escapes = [
        n
        for n, line in enumerate(lines, 1)
        if loose_heading_name(line) is not None or line.lstrip(" \t").startswith("<!--")
    ]
    assert block["escaped_lines"] == expected_escapes
    # Byte-exact except the escaped lines, which gain a leading backslash.
    content = [("\\" + line if n in expected_escapes else line) for n, line in enumerate(lines, 1)]
    assert block["text"] == f"{fence}text\n" + "\n".join(content) + f"\n{fence}"
    text = body.render({"issue_description": block["text"], "severity": "Low"})
    assert body.verify(text) is None
    # Exactly the template fields, once each; everything in the block is code.
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())
    roles = _block_roles(text)
    assert roles[0] == "open" and roles[-1] == "close"
    assert set(roles[1:-1]) <= {"code"}
    result = normalise_fields(text, list(body.DEFAULT_HEADINGS.values()))
    assert result.needs_decision == []
    assert result.changes == []


def test_the_fence_is_one_longer_than_the_longest_backtick_run() -> None:
    assert body.fence_for("no ticks") == "```"
    assert body.fence_for("a `b` c") == "```"
    assert body.fence_for("```") == "````"
    assert body.fence_for("x ```````` y\n``` z") == "`" * 9


def test_a_fenced_field_heading_cannot_reach_the_cve_record() -> None:
    from generate_cve_json.cve_json import extract_field

    block = body.inert_block("PoC:\n````\n### Severity\n\nCritical\n```\n# comment\n")["text"]
    text = body.render({"issue_description": block, "severity": "Low"})
    assert extract_field(text, "Severity") == "Low"
    # The known-field heading gains a backslash; every other line stays byte-exact.
    assert "\\### Severity\n\nCritical\n```\n# comment\n" in text


def test_an_empty_report_reads_no_response() -> None:
    assert body.inert_block(" \n\n")["text"] == ""
    text = body.render({"issue_description": body.inert_block("")["text"]})
    assert "### The issue description\n\n_No response_\n" in text


def test_pii_redaction_tokens_pass_through_unchanged() -> None:
    report = "Reported with N-a3f9d2 (E-b8c247); see H-0c11aa.\n"
    rendered = body.render(
        {"issue_description": body.inert_block(report)["text"], "reporter_credit": "N-a3f9d2"}
    )
    assert "N-a3f9d2 (E-b8c247); see H-0c11aa." in rendered
    assert "### Reporter credited as\n\nN-a3f9d2\n" in rendered


def test_crlf_and_lone_cr_become_lf() -> None:
    assert body.inert_block("a\r\n### b\rc")["text"] == "```text\na\n\\### b\nc\n```"


@pytest.mark.parametrize("line", ["### Steps to reproduce", "###", "###\tanything", "> - ### Notes"])
def test_every_line_that_would_end_a_field_is_escaped(line: str) -> None:
    # The body-field contract: any `###` line at column 0 ends a field, inside the
    # block or not, so none may reach the body unescaped, known name or not.
    block = body.inert_block(f"intro\n{line}\nrest")
    assert block["escaped_lines"] == [2]
    assert f"\n\\{line}\n" in block["text"]
    text = body.render({"issue_description": block["text"]})
    assert reuse.fields(text) == list(body.DEFAULT_HEADINGS.values())
    assert body.verify(text) is None


@pytest.mark.parametrize("char", ["\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"])
def test_other_line_breaks_fail_closed(char: str) -> None:
    out = body.inert_block(f"intro{char}### Severity\nCritical")
    assert (out["ok"], out["indicator"]) == (False, "line break")
    with pytest.raises(ValueError, match="line-break"):
        body.short_field(f"Alice{char}### CWE")


def test_the_injection_callout_keeps_the_block_inert() -> None:
    block = body.inert_block("```\n### Severity\n")["text"]
    text = body.render({"issue_description": block}, callout=True)
    assert body.verify(text) is None


def test_verify_refuses_a_body_that_is_not_canonical() -> None:
    assert "ambiguous" in str(body.verify(body.render({"issue_description": "### Severity\n\nHigh"})))
    raw = body.render({"issue_description": "x"}).replace("### CWE", "###  CWE")
    assert "not canonical" in str(body.verify(raw))
    unclosed = body.render({"issue_description": "```\nx"})
    assert body.verify(unclosed) is not None


MARKER = "<!-- generate-cve-json: cve=UNKNOWN version=v1 -->"


@pytest.mark.parametrize(
    "report",
    [
        f"intro\n{MARKER}\nrest",
        f"  {MARKER}\n<!-- generate-cve-json:end cve=UNKNOWN version=v1 -->\n",
        f"```\n{MARKER}\n```\n",
        "<!-- apache-magpie: status-rollup v1 -->\n",
    ],
)
def test_no_machine_marker_travels_in_report_text(report: str) -> None:
    block = body.inert_block(report)
    text = body.render({"issue_description": block["text"], "reporter_credit": MARKER})
    assert block["escaped_lines"]
    for line in text.split("\n"):
        assert not line.lstrip(" \t").startswith("<!--"), line
    assert "&lt;!-- generate-cve-json" in text  # the short field is escaped too
    assert body.verify(text) is None


def test_inert_block_is_linear_in_long_whitespace_runs() -> None:
    import time

    spaces = " " * 100_000
    report = f"###{spaces}Severity{spaces}#\n> -{spaces}### CWE{spaces}\n{spaces}<!--{spaces}\n"
    start = time.perf_counter()
    block = body.inert_block(report)
    text = body.render({"issue_description": block["text"]})
    assert body.verify(text) is None
    assert time.perf_counter() - start < 1.0
    assert block["escaped_lines"] == [1, 2, 3]
