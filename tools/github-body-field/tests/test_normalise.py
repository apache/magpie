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
"""CommonMark fence pairing, lenient headings and `normalise`."""

from __future__ import annotations

import json

import pytest

from github_body_field import cli
from github_body_field.parser import (
    DuplicateFieldError,
    FieldNotFoundError,
    extract_field,
    fence_roles,
    list_fields,
    normalise,
    replace_field,
)

KNOWN = ["Short public summary for publish", "Affected versions", "Severity", "CWE"]


def kinds(result) -> list[tuple[int, str]]:
    return [(int(c["line"]), str(c["kind"])) for c in result.changes]


# ---------------------------------------------------------------------------
# Headings the parser accepts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "heading",
    [
        "###  Severity",  # two spaces
        "###\tSeverity",  # a tab
        "   ### Severity",  # three-space indent
        "### Severity ###",  # closing sequence
        "### Severity #",
        "### Severity   ",  # trailing whitespace
    ],
)
def test_lenient_level_3_headings_are_fields(heading: str) -> None:
    body = f"{heading}\n\nLow\n\n### CWE\n\nCWE-79\n"
    assert list_fields(body) == ["Severity", "CWE"]
    assert extract_field(body, "Severity") == "Low\n"
    result = normalise(body)
    assert result.text == "### Severity\n\nLow\n\n### CWE\n\nCWE-79\n"
    assert kinds(result) == [(1, "heading")]


@pytest.mark.parametrize("line", ["    ### Severity", "#### Severity", "## Severity", "###Severity"])
def test_not_a_level_3_heading(line: str) -> None:
    body = f"### CWE\n\nx\n{line}\n"
    assert list_fields(body) == ["CWE"]
    assert normalise(body).text == body


def test_closing_hashes_without_a_space_are_part_of_the_name() -> None:
    assert list_fields("### C# #\n") == ["C#"]


def test_known_fields_canonicalise_case_and_spacing() -> None:
    body = "### short  public SUMMARY for publish\n\ntext\n\n### severity\n\nLow\n"
    result = normalise(body, KNOWN)
    assert list_fields(result.text) == ["Short public summary for publish", "Severity"]
    assert kinds(result) == [(1, "heading_name"), (5, "heading_name")]
    # Without the known names the spelling is left as written.
    assert normalise(body).text == body


def test_crlf_and_lone_cr_become_lf() -> None:
    body = "###  Severity\r\n\r\nLow\r\n\r\n### CWE\rCWE-79\r"
    result = normalise(body, KNOWN)
    assert result.text == "### Severity\n\nLow\n\n### CWE\nCWE-79\n"
    assert kinds(result) == [(1, "heading"), (1, "line_endings")]
    # The parser itself treats CR and CRLF as line endings too.
    assert list_fields(body) == ["Severity", "CWE"]


def test_other_line_break_characters_are_not_line_endings() -> None:
    # U+2028 and form feed break lines for str.splitlines, not for CommonMark.
    body = "### A\n\nx" + chr(0x2028) + "### B\x0c### C\n"
    assert list_fields(body) == ["A"]


# ---------------------------------------------------------------------------
# Fences
# ---------------------------------------------------------------------------


def test_four_backtick_fence_holding_three_backticks_keeps_its_content() -> None:
    body = "### A\n\n````\n```\n### Severity\n```\n````\n\n### Severity\n\nLow\n"
    assert fence_roles(body.split("\n")) == [
        "text", "text", "open", "code", "code", "code", "close", "text", "text", "text", "text", "text",
    ]  # fmt: skip
    assert list_fields(body) == ["A", "Severity"]
    assert extract_field(body, "Severity") == "Low\n"


def test_tilde_fence_is_not_closed_by_backticks() -> None:
    body = "### A\n\n~~~\n```\n### Severity\n~~~\n\n### B\n\nx\n"
    assert list_fields(body) == ["A", "B"]
    body = "### A\n\n```\n~~~\n### Severity\n```\n\n### B\n\nx\n"
    assert list_fields(body) == ["A", "B"]


def test_closer_needs_nothing_but_whitespace_after_the_run() -> None:
    body = "```\n``` not a closer\n### Hidden\n```  \t\n### Seen\n"
    assert list_fields(body) == ["Seen"]


def test_backtick_info_string_with_a_backtick_is_not_a_fence() -> None:
    assert list_fields("``` a`b\n### Seen\n") == ["Seen"]


def test_four_space_indent_is_not_a_fence() -> None:
    assert list_fields("    ```\n### Seen\n") == ["Seen"]


def test_unclosed_fence_hides_the_rest_and_is_closed_by_normalise() -> None:
    body = "### A\n\n````py\ncode\n### B\n"
    assert list_fields(body) == ["A"]
    result = normalise(body)
    assert result.text == "### A\n\n````py\ncode\n\\### B\n````\n"
    assert kinds(result) == [(3, "unclosed_fence"), (5, "heading_in_fence")]


def test_unclosed_fence_without_a_final_newline() -> None:
    assert normalise("```\ncode").text == "```\ncode\n```\n"


def test_heading_inside_a_fence_is_escaped() -> None:
    body = "### A\n\n```\n# one\n  ### Severity\n#### four\n#hashtag\n```\n"
    result = normalise(body)
    assert result.text == "### A\n\n```\n\\# one\n  \\### Severity\n\\#### four\n#hashtag\n```\n"
    assert kinds(result) == [(4, "heading_in_fence"), (5, "heading_in_fence"), (6, "heading_in_fence")]
    assert list_fields(result.text) == ["A"]


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------


def test_equal_duplicates_are_collapsed_to_the_first() -> None:
    body = "### Severity\n\nLow\n\n### CWE\n\nx\n\n### Severity\n\n Low \n"
    result = normalise(body)
    assert result.text == "### Severity\n\nLow\n\n### CWE\n\nx\n"
    assert kinds(result) == [(9, "duplicate_dropped")]
    assert result.needs_decision == []


def test_differing_duplicates_need_a_decision_and_are_left_alone() -> None:
    body = "### Affected versions\n\n< 1.0\n\n### CWE\n\nx\n\n### Affected versions\n\n< 2.0\n"
    result = normalise(body)
    assert result.text == body
    assert result.changes == []
    assert result.needs_decision == [{"field": "Affected versions", "kind": "duplicate", "lines": [1, 9]}]
    with pytest.raises(DuplicateFieldError):
        extract_field(body, "Affected versions")


def test_a_decision_resolves_a_duplicate() -> None:
    body = "### Affected versions\n\n< 1.0\n\n### CWE\n\nx\n\n### Affected versions\n\n< 2.0\n"
    result = normalise(body, keep={"Affected versions": 9})
    assert result.needs_decision == []
    assert result.text == "### CWE\n\nx\n\n### Affected versions\n\n< 2.0\n"
    assert kinds(result) == [(1, "duplicate_resolved")]
    # A keep line that is not one of the copies decides nothing.
    assert normalise(body, keep={"Affected versions": 5}).needs_decision != []


def test_duplicates_spelled_differently_are_found_once_canonical() -> None:
    body = "###  Severity\n\nLow\n\n### severity\n\nLow\n"
    result = normalise(body, KNOWN)
    assert result.text == "### Severity\n\nLow\n"


def test_duplicate_inside_a_fence_is_not_a_duplicate() -> None:
    body = "### Severity\n\nLow\n\n```\n### Severity\n```\n"
    assert normalise(body).needs_decision == []


def test_duplicate_errors_are_field_not_found_errors() -> None:
    assert issubclass(DuplicateFieldError, FieldNotFoundError)


# ---------------------------------------------------------------------------
# Idempotency and the other readers agreeing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "",
        "no headings\n",
        "### A\n\nx\n",
        "### A\r\n\r\n```\r\n### B\r\n",
        "###  a\n\n````\n```\n# x\n```\n\n### a\n\n\n",
        "### Severity\n\nLow\n\n### Severity\n\nHigh\n",
    ],
)
def test_normalise_is_idempotent(body: str) -> None:
    once = normalise(body, KNOWN)
    twice = normalise(once.text, KNOWN)
    assert twice.text == once.text
    assert twice.changes == []


def test_replace_field_stays_byte_exact_on_a_crlf_body() -> None:
    body = "### A\r\n\r\nx\r\n\r\n### B\r\n\r\ny\r\n"
    new = replace_field(body, "B", "z\n")
    assert new.startswith("### A\r\n\r\nx\r\n\r\n### B\r\n")
    assert list_fields(new) == ["A", "B"]


def test_replace_field_finds_a_lenient_heading_and_keeps_it() -> None:
    body = "###  A ##\n\nx\n\n### B\n\ny\n"
    assert replace_field(body, "A", "z") == "###  A ##\n\nz\n\n### B\n\ny\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_normalise_reports_and_writes_locally(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "body.md"
    src.write_text("###  severity\n\nLow\n\n### Severity\n\nHigh\n", encoding="utf-8")
    fields = tmp_path / "fields.json"
    fields.write_text(json.dumps(KNOWN), encoding="utf-8")
    out = tmp_path / "out.md"
    rc = cli.main(["normalise", "--body-file", str(src), "--fields-json", str(fields), "--output", str(out)])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["needs_decision"] == [{"field": "Severity", "kind": "duplicate", "lines": [1, 5]}]
    assert report["changed"] is True
    assert "text" not in report  # the body never reaches stdout
    assert out.read_text(encoding="utf-8").startswith("### Severity\n")

    rc = cli.main(
        ["normalise", "--body-file", str(src), "--fields-json", str(fields), "--keep", "Severity=5"]
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["needs_decision"] == []


def test_cli_normalise_needs_exactly_one_source(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["normalise"]) == 2
    src = tmp_path / "b.md"
    src.write_text("x", encoding="utf-8")
    assert cli.main(["normalise", "1", "--body-file", str(src)]) == 2
    with pytest.raises(SystemExit):
        cli.main(["normalise", "--body-file", str(src), "--keep", "Severity"])
