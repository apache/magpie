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

"""The per-item failure budget (docs/batch-failure-budget.md) in pr-stale-sweep."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pr_management import config, failure_budget, model, people
from pr_management.stale_sweep import classify as C

from ..helpers import NOW
from .test_stale_sweep import node, plan

# --- the budget itself --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "pool", "expected"),
    [
        (None, 10, 3),  # default max(3, 10%)
        (None, 100, 10),
        ("max(3, 10%)", 45, 4),
        ("5", 1000, 5),
        ("0", 10, 0),
        ("20%", 9, 1),  # rounded down
        ("  MAX( 2 , 50% ) ", 3, 2),
    ],
)
def test_limit(spec: str | None, pool: int, expected: int) -> None:
    assert failure_budget.limit(spec, pool) == expected


@pytest.mark.parametrize("spec", ["three", "-1", "10 %", "max(3)", "150%", "min(3, 10%)"])
def test_a_malformed_spec_is_an_error_not_a_silent_default(spec: str) -> None:
    with pytest.raises(failure_budget.BudgetSpecError):
        failure_budget.limit(spec, 10)


def test_exhausted_only_past_the_limit() -> None:
    b = failure_budget.Budget(limit=1)
    b.record(1, "x")
    assert not b.exhausted
    b.record(2, "y")
    assert b.exhausted


def test_rerun_selector() -> None:
    assert failure_budget.rerun_selector([7, 3, 7]) == "3,7"
    assert failure_budget.rerun_selector([]) is None


# --- in the sweep -------------------------------------------------------------------------


def _sweep(loaded: list[Any], *, spec: str | None = None, load_failures: list[dict[str, Any]] | None = None):
    return C.sweep(
        loaded,
        plan(),
        config.Config(upstream_repo="apache/myproject", item_failure_budget=spec),
        people.Maintainers(),
        NOW,
        load_failures=load_failures,
    )


def _loaded(*numbers: int) -> list[Any]:
    out = []
    for n in numbers:
        nd = node(n, idle=60)
        out.append((model.from_node(nd), C.raw_comments(nd)))
    return out


def test_a_clean_sweep_reports_an_unused_budget() -> None:
    result = _sweep(_loaded(1, 2))
    assert result["failed"] == [] and result["unfinished"] == [] and result["stopped"] is None
    assert result["budget"] == {"limit": 3, "used": 0, "exhausted": False}
    assert result["rerun_selector"] is None
    assert len(result["proposals"]) == 2


def test_one_item_that_cannot_be_classified_is_recorded_and_the_sweep_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = C.classify_one

    def flaky(pr, *args, **kwargs):  # one PR's data breaks classification
        if pr.number == 2:
            raise KeyError("labels")
        return real(pr, *args, **kwargs)

    monkeypatch.setattr(C, "classify_one", flaky)
    result = _sweep(_loaded(1, 2, 3))
    assert [p["number"] for p in result["proposals"]] == [1, 3]
    assert result["failed"] == [{"number": 2, "reason": "could not classify: KeyError: 'labels'"}]
    assert result["stopped"] is None and result["unfinished"] == []
    assert result["rerun_selector"] == "2"


def test_exceeding_the_budget_stops_before_the_next_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(C, "classify_one", lambda *a, **k: (_ for _ in ()).throw(ValueError("bad node")))
    result = _sweep(_loaded(1, 2, 3, 4, 5), spec="1")
    assert [f["number"] for f in result["failed"]] == [1, 2]  # the second failure exceeds a budget of 1
    assert result["unfinished"] == [3, 4, 5]
    assert result["stopped"] == "item-failure-budget"
    assert result["budget"] == {"limit": 1, "used": 2, "exhausted": True}
    assert result["rerun_selector"] == "1,2,3,4,5"  # exactly the failed and unfinished items


def test_unreadable_nodes_count_against_the_budget(tmp_path: Path) -> None:
    good = node(1, idle=60)
    page = {"data": {"search": {"nodes": [good, {"number": 2, "labels": "not-a-connection"}]}}}
    path = tmp_path / "pages.json"
    path.write_text(json.dumps(page))
    loaded, failures = C.load_with_failures([path])
    assert [pr.number for pr, _raw in loaded] == [1]
    assert [f["number"] for f in failures] == [2] and "could not read the PR" in failures[0]["reason"]
    result = _sweep(loaded, load_failures=failures)
    assert [f["number"] for f in result["failed"]] == [2]
    assert [p["number"] for p in result["proposals"]] == [1]


def test_a_later_good_read_of_the_same_pr_replaces_its_failure(tmp_path: Path) -> None:
    bad = tmp_path / "a.json"
    bad.write_text(json.dumps({"data": {"search": {"nodes": [{"number": 7, "labels": "not-a-connection"}]}}}))
    good = tmp_path / "b.json"
    good.write_text(json.dumps({"data": {"search": {"nodes": [node(7, idle=60)]}}}))
    loaded, failures = C.load_with_failures([bad, good])
    assert [pr.number for pr, _raw in loaded] == [7] and failures == []


def test_a_malformed_budget_is_an_error(tmp_path: Path) -> None:
    result = _sweep(_loaded(1), spec="lots")
    assert "item_failure_budget" in result["error"]


def test_the_config_key_is_read(tmp_path: Path) -> None:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "pr-management-config.md").write_text("| `item_failure_budget` | max(2, 5%) |\n")
    cfg = config.load(tmp_path, cfg_dir)
    assert cfg.item_failure_budget == "max(2, 5%)"
