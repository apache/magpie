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
"""Loading the saved sweep: pagination dedup and session suppression.

Mirrors the retired model-graded `pagination-dedup` suite.
"""

from __future__ import annotations

import json
from pathlib import Path

from pr_management import config, model, people
from pr_management.triage import classify as C

from .helpers import NOW, page, pr


def _save(tmp_path: Path, pages: list[list[dict]]) -> Path:
    path = tmp_path / "triage-pages.json"
    path.write_text(json.dumps([p[0] for p in pages]))
    return path


def test_a_pr_that_moves_to_a_later_page_is_kept_once_at_its_freshest(tmp_path: Path) -> None:
    stale = pr(7, title="old title")
    fresh = pr(7, title="new title")
    prs, count = model.load_pages([_save(tmp_path, [page(stale, pr(8)), page(pr(9), fresh)])])
    assert count == 2
    assert sorted(p.number for p in prs) == [7, 8, 9]
    assert next(p for p in prs if p.number == 7).title == "new title"


def test_a_single_pr_read_loads_too(tmp_path: Path) -> None:
    path = tmp_path / "one.json"
    path.write_text(json.dumps({"data": {"repository": {"pullRequest": pr(5)}}}))
    prs, _ = model.load_pages([path])
    assert [p.number for p in prs] == [5]


def _classify(session: dict) -> C.Decision:
    (decision,) = C.classify(
        [model.from_node(pr(1))],
        config.Config(real_ci_patterns=["Tests"]),
        C.Options(viewer="triager", now=NOW, session=session),
        people.Maintainers(),
        {},
        set(),
    )
    return decision


def test_a_pr_acted_on_this_session_is_suppressed_while_its_head_is_unchanged() -> None:
    assert _classify({"1": {"head_sha": "abc1234def5678", "terminal": True}}).outcome == "suppressed"


def test_a_pr_whose_head_moved_is_classified_again() -> None:
    assert _classify({"1": {"head_sha": "0000000", "terminal": True}}).outcome == "act"


def test_a_cache_entry_without_a_terminal_action_never_suppresses() -> None:
    assert _classify({"1": {"head_sha": "abc1234def5678", "terminal": False}}).outcome == "act"
