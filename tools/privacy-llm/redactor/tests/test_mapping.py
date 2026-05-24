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
"""Tests for ``redactor.mapping`` — hashing, persistence, collisions."""

from __future__ import annotations

import json
import pathlib

import pytest

from redactor.mapping import (
    DEFAULT_HEX_LEN,
    MAPPING_VERSION,
    Entry,
    generate_identifier,
    hash_value,
    load_mapping,
    locate_mapping_path,
    normalise_value,
    save_mapping_atomic,
    upsert,
)

# -- normalisation --------------------------------------------------------


def test_normalise_lowercases_and_trims():
    assert normalise_value("  Jane Smith  ") == "jane smith"


def test_normalise_keeps_internal_whitespace():
    # Two-space "Jane  Smith" stays distinct from "Jane Smith"
    # because internal whitespace can be intentional.
    assert normalise_value("Jane  Smith") == "jane  smith"


# -- deterministic identifiers -------------------------------------------


def test_hash_value_is_deterministic_across_case_and_whitespace():
    assert hash_value("Jane Smith") == hash_value("  jane smith  ")


def test_generate_identifier_default_length():
    ident, extended = generate_identifier("N", "Jane Smith", existing={})
    prefix, hex_part = ident.split("-", 1)
    assert prefix == "N"
    assert len(hex_part) == DEFAULT_HEX_LEN
    assert all(c in "0123456789abcdef" for c in hex_part)
    assert extended is False


def test_generate_identifier_idempotent_for_same_value():
    existing: dict[str, Entry] = {}
    ident_a, _ = generate_identifier("N", "Jane Smith", existing)
    # Idempotency check needs the entry to exist in the map.
    existing[ident_a] = Entry(identifier=ident_a, type="name", value="Jane Smith")
    ident_b, _ = generate_identifier("N", "Jane Smith", existing)
    assert ident_a == ident_b


def test_generate_identifier_idempotent_normalises_input():
    """Same value with different case / whitespace gets the same identifier."""
    existing: dict[str, Entry] = {}
    ident_a, _ = generate_identifier("N", "Jane Smith", existing)
    existing[ident_a] = Entry(identifier=ident_a, type="name", value="Jane Smith")
    ident_b, _ = generate_identifier("N", "  jane smith  ", existing)
    assert ident_a == ident_b


def test_generate_identifier_extends_on_collision():
    """Force a collision by pre-seeding the existing map."""
    # Compute the natural identifier for "Jane Smith".
    natural_ident, _ = generate_identifier("N", "Jane Smith", existing={})
    # Pretend that identifier is already taken by a *different*
    # value (idempotency check is by value, so a different value
    # at the same identifier triggers extension for the new one).
    pre_seeded = {
        natural_ident: Entry(
            identifier=natural_ident,
            type="name",
            value="some other reporter",
        ),
    }
    new_ident, extended = generate_identifier("N", "Jane Smith", pre_seeded)
    assert extended is True
    assert new_ident != natural_ident
    assert new_ident.startswith("N-")
    # Extended hex is longer than the default.
    _prefix, hex_part = new_ident.split("-", 1)
    assert len(hex_part) > DEFAULT_HEX_LEN


def test_generate_identifier_rejects_unknown_type():
    with pytest.raises(ValueError, match="unknown type code"):
        generate_identifier("Z", "anything", existing={})


# -- upsert ---------------------------------------------------------------


def test_upsert_creates_then_returns_existing():
    mapping: dict[str, Entry] = {}
    a = upsert(mapping, "N", "Jane Smith")
    b = upsert(mapping, "N", "Jane Smith")
    assert a is b or a == b
    assert len(mapping) == 1
    assert a.value == "Jane Smith"
    assert a.type == "name"


def test_upsert_distinguishes_types_for_same_value():
    """A reporter named ``foo`` and an email ``foo`` get distinct entries."""
    mapping: dict[str, Entry] = {}
    r = upsert(mapping, "N", "foo")
    e = upsert(mapping, "E", "foo")
    assert r.identifier != e.identifier
    assert r.identifier.startswith("N-")
    assert e.identifier.startswith("E-")


# -- file persistence ----------------------------------------------------


def test_save_and_load_round_trip(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    mapping: dict[str, Entry] = {}
    upsert(mapping, "N", "Jane Smith")
    upsert(mapping, "E", "jane@example.com")

    save_mapping_atomic(path, mapping)
    loaded = load_mapping(path)
    assert loaded == mapping


def test_load_round_trips_non_ascii_values(tmp_path: pathlib.Path):
    """Non-ASCII PII values must survive a save/load round-trip.

    Regression: ``load_mapping`` read the file with the locale-default
    encoding while ``save_mapping_atomic`` writes UTF-8, corrupting
    non-ASCII values (accented names, IDN domains) on non-UTF-8 hosts.
    """
    path = tmp_path / "pii.json"
    mapping: dict[str, Entry] = {}
    upsert(mapping, "N", "José Müller")
    upsert(mapping, "E", "renée@exámple.com")

    save_mapping_atomic(path, mapping)
    loaded = load_mapping(path)
    assert loaded == mapping


def test_save_creates_parent_dir(tmp_path: pathlib.Path):
    path = tmp_path / "deeper" / "nested" / "pii.json"
    mapping: dict[str, Entry] = {}
    upsert(mapping, "N", "Jane Smith")
    save_mapping_atomic(path, mapping)
    assert path.exists()


def test_save_writes_mode_0o600(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    mapping: dict[str, Entry] = {}
    upsert(mapping, "N", "Jane Smith")
    save_mapping_atomic(path, mapping)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_save_serialises_with_version_and_entries(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    mapping: dict[str, Entry] = {}
    upsert(mapping, "N", "Jane Smith")
    save_mapping_atomic(path, mapping)
    raw = json.loads(path.read_text())
    assert raw["version"] == MAPPING_VERSION
    assert "entries" in raw


def test_load_missing_file_returns_empty(tmp_path: pathlib.Path):
    assert load_mapping(tmp_path / "does-not-exist.json") == {}


def test_load_rejects_wrong_version(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    path.write_text(json.dumps({"version": 999, "entries": {}}))
    with pytest.raises(ValueError, match="version"):
        load_mapping(path)


def test_load_rejects_top_level_array(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    path.write_text(json.dumps([]))
    with pytest.raises(ValueError, match="JSON object"):
        load_mapping(path)


def test_load_rejects_malformed_entry(tmp_path: pathlib.Path):
    path = tmp_path / "pii.json"
    path.write_text(
        json.dumps(
            {
                "version": MAPPING_VERSION,
                "entries": {"N-abcdef": {"type": "name"}},  # missing value
            }
        )
    )
    with pytest.raises(ValueError, match="missing field 'value'"):
        load_mapping(path)


# -- locate_mapping_path -------------------------------------------------


def test_locate_explicit_wins(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("PII_MAPPING_PATH", "/should-not-be-used")
    explicit = str(tmp_path / "explicit.json")
    assert locate_mapping_path(explicit) == pathlib.Path(explicit)


def test_locate_env_used_when_no_explicit(tmp_path: pathlib.Path, monkeypatch):
    env_path = str(tmp_path / "from-env.json")
    monkeypatch.setenv("PII_MAPPING_PATH", env_path)
    assert locate_mapping_path(None) == pathlib.Path(env_path)


def test_locate_default_when_no_explicit_or_env(monkeypatch):
    monkeypatch.delenv("PII_MAPPING_PATH", raising=False)
    result = locate_mapping_path(None)
    assert result.parts[-2:] == ("apache-steward", "pii-mapping.json")
