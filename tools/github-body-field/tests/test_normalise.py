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
    AmbiguousFieldError,
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


@pytest.mark.parametrize(
    "line", ["   ### Severity", "    ### Severity", "#### Severity", "## Severity", "###Severity"]
)
def test_not_a_level_3_heading(line: str) -> None:
    body = f"### CWE\n\nx\n{line}\n"
    assert list_fields(body) == ["CWE"]
    assert normalise(body).text == body


def test_closing_hashes_without_a_space_are_part_of_the_name() -> None:
    assert list_fields("### C# #\n") == ["C#"]


def test_known_fields_canonicalise_spacing_but_keep_case() -> None:
    body = "### Short  public summary\tfor publish\n\ntext\n\n###  Affected versions\n\n< 2\n"
    result = normalise(body, KNOWN)
    assert list_fields(result.text) == ["Short public summary for publish", "Affected versions"]
    assert kinds(result) == [(1, "heading_name"), (5, "heading")]
    # Without the known names the inner spacing is left as written.
    assert list_fields(normalise(body).text)[0] == "Short  public summary\tfor publish"


def test_a_differently_cased_heading_is_content_not_the_field() -> None:
    # A reporter's own "### Affected Versions" (capital V) in the description, as main read it.
    body = (
        "### The issue description\n\n### Affected Versions\n\nall of them\n\n"
        "### Affected versions\n\n< 2.0\n"
    )
    result = normalise(body, KNOWN)
    assert result.needs_decision == []
    assert result.text == body
    assert extract_field(body, "Affected versions") == "< 2.0\n"
    nested = "### A\n\n> ### severity\n\n### Severity\n\nLow\n"
    assert normalise(nested, KNOWN).needs_decision == []


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


def test_an_unclosed_fence_hides_nothing_and_is_closed_in_its_own_field() -> None:
    # The body-field contract: every `###` line at column 0 ends a field, and a
    # block left open marks nothing, so B stays a field.
    body = "### A\n\n````py\ncode\n### B\n"
    assert list_fields(body) == ["A", "B"]
    result = normalise(body)
    assert result.text == "### A\n\n````py\ncode\n````\n### B\n"
    assert kinds(result) == [(3, "unclosed_fence")]
    assert extract_field(result.text, "B") == ""


def test_unclosed_fence_without_a_final_newline() -> None:
    assert normalise("```\ncode").text == "```\ncode\n```\n"


def test_fenced_lines_stay_byte_exact() -> None:
    body = "### A\n\n```\n# one\n  ### Severity\n#### four\n#hashtag\n```\n"
    result = normalise(body)
    assert result.text == body
    assert result.changes == []
    assert list_fields(result.text) == ["A"]


def test_fenced_payloads_round_trip_through_extract_and_duplicate_resolution() -> None:
    payload = "```py\n# comment\n#### Severity\n\\escaped\n```\n"
    body = f"### Short public summary for publish\n\n{payload}\n### Severity\n\nLow\n\n### Severity\n\nHigh\n"
    result = normalise(body, KNOWN, keep={"Severity": 9})
    assert result.needs_decision == []
    assert extract_field(result.text, "Short public summary for publish") == payload
    assert extract_field(result.text, "Severity") == "Low\n"


def test_a_heading_inside_a_closed_fence_ends_the_field_but_never_becomes_it() -> None:
    # Every `###` line at column 0 ends a field, fence or not: no fence can make
    # one field absorb the next. The fence only decides which heading is the field.
    body = (
        "### Short public summary for publish\n\n```\n### Severity\nCritical\n```\n\n"
        "### Severity\n\nLow\n\n### Severity\n\nHigh\n"
    )
    assert extract_field(body, "Short public summary for publish") == "```\n"
    result = normalise(body, KNOWN, keep={"Severity": 8})
    assert result.needs_decision == []
    assert result.text.count("Critical") == 1  # the fenced copy is never dropped or rewritten
    assert extract_field(result.text, "Severity") == "Low\n"
    # With no copy outside a closed block, the field is absent: quoted text never becomes it.
    with pytest.raises(FieldNotFoundError):
        extract_field("### A\n\n```\n### B\n\nquoted\n```\n", "B")


def test_replace_refuses_a_span_holding_a_heading_shaped_line() -> None:
    body = "### The issue description\n\nreport\n\n   ### Severity\n\nHigh\n"
    with pytest.raises(AmbiguousFieldError, match="heading-shaped"):
        replace_field(body, "The issue description", "new report")
    # A fenced `### Severity` ends the field; replacing the value would take
    # the heading out of its closed block, so that is refused too.
    fenced = "### The issue description\n\n```\n### Severity\n```\n\n### CWE\n\nx\n"
    with pytest.raises(AmbiguousFieldError, match="another field"):
        replace_field(fenced, "The issue description", "new")
    # A fenced line that ends no field does not block the rewrite.
    fenced = "### The issue description\n\n```\n#### Severity\n```\n\n### CWE\n\nx\n"
    assert replace_field(fenced, "The issue description", "new").startswith(
        "### The issue description\n\nnew\n\n### CWE"
    )


def test_replace_refuses_a_new_value_that_would_add_a_field() -> None:
    body = "### A\n\nx\n\n### B\n\ny\n"
    for value in ("z\n\n### Severity\n\nHigh", "> ### B\n", "```\n###\n```", "x\r###\tB"):
        with pytest.raises(AmbiguousFieldError):
            replace_field(body, "A", value)


def test_spacing_variant_after_an_indented_list_fence_is_a_duplicate() -> None:
    # `###  Severity` at column 0 ends a field whatever fence is open before it.
    complete = "### Severity\n\nLow\n\n### CWE\n\nx\n\n"
    body = complete + "- item\n   ```\n\n###  Severity\n\nHigh\n"
    decisions = normalise(body, KNOWN).needs_decision
    assert decisions == [{"field": "Severity", "kind": "duplicate", "lines": [1, 12]}]


def test_long_whitespace_runs_parse_in_linear_time() -> None:
    import time

    spaces = " " * 100_000
    body = f"### A{spaces}x\n\n###{spaces}Severity{spaces}#{spaces}\n\nLow\n\n> -{spaces}### CWE{spaces}x\n"
    start = time.perf_counter()
    normalise(body, KNOWN)
    list_fields(body)
    assert time.perf_counter() - start < 1.0


def test_cli_keeps_crlf_bytes_from_a_body_file(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "b.md"
    src.write_bytes(b"### A\r\n\r\nx\r\n")
    out = tmp_path / "o.md"
    assert cli.main(["normalise", "--body-file", str(src), "--output", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["changed"] is True
    assert report["changes"] == [{"line": 1, "kind": "line_endings"}]
    assert out.read_bytes() == b"### A\n\nx\n"
    same = tmp_path / "s.md"
    same.write_bytes(b"### A\n\nx\n")
    assert cli.main(["normalise", "--body-file", str(same), "--output", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False
    assert out.read_bytes() == same.read_bytes()


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
    body = "###  Severity\n\nLow\n\n###\tSeverity ##\n\nLow\n"
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
    src.write_text("###  Severity\n\nLow\n\n### Severity\n\nHigh\n", encoding="utf-8")
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


# ---------------------------------------------------------------------------
# Lists and block quotes: never modelled, fail closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inner", "field"),
    [
        ("- item\n   ### Severity\n   High\n", "Severity"),
        ("> ### Severity\n", "Severity"),
        (">> ### CWE\n", "CWE"),
        ("> > ### CWE\n", "CWE"),
        ("1. x\n\n   ### CWE\n", "CWE"),
        ("- item\n  ### Severity\n", "Severity"),  # continuation indented less than the content offset
        ("10. item\n  ### Severity\n", "Severity"),
        ("Some text\n---\n   ### Severity\n", "Severity"),  # after a thematic break / setext line
        ("Some text\n***\n- ### Severity\n", "Severity"),
        ("Paragraph text\n- ### Severity\n", "Severity"),  # a bullet under paragraph text
        ("Paragraph text\n2. ### CWE\n", "CWE"),  # an ordered marker other than 1 interrupting a paragraph
        ("* ### Severity ##\n", "Severity"),
    ],
)
def test_a_nested_known_field_heading_needs_a_decision(inner: str, field: str) -> None:
    body = f"### The issue description\n\nIntro\n{inner}\n### Severity\n\nLow\n\n### CWE\n\nx\n"
    lines = [n for n, line in enumerate(body.split("\n"), 1) if n > 3 and field.casefold() in line.casefold()]
    lines = [n for n in lines if not body.split("\n")[n - 1].startswith(f"### {field}")]
    # Never the field: the column-0 heading still is.
    assert list_fields(body) == ["The issue description", "Severity", "CWE"]
    # The read layer refuses the disputed field and still reads the others.
    with pytest.raises(AmbiguousFieldError):
        extract_field(body, field)
    other = "CWE" if field == "Severity" else "Severity"
    assert extract_field(body, other) == ("x\n" if other == "CWE" else "Low\n")
    result = normalise(body, KNOWN)
    assert result.text == body  # never rewritten
    assert result.needs_decision == [{"field": field, "kind": "container-heading", "lines": lines}]


def test_a_column_0_heading_under_paragraph_text_ends_the_field() -> None:
    body = "### The issue description\n\nIntro\nParagraph text\n###  Severity\n\n### Severity\n\nLow\n"
    assert list_fields(body) == ["The issue description", "Severity", "Severity"]
    assert normalise(body, KNOWN).needs_decision == [
        {"field": "Severity", "kind": "duplicate", "lines": [5, 7]}
    ]


def test_a_nested_unknown_heading_stays_content() -> None:
    body = "### A\n\n- item\n   ### Steps to reproduce\n> ### Notes\n"
    result = normalise(body, KNOWN)
    assert result.needs_decision == []
    assert list_fields(body) == ["A"]


def test_without_known_fields_nothing_is_flagged() -> None:
    assert normalise("### A\n\n> ### Severity\n").needs_decision == []


def test_column_0_headings_are_fields_whatever_precedes_them() -> None:
    body = "- item\n### Severity\n\nLow\n> quote\n### CWE\nx\n"
    assert list_fields(body) == ["Severity", "CWE"]
    assert normalise(body, KNOWN).needs_decision == []


def test_lenient_column_0_headings_are_fields_and_indented_ones_need_a_decision() -> None:
    body = "###  Severity\n   ### CWE\n\nx\n\n###\tAffected versions #\n\ny\n"
    assert list_fields(body) == ["Severity", "Affected versions"]
    result = normalise(body, KNOWN)
    assert result.needs_decision == [{"field": "CWE", "kind": "container-heading", "lines": [2]}]
    assert list_fields(result.text) == ["Severity", "Affected versions"]


def test_an_indented_fence_in_a_list_cannot_hide_a_field() -> None:
    # GitHub closes the list item's fence when the list ends; this parser does not
    # model lists, but a fence never decides where a field ends, so Severity stays
    # a field. normalise closes the fence, at its own indent, before the field.
    body = "- item\n   ```\n\n### Severity\n\nLow\n"
    result = normalise(body, KNOWN)
    assert result.needs_decision == []
    assert result.text == "- item\n   ```\n   ```\n\n### Severity\n\nLow\n"
    assert extract_field(body, "Severity") == "Low\n"


def test_fence_readers_that_disagree_cannot_move_a_field() -> None:
    # An indented fence at top level closed by a column-0 run: CommonMark closes
    # the fence there; a column-0-only reader opens one there that never closes.
    # Either way `### Severity` ends the field before it and starts its own.
    body = "### A\n\n  ```\ncode\n```\n\n### Severity\n\nLow\n"
    assert normalise(body, KNOWN).needs_decision == []
    assert extract_field(body, "Severity") == "Low\n"
    assert extract_field(body, "A") == "  ```\ncode\n```\n"


# ---------------------------------------------------------------------------
# The read/write layer fails closed on its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        "### A\n\n> ### Severity\nHigh\n\n### Severity\n\nLow\n",  # a nested copy of the field
        "### A\n\n- item\n   ### Severity\n   High\n",  # only a nested copy: not "not found"
    ],
)
def test_extract_and_replace_refuse_an_ambiguous_field(body: str) -> None:
    with pytest.raises(AmbiguousFieldError, match="refusing to guess"):
        extract_field(body, "Severity")
    with pytest.raises(AmbiguousFieldError):
        replace_field(body, "Severity", "Medium")
    assert issubclass(AmbiguousFieldError, FieldNotFoundError)


def test_an_unrelated_nested_heading_does_not_block_another_field() -> None:
    body = "### A\n\n> ### Notes\n\n### Severity\n\nLow\n"
    assert extract_field(body, "Severity") == "Low\n"
    assert extract_field(body.replace("Notes", "Severity"), "A") == "> ### Severity\n"


def test_cli_get_and_set_exit_2_on_an_ambiguous_field(monkeypatch, capsys) -> None:
    import subprocess

    body = "### A\n\n> ### Severity\nHigh\n\n### Severity\n\nLow\n"

    class Result:
        returncode = 0
        stdout = json.dumps({"body": body})
        stderr = ""

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cli.main(["get", "1", "--field", "Severity"]) == 2
    assert cli.main(["set", "1", "--field", "Severity", "--value", "Medium"]) == 2
    assert not any("edit" in c for c in calls)  # nothing was written
    assert "refusing to guess" in capsys.readouterr().err


def test_nested_heading_detection_is_linear() -> None:
    import time

    line = "> - 1. " * 15_000 + "x"  # about 100k characters, no heading at the end
    body = f"### A\n\n{line}\n\n{line} ###\n"
    start = time.perf_counter()
    result = normalise(body, KNOWN)
    list_fields(body)
    assert time.perf_counter() - start < 1.0
    assert result.needs_decision == []


@pytest.mark.parametrize("count", [65, 10_000])
def test_any_number_of_markers_still_needs_a_decision(count: int) -> None:
    for prefix in (">" * count, "> " * count, "- 1. " * count):
        body = f"### A\n\n{prefix}### Severity\n\n### Severity\n\nLow\n"
        result = normalise(body, KNOWN)
        assert result.needs_decision == [{"field": "Severity", "kind": "container-heading", "lines": [3]}]
        with pytest.raises(AmbiguousFieldError):
            extract_field(body, "Severity")


def test_ten_digit_ordered_markers_are_not_markers() -> None:
    assert normalise("### A\n\n1234567890. ### Severity\n", KNOWN).needs_decision == []


def test_replace_refuses_a_value_that_moves_another_field_into_a_block() -> None:
    # B's value opens a fence nothing closes; a fence in A's new value would pair
    # with it and put B's heading in a closed block, changing how B is chosen.
    body = "### A\n\nx\n\n### B\n\n```\n"
    with pytest.raises(AmbiguousFieldError, match="another field"):
        replace_field(body, "A", "```")
    # Fence readers that disagree no longer matter: a fence never ends a field.
    new = replace_field("### A\n\nx\n\n### B\n\ny\n", "A", "  ```\ncode\n```")
    assert new.endswith("### B\n\ny\n")


def test_jira_blocks_choose_the_heading_too() -> None:
    body = "### A\n\n{code:java}\n### Severity\nCritical\n{code}\n\n### Severity\n\nLow\n"
    assert list_fields(body) == ["A", "Severity"]
    assert extract_field(body, "Severity") == "Low\n"
    assert extract_field(body, "A") == "{code:java}\n"
    # Inline or never closed, a macro marks nothing.
    for opener in ("see `{code}` here", "{noformat}"):
        unclosed = f"### A\n\n{opener}\n### Severity\n\nHigh\n\n### Severity\n\nLow\n"
        with pytest.raises(DuplicateFieldError):
            extract_field(unclosed, "Severity")


def test_crlf_bodies_keep_their_spacers_and_line_endings() -> None:
    body = "### A\r\n\r\nx\r\n\r\n### B\r\n\r\ny\r\n"
    assert extract_field(body, "A") == "x\r\n"
    assert replace_field(body, "A", extract_field(body, "A")) == body
    assert replace_field(body, "A", "x") == body
    new = replace_field(body, "A", "one\ntwo\n")
    assert new == "### A\r\n\r\none\r\ntwo\r\n\r\n### B\r\n\r\ny\r\n"
    lone_cr = "### A\r\rx\r\r### B\r\ry\r"
    assert replace_field(lone_cr, "A", "x") == lone_cr


def test_cli_get_and_set_on_a_remote_crlf_body(monkeypatch, capsys) -> None:
    import subprocess

    body = "### A\r\n\r\nx\r\n\r\n### B\r\n\r\ny\r\n"
    writes: list[str] = []

    class Result:
        def __init__(self, stdout: str = "") -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def fake_run(cmd, input=None, **kwargs):
        if "edit" in cmd:
            writes.append(input)
            return Result()
        return Result(json.dumps({"body": body}))

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cli.main(["get", "1", "--field", "A"]) == 0
    assert capsys.readouterr().out == "x\r\n"
    assert cli.main(["set", "1", "--field", "A", "--value", "x"]) == 0
    assert writes == []  # unchanged: byte-identical, nothing written
    assert cli.main(["set", "1", "--field", "A", "--value", "z"]) == 0
    assert writes == [body.replace("\r\nx\r\n", "\r\nz\r\n")]


def test_a_jira_macro_opened_mid_line_before_a_field_is_a_decision() -> None:
    body = "### A\n\ntext {code}\n### Severity\nCritical\n{code}\n\n### CWE\n\nx\n"
    result = normalise(body, KNOWN)
    assert [(d["field"], d["kind"], d["lines"]) for d in result.needs_decision] == [
        ("Severity", "macro-ambiguous", [3, 4])
    ]
    for field in ("A", "Severity"):
        with pytest.raises(AmbiguousFieldError):
            extract_field(body, field)
    assert extract_field(body, "CWE") == "x\n"
    with pytest.raises(AmbiguousFieldError):
        replace_field("### A\n\na\n\n### B\n\nb\n\n### C\n\n{code}\n", "A", "see {code}")


def test_a_jira_macro_closed_on_its_line_stays_text() -> None:
    body = "### A\n\ninline {code}x{code} here\n### Severity\nLow\n{code}\n"
    assert normalise(body, KNOWN).needs_decision == []
    assert extract_field(body, "Severity") == "Low\n{code}\n"
    # A macro opened mid-line but never closed hides nothing either.
    assert normalise("### A\n\ntext {noformat}\n### Severity\nLow\n", KNOWN).needs_decision == []
