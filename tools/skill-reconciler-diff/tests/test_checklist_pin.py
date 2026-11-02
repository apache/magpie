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

"""Pin the clause regexes to the safety-baseline checklist they implement.

``_CLAUSE1_RE`` .. ``_CLAUSE3_RE`` are hand-written, and the checklist the
skill-reconciler classifies against is prose; nothing tied the two together,
so either could drift. These tests read the checklist itself:

- every **canonical wording** blockquote of a clause must trip that clause's
  regex, so a rewording of the checklist that the helper no longer recognises
  fails here rather than as a silent miss in a reconciliation;
- every **softened** phrasing the checklist quotes as a failure must *not*
  trip it, and the strong phrasing it is contrasted with must, so the helper
  does not credit the softened phrasing on its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from skill_reconciler_diff import _CLAUSE1_RE, _CLAUSE2_RE, _CLAUSE3_RE

CHECKLIST = (
    Path(__file__).resolve().parents[3]
    / "plugins"
    / "magpie-utilities"
    / "skills"
    / "skill-reconciler"
    / "safety-baseline-checklist.md"
)
REGEXES = {1: _CLAUSE1_RE, 2: _CLAUSE2_RE, 3: _CLAUSE3_RE}


def _clauses() -> dict[int, str]:
    # Fail, never skip: a moved checklist would otherwise turn the pin into a no-op.
    assert CHECKLIST.is_file(), f"{CHECKLIST} missing: update the path if the checklist moved"
    text = CHECKLIST.read_text(encoding="utf-8")
    parts = re.split(r"^## Clause (\d+) .*$", text, flags=re.MULTILINE)
    return {int(number): body for number, body in zip(parts[1::2], parts[2::2], strict=True)}


def _canonical(body: str) -> list[str]:
    """The blockquotes under the clause's **Canonical wording** heading."""
    section = body.split("**Canonical wording", 1)[1].split("**Reference", 1)[0]
    quotes: list[str] = []
    current: list[str] = []
    for line in [*section.splitlines(), ""]:
        if line.startswith(">"):
            current.append(line.lstrip("> ").strip())
        elif current:
            quotes.append(" ".join(current))
            current = []
    return quotes


def _softenings(body: str) -> list[tuple[str, str | None]]:
    """``(softened, strong)`` from each failure bullet that describes a softening."""
    failures = body.split("**What constitutes a failure:**", 1)[1].split("**Canonical wording", 1)[0]
    bullets = re.split(r"^- ", failures, flags=re.MULTILINE)[1:]
    pairs: list[tuple[str, str | None]] = []
    for bullet in bullets:
        flat = " ".join(bullet.split())
        if "soften" not in flat:
            continue
        quotes = re.findall(r'"([^"]+)"', flat)
        if not quotes:
            continue
        strong = re.search(r'instead of "([^"]+)"', flat)
        pairs.append((quotes[0], strong.group(1) if strong else None))
    return pairs


def test_the_checklist_has_the_three_clauses_the_helper_detects() -> None:
    assert sorted(_clauses()) == sorted(REGEXES)


@pytest.mark.parametrize("clause", sorted(REGEXES))
def test_every_canonical_wording_trips_its_clause(clause: int) -> None:
    quotes = _canonical(_clauses()[clause])
    assert quotes, f"clause {clause} has no canonical wording to pin against"
    for quote in quotes:
        assert REGEXES[clause].search(quote), f"_CLAUSE{clause}_RE misses the checklist's wording: {quote!r}"


@pytest.mark.parametrize("clause", sorted(REGEXES))
def test_a_softened_phrasing_never_counts_as_the_clause(clause: int) -> None:
    pairs = _softenings(_clauses()[clause])
    assert pairs, f"clause {clause} quotes no softened phrasing to pin against"
    for softened, strong in pairs:
        assert not REGEXES[clause].search(softened), (
            f"_CLAUSE{clause}_RE credits a softened phrasing the checklist calls a failure: {softened!r}"
        )
        if strong is not None:
            assert REGEXES[clause].search(strong), f"_CLAUSE{clause}_RE misses the strong form: {strong!r}"
