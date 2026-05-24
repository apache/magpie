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
"""Tests for ``redactor.redact`` — the ``pii-redact`` CLI."""

from __future__ import annotations

import io
import pathlib
from collections.abc import Iterator

import pytest

from redactor import redact
from redactor.mapping import load_mapping


@pytest.fixture()
def mapping_path(tmp_path: pathlib.Path, monkeypatch) -> Iterator[pathlib.Path]:
    """Pin the mapping file to a tmp path for the duration of the test."""
    path = tmp_path / "pii-mapping.json"
    monkeypatch.setenv("PII_MAPPING_PATH", str(path))
    yield path


def _run(monkeypatch, stdin_text: str, argv: list[str]) -> tuple[str, int]:
    """Invoke ``redact.main`` with ``stdin_text`` and capture stdout."""
    stdin = io.StringIO(stdin_text)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)
    rc = redact.main(argv)
    return stdout.getvalue(), rc


# -- field parsing -------------------------------------------------------


def test_parse_field_friendly_name():
    assert redact.parse_field("name:Jane Smith") == ("N", "Jane Smith")


def test_parse_field_code():
    assert redact.parse_field("N:Jane Smith") == ("N", "Jane Smith")


def test_parse_field_value_can_contain_colon():
    """An email address containing ``:`` must round-trip through the parser."""
    assert redact.parse_field("email:foo:bar@example.com") == ("E", "foo:bar@example.com")


def test_parse_field_rejects_missing_colon():
    with pytest.raises(SystemExit, match="must be of the form"):
        redact.parse_field("just-a-value")


def test_parse_field_rejects_unknown_type():
    with pytest.raises(SystemExit, match="unknown field type"):
        redact.parse_field("nope:value")


def test_parse_field_rejects_empty_value():
    with pytest.raises(SystemExit, match="value is empty"):
        redact.parse_field("name:")


def test_field_help_text_lists_real_type_names(monkeypatch):
    """The ``--field`` help must name types the parser accepts.

    Regression: the help listed ``reporter`` / code ``R``, neither of
    which exists. A user copying the help got ``SystemExit`` and their
    PII flowed to the LLM unredacted.
    """
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    with pytest.raises(SystemExit):
        redact.main(["--help"])
    # argparse wraps the help line; collapse whitespace before matching.
    help_text = " ".join(stdout.getvalue().split())
    assert "reporter" not in help_text
    assert "name, email, phone, ip, handle, address" in help_text


# -- end-to-end redaction ------------------------------------------------


def test_redact_replaces_values_with_identifiers(mapping_path, monkeypatch):
    body = "Hi I am Jane Smith and you can email me at jane@example.com."
    out, rc = _run(
        monkeypatch,
        body,
        ["--field", "name:Jane Smith", "--field", "email:jane@example.com"],
    )
    assert rc == 0
    assert "Jane Smith" not in out
    assert "jane@example.com" not in out
    assert "N-" in out
    assert "E-" in out


def test_redact_persists_mapping(mapping_path, monkeypatch):
    _, rc = _run(
        monkeypatch,
        "Jane Smith",
        ["--field", "name:Jane Smith"],
    )
    assert rc == 0
    mapping = load_mapping(mapping_path)
    # Exactly one entry, of type name, value "Jane Smith".
    assert len(mapping) == 1
    [entry] = mapping.values()
    assert entry.type == "name"
    assert entry.value == "Jane Smith"


def test_redact_idempotent_across_runs(mapping_path, monkeypatch):
    """Running redact twice with the same field produces the same identifier."""
    out_a, _ = _run(monkeypatch, "Jane Smith", ["--field", "name:Jane Smith"])
    out_b, _ = _run(monkeypatch, "Jane Smith", ["--field", "name:Jane Smith"])
    assert out_a == out_b
    assert len(load_mapping(mapping_path)) == 1


def test_redact_no_fields_passes_input_through(mapping_path, monkeypatch):
    """No ``--field`` declared → stdin → stdout unchanged."""
    out, rc = _run(monkeypatch, "untouched text", [])
    assert rc == 0
    assert out == "untouched text"
    assert load_mapping(mapping_path) == {}


def test_redact_replaces_all_occurrences(mapping_path, monkeypatch):
    body = "Jane Smith said. Then Jane Smith left. Finally Jane Smith returned."
    out, _ = _run(monkeypatch, body, ["--field", "name:Jane Smith"])
    assert "Jane Smith" not in out
    # Exactly three identifiers in the output.
    mapping = load_mapping(mapping_path)
    [entry] = mapping.values()
    assert out.count(entry.identifier) == 3


def test_redact_substring_safety(mapping_path, monkeypatch):
    """A short value that is a substring of a longer value should not break the longer match.

    Reporter ``Jane`` is a substring of email ``jane@example.com``.
    With longest-first substitution the email is replaced first,
    so the email's identifier never gets re-redacted by the
    reporter pass.
    """
    body = "Jane wrote from jane@example.com."
    out, _ = _run(
        monkeypatch,
        body,
        ["--field", "name:Jane", "--field", "email:jane@example.com"],
    )
    # The email's identifier should be intact (not contain "N-").
    mapping = load_mapping(mapping_path)
    email_entry = next(e for e in mapping.values() if e.type == "email")
    assert email_entry.identifier in out
    # The standalone "Jane" should be redacted.
    reporter_entry = next(e for e in mapping.values() if e.type == "name")
    assert reporter_entry.identifier in out


def test_redact_missing_value_in_input_is_silent(mapping_path, monkeypatch):
    """Declaring a ``--field`` whose value is absent from stdin is a no-op on the text."""
    body = "no PII here"
    out, _ = _run(monkeypatch, body, ["--field", "name:Absent Person"])
    assert out == "no PII here"
    # The value was still recorded in the mapping (skill's
    # responsibility to declare; we trust the declaration).
    mapping = load_mapping(mapping_path)
    assert len(mapping) == 1


def test_redact_returns_2_on_malformed_mapping_file(mapping_path, monkeypatch):
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text("not json")
    monkeypatch.setattr("sys.stdin", io.StringIO("ignored"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    rc = redact.main(["--field", "name:Jane Smith"])
    assert rc == 2


def test_redact_case_insensitive(mapping_path, monkeypatch):
    """The matcher should redact lowercase / uppercase variants of the declared value."""
    body = "Jane Smith reported. jane smith confirmed. JANE SMITH signed off."
    out, _ = _run(monkeypatch, body, ["--field", "name:Jane Smith"])
    mapping = load_mapping(mapping_path)
    [entry] = mapping.values()
    # All three case variants get the same identifier.
    assert out.count(entry.identifier) == 3
    assert "Jane Smith" not in out
    assert "jane smith" not in out
    assert "JANE SMITH" not in out


def test_redact_whitespace_normalised(mapping_path, monkeypatch):
    """The matcher should redact double-spaced and tab-separated variants of the declared value."""
    body = "Hello Jane Smith. Hello Jane  Smith. Hello Jane\tSmith. Hello Jane\xa0Smith."
    out, _ = _run(monkeypatch, body, ["--field", "name:Jane Smith"])
    mapping = load_mapping(mapping_path)
    [entry] = mapping.values()
    # Single-space, double-space, tab, NBSP — four variants, same identifier.
    assert out.count(entry.identifier) == 4
    assert "Jane Smith" not in out
    assert "Jane  Smith" not in out
    assert "Jane\tSmith" not in out
    assert "Jane\xa0Smith" not in out


def test_redact_does_not_match_across_newlines(mapping_path, monkeypatch):
    """The whitespace class is `[^\\S\\n]+` — newlines stop the match.

    A name spanning a paragraph break almost never represents the
    same person; matching there risks redacting unrelated content
    that happens to share endpoint tokens.
    """
    body = "First Jane\nSecond Smith"
    out, _ = _run(monkeypatch, body, ["--field", "name:Jane Smith"])
    mapping = load_mapping(mapping_path)
    [entry] = mapping.values()
    # The body did NOT contain "Jane Smith" — declared name is absent
    # in the literal in-line sense, so identifier should not appear.
    assert entry.identifier not in out
    assert out == body
