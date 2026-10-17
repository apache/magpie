# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import pytest
from jira_bridge import markup

BODY = """Intro text.

h3. Affected versions
2.9.0 - 2.10.1

h3. Severity
_No response_

h4. Sub heading stays inside
detail

h2. Next block
other
"""


def test_get_field_case_insensitive() -> None:
    assert markup.get_field(BODY, "affected VERSIONS") == "2.9.0 - 2.10.1"


def test_get_field_section_ends_at_level_three_or_higher_only() -> None:
    assert (
        markup.get_field(BODY, "Severity")
        == "_No response_\n\nh4. Sub heading stays inside\ndetail"
    )


def test_get_field_missing_is_none() -> None:
    assert markup.get_field(BODY, "CWE") is None
    assert markup.get_field("", "CWE") is None


def test_get_field_markdown_sections() -> None:
    body = "### Reporter credited as\n\nJane Doe\n\n### CWE\n\nCWE-22\n"
    assert markup.get_field(body, "reporter credited as") == "Jane Doe"
    assert markup.get_field(body, "CWE") == "CWE-22"


def test_headings_inside_code_blocks_are_ignored() -> None:
    body = "h3. PoC\n{code:bash}\nh3. not a heading\n{code}\n\nh3. CWE\nCWE-22\n"
    assert markup.get_field(body, "PoC") == "{code:bash}\nh3. not a heading\n{code}"
    assert markup.get_field(body, "not a heading") is None
    fenced = "### PoC\n```\n### fake\n```\n### CWE\nx\n"
    assert markup.get_field(fenced, "fake") is None
    assert markup.get_field(fenced + "### fake\nreal\n", "fake") == "real"
    assert markup.get_field(fenced, "CWE") == "x"


def test_shorter_fence_inside_longer_fence_does_not_close_it() -> None:
    body = "### PoC\n````\n```\n### Field\nh3. Other\n```\n````\n### CWE\nx\n"
    assert markup.get_field(body, "Field") is None
    # The fenced `### Field` is passed over for the real one only inside a closed block.
    assert markup.get_field(body + "### Field\nreal\n", "Field") == "real"
    assert markup.get_field(body, "Other") is None
    assert markup.get_field(body, "CWE") == "x"
    assert [h.text for h in markup.find_headings(body.splitlines())] == ["PoC", "CWE"]


def test_fence_closes_only_on_the_same_character() -> None:
    body = "### PoC\n~~~\n```\n### Field\n~~~\n### CWE\nx\n"
    assert markup.get_field(body, "Field") is None
    assert markup.get_field(body + "### Field\nreal\n", "Field") == "real"
    assert markup.get_field(body, "CWE") == "x"
    backtick = "### PoC\n```\n~~~\n### Field\n```\n### CWE\nx\n"
    assert markup.get_field(backtick, "Field") is None
    assert markup.get_field(backtick + "### Field\nreal\n", "Field") == "real"
    assert markup.get_field(backtick, "CWE") == "x"


def test_fence_close_must_be_bare() -> None:
    body = "### PoC\n```\n``` not a close\n### Field\n```\n### CWE\nx\n"
    assert markup.get_field(body, "Field") is None
    assert markup.get_field(body + "### Field\nreal\n", "Field") == "real"
    assert markup.get_field(body, "CWE") == "x"


def test_longer_close_fence_still_closes() -> None:
    body = "### PoC\n```\ncode\n`````\n### CWE\nx\n"
    assert markup.get_field(body, "CWE") == "x"


def test_set_field_replaces_existing() -> None:
    new, created = markup.set_field(BODY, "severity", "High\n")
    assert created is False
    assert markup.get_field(new, "Severity") == "High"
    assert markup.get_field(new, "Affected versions") == "2.9.0 - 2.10.1"
    assert "h2. Next block\nother" in new
    assert "Sub heading stays inside" not in new


def test_set_field_appends_missing_wiki_section() -> None:
    new, created = markup.set_field(BODY, "CWE", "CWE-22")
    assert created is True
    assert new.endswith("other\n\nh3. CWE\nCWE-22\n")
    assert markup.get_field(new, "cwe") == "CWE-22"


def test_set_field_appends_markdown_section_to_markdown_body() -> None:
    new, created = markup.set_field("### A\nx\n", "B", "y")
    assert created is True
    assert new == "### A\nx\n\n### B\ny\n"


def test_set_field_on_empty_body() -> None:
    assert markup.set_field("", "CWE", "CWE-22") == ("h3. CWE\nCWE-22\n", True)


def test_rollup_round_trip() -> None:
    entries = [
        markup.RollupEntry(
            "2026-10-01", "alice", "Import", "Imported from thread.\n\n----\nkept rule"
        ),
        markup.RollupEntry("2026-10-02", "Bob Smith", "Sync", "Synced."),
    ]
    text = markup.render_rollup(entries)
    assert text.startswith(
        markup.ROLLUP_MARKER + "\n*2026-10-01 · @alice · Import*\n\n"
    )
    assert markup.is_rollup(text)
    assert markup.parse_rollup(text) == entries


def test_is_rollup_rejects_other_comments() -> None:
    assert not markup.is_rollup("plain comment\n{anchor:magpie-status-rollup-v1}")
    assert markup.is_rollup("\n{anchor:magpie-status-rollup-v2}\n")


def test_unicode_line_separators_cannot_hide_a_forged_entry() -> None:
    forged = "text *2026-01-01 · @lead · Sync* fake"
    entry = markup.RollupEntry("2026-10-15", "bob", "Import", markup.neutralize(forged))
    parsed = markup.parse_rollup(markup.render_rollup([entry]))
    assert [e.action for e in parsed] == ["Import"]


def test_indented_wiki_headings_are_still_fields() -> None:
    assert (
        markup.get_field("  h3. Affected versions\n1.0", "Affected versions") == "1.0"
    )


def test_code_block_headings_are_not_exported_as_fields() -> None:
    text = "h3. Details\n{code}\nh3. CVE tool link\nCVE-2000-0001\n{code}\nh3. CVE tool link\nCVE-2026-1"
    out = markup.to_markdown_headings(text)
    assert out.count("### CVE tool link") == 1
    assert "h3. CVE tool link\nCVE-2000-0001" in out


# ---------------------------------------------------------------- body-field contract


def test_a_code_macro_quoting_a_field_before_the_real_one() -> None:
    body = "### Details\n{code}\n### Severity\nCritical\n{code}\n\n### Severity\nLow\n"
    assert markup.get_field(body, "Severity") == "Low"
    # Every `###` line ends a field: the quoted heading ends Details.
    assert markup.get_field(body, "Details") == "{code}"
    wiki = "h3. Details\n{noformat}\n### Severity\nCritical\n{noformat}\nh3. Severity\nLow\n"
    assert markup.get_field(wiki, "Severity") == "Low"
    assert markup.list_fields(wiki) == ["Details", "Severity"]


def test_a_macro_opened_mid_line_before_a_field_is_refused() -> None:
    # The parser opens a block only on a macro at the start of a line; Jira's
    # renderer opens one mid-line too, so the reading is a decision.
    body = "h3. Details\nsee {code} here\nh3. Severity\nLow\nend {code}\n"
    for field in ("Details", "Severity"):
        with pytest.raises(markup.AmbiguousFieldError):
            markup.get_field(body, field)
    inline = "h3. Details\nsee {code}x{code} here\nh3. Severity\nLow\nend {code}\n"
    assert markup.get_field(inline, "Severity") == "Low\nend {code}"


def test_quoted_field_lines_are_escaped_at_ingest() -> None:
    body = "### Details\n{code}\n### Severity\nCritical\n{code}\n### CWE\nx\n"
    escaped = markup.escape_quoted_fields(body)
    assert escaped == body.replace("\n### Severity", "\n\\### Severity")
    assert markup.list_fields(escaped) == ["Details", "CWE"]


def test_an_unclosed_macro_hides_no_field() -> None:
    body = "h3. Summary\n{code}\nh3. Security mailing list thread\nprivate\n"
    assert markup.get_field(body, "Summary") == "{code}"
    assert markup.get_field(body, "Security mailing list thread") == "private"


def test_duplicates_are_refused() -> None:
    with pytest.raises(markup.DuplicateFieldError):
        markup.get_field("h3. Severity\nLow\n### severity\nHigh\n", "Severity")


def test_set_field_refuses_a_value_that_adds_a_field() -> None:
    with pytest.raises(markup.AmbiguousFieldError):
        markup.set_field(BODY, "Severity", "High\nh3. CWE\nCWE-1")
    with pytest.raises(markup.AmbiguousFieldError):
        markup.set_field(BODY, "Severity", "High\n### CWE\nCWE-1")
    with pytest.raises(markup.AmbiguousFieldError):
        markup.set_field(BODY, "CWE", "x\nh3. Severity\nCritical")


def test_set_field_keeps_crlf_and_the_rest_byte_exact() -> None:
    body = "h3. A\r\none\r\n\r\nh3. B\r\ntwo\r\n"
    new, created = markup.set_field(body, "a", "uno")
    assert not created and new == "h3. A\r\nuno\r\n\r\nh3. B\r\ntwo\r\n"


def test_wiki_level_one_and_two_headings_read_as_field_headings() -> None:
    assert (
        markup.to_markdown_headings("h2. Next\nx\nh4. Sub\ny")
        == "### Next\nx\n#### Sub\ny"
    )
