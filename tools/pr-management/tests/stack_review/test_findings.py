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
"""Step 3 — detector output to findings, and the verdict.

`test_case_*` mirror the mechanical cases of the model-graded
`step-3-structural-findings` suite; the judgement cases stay there.
"""

from __future__ import annotations

import shlex
from typing import Any

from pr_management.stack_review import findings as F
from pr_management.stack_review.cli import residue_command


def chain(
    *,
    contains: dict[int, bool] | None = None,
    merges: dict[int, int] | None = None,
    touched: list[str] | None = None,
    empty: tuple[int, ...] = (),
    size: int = 4,
) -> dict[str, Any]:
    return {
        "behind_trunk_commits": 3,
        "trunk_touches_stack_files": touched or [],
        "layers": [
            {
                "position": k,
                "contains_below": (contains or {}).get(k, True),
                "own_commits": 0 if k in empty else 1,
                "merge_commits": (merges or {}).get(k, 0),
            }
            for k in range(1, size + 1)
        ],
    }


def seams(hits: dict[int, dict[str, Any]] | None = None, size: int = 4) -> dict[str, Any]:
    return {
        "layers": [
            {"position": k, "removed_definitions": 1, "hits": (hits or {}).get(k, {})}
            for k in range(1, size + 1)
        ]
    }


def ledger(**detectors: list[dict[str, Any]]) -> dict[str, Any]:
    base: dict[str, list[dict[str, Any]]] = {
        "release_note_in_several_layers": [],
        "generated_in_several_layers": [],
        "lock_without_manifest": [],
    }
    base.update(detectors)
    return {"overlap": {}, "detectors": base, "layers": []}


def classes(result: dict[str, Any]) -> list[tuple[str, str, list[int]]]:
    return [(f["class"], f["severity"], f["layers"]) for f in result["findings"]]


def test_case_1_stale_base() -> None:
    out = F.collect(chain(contains={3: False}), seams(), None, ledger())
    assert classes(out) == [("chain", "blocking", [3])]
    assert F.verdict(out["findings"])["verdict"] == "not-mergeable"


def test_case_2_removed_definition_used_at_own_head() -> None:
    hit = {
        "load": {
            "removed_in": "src/a.py",
            "at_own_head": ["src/b.py:3:load()"],
            "at_later_heads": {},
            "new_on_trunk": [],
        }
    }
    out = F.collect(chain(), seams({3: hit}), None, ledger())
    assert classes(out) == [("ordering", "blocking", [3])]
    assert "verify" in out["findings"][0]


def test_case_3_later_head_hit_is_a_candidate_for_judgement() -> None:
    hit = {
        "load": {
            "removed_in": "src/a.py",
            "at_own_head": [],
            "at_later_heads": {"4": ["x.py:1:load()"]},
            "new_on_trunk": [],
        }
    }
    out = F.collect(chain(), seams({3: hit}), None, ledger())
    assert out["findings"] == []
    assert out["candidates"][0]["layers"] == [3, 4] and out["candidates"][0]["if_confirmed"] == "blocking"


def test_case_4_new_use_on_trunk() -> None:
    hit = {
        "load": {
            "removed_in": "src/a.py",
            "at_own_head": [],
            "at_later_heads": {},
            "new_on_trunk": ["n.py:9:load()"],
        }
    }
    out = F.collect(chain(), seams({3: hit}), None, ledger())
    assert classes(out) == [("trunk-drift", "major", [3])]
    assert F.verdict(out["findings"])["verdict"] == "needs-attention"


def test_case_5_duplicate_release_note_and_lock() -> None:
    out = F.collect(
        chain(),
        seams(),
        None,
        ledger(
            release_note_in_several_layers=[{"path": "newsfragments/1.misc", "layers": [1, 4]}],
            generated_in_several_layers=[{"path": "uv.lock", "layers": [2, 4]}],
        ),
    )
    assert classes(out) == [("duplicate", "major", [1, 4]), ("duplicate", "major", [2, 4])]


def test_case_6_clean_stack_behind_trunk_with_red_ci_is_coherent() -> None:
    out = F.collect(chain(), seams(), None, ledger())
    assert out["findings"] == [] and out["informational"] == [{"kind": "behind-trunk", "commits": 3}]
    assert F.verdict(out["findings"])["verdict"] == "coherent"


def test_case_12_node_lock_without_manifest() -> None:
    out = F.collect(
        chain(),
        seams(),
        None,
        ledger(lock_without_manifest=[{"path": "package-lock.json", "layer": 2, "manifest_layers": [1]}]),
    )
    assert classes(out) == [("duplicate", "major", [1, 2])]


def test_case_13_node_rename_clean() -> None:
    assert F.verdict(F.collect(chain(), seams(), None, ledger())["findings"])["verdict"] == "coherent"


def test_chain_mapping_covers_merge_commits_empty_layers_and_trunk_touches() -> None:
    out = F.collect(chain(merges={2: 1}, empty=(4,), touched=["src/x.py"]), seams(), None, ledger())
    assert classes(out) == [
        ("chain", "blocking", [2]),
        ("trunk-drift", "major", [1]),
        ("narrative", "minor", [4]),
    ]


def test_a_floor_move_is_a_candidate_naming_the_layer() -> None:
    floors = {
        "floor_changes": [{"position": 7, "moved": {"pyproject.toml": {"from": ">=3.10", "to": ">=3.11"}}}]
    }
    candidate = F.collect(chain(), seams(), floors, ledger())["candidates"][0]
    assert candidate["class"] == "ordering" and candidate["layers_below"] == 7


def test_overlap_and_off_theme_files_are_wrong_layer_candidates() -> None:
    led = ledger()
    led["overlap"] = {"src/cli.py": [3, 4]}
    led["layers"] = [{"position": 2, "dir_outliers": ["docs/x.md"]}]
    candidates = F.collect(chain(), seams(), None, led)["candidates"]
    assert [(c["class"], c["layers"]) for c in candidates] == [("wrong-layer", [3, 4]), ("wrong-layer", [2])]


def test_case_10_verdict_merge_unit_when_every_major_is_an_ordering_unit() -> None:
    out = F.verdict([{"class": "ordering", "severity": "major", "layers": [4, 5, 6, 7]}])
    assert (out["verdict"], out["merge_unit"]) == ("merge-unit", "4\u20137")
    assert out["label"] == "mergeable bottom-up; merge layers 4\u20137 together"


def test_verdict_with_a_minor_only_is_coherent_and_gates_never_count() -> None:
    assert (
        F.verdict([{"class": "wrong-layer", "severity": "minor", "layers": [3, 4]}])["verdict"] == "coherent"
    )
    assert F.verdict([{"class": "gates", "severity": "gate", "layers": [2]}])["verdict"] == "coherent"


def test_findings_sort_blocking_first_then_bottom_layer() -> None:
    ordered = F.sort_findings(
        [
            {"class": "duplicate", "severity": "major", "layers": [1]},
            {"class": "chain", "severity": "blocking", "layers": [3]},
            {"class": "ordering", "severity": "blocking", "layers": [2]},
        ]
    )
    assert [(f["severity"], f["layers"][0]) for f in ordered] == [
        ("blocking", 2),
        ("blocking", 3),
        ("major", 1),
    ]


def test_a_demoted_layer_puts_the_coverage_clause_on_the_verdict_line() -> None:
    led = {
        "layers": [
            {
                "position": 1,
                "plan": "full",
                "planned_hunks": 10,
                "hunks": 10,
                "planned_lines": 100,
                "changed_lines": 100,
            },
            {
                "position": 2,
                "plan": "exemplar",
                "planned_hunks": 5,
                "hunks": 40,
                "planned_lines": 50,
                "changed_lines": 900,
            },
        ]
    }
    out = F.verdict([], ledger=led)
    assert (
        out["line"]
        == "coherent (structure checked in full; code read 15 of 50 hand-written hunks, 150 of 1,000 lines)"
    )
    assert out["demoted_layers"] == [2]


def test_residue_command_is_one_quoted_git_grep() -> None:
    argv = shlex.split(
        residue_command("/c", "magpie-stack/120", 4, ["Python 3\\.10", "py310"], ["**/vendor/**"])
    )
    assert argv[:9] == ["git", "-C", "/c", "grep", "-n", "-I", "-i", "-E", "(?:Python 3\\.10)|(?:py310)"]
    assert argv[9:12] == ["refs/magpie-stack/120/4", "--", "."]
    assert argv[-1] == ":(glob,exclude)**/vendor/**"
