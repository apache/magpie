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
"""reviewer-routing: pre-flight, roster, scoring, proposal.

Mirrors the retired model-graded suites case by case: `step-0-preflight`
cases 1-3 and `step-score-and-propose` cases 1-3. Case 4 (the injection
screen) stays a model case; its scoring half is tested here too.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from pr_management.reviewer_routing import cli, codeowners, roster, score

ROSTER = """# Reviewer roster

## Roster

<!--
  - handle: example-only
    areas: [ignored]
-->

- handle: {a}
  areas:
    - {a_areas}
  max_reviews: 5
- handle: {b}
  areas: [{b_areas}]
  max_reviews: 5
"""


def _cfg(tmp_path: Path, members: list[tuple[str, list[str], int]] | None) -> Path:
    d = tmp_path / "cfg"
    d.mkdir(exist_ok=True)
    (d / "project.md").write_text(
        "| Key | Value |\n|---|---|\n| `upstream_repo` | `apache/example` |\n"
        "| `upstream_default_branch` | `main` |\n"
    )
    if members is not None:
        lines = ["## Roster", ""]
        for handle, areas, limit in members:
            lines += [
                f"- handle: {handle}",
                "  areas:",
                *[f"    - {a}" for a in areas],
                f"  max_reviews: {limit}",
            ]
        (d / "reviewer-roster.md").write_text("\n".join(lines) + "\n")
    return d


def _args(tmp_path: Path, cfg: Path, **kw: object) -> argparse.Namespace:
    base: dict[str, object] = {"project_root": tmp_path, "config_dir": cfg, "repo": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_preflight_case_1_all_clear(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, [("a", ["x"], 5)])
    r = cli.preflight(_args(tmp_path, cfg, target="pr:42", privacy_exit=0, privacy_message=""))
    assert r == {
        "verdict": "proceed",
        "blockers": [],
        "privacy_gate_passed": True,
        "roster_source": "reviewer-roster",
        "item_type": "pr",
        "item_number": 42,
        "upstream_repo": "apache/example",
    }


def test_preflight_case_2_privacy_gate_blocked(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, [("a", ["x"], 5)])
    r = cli.preflight(
        _args(
            tmp_path,
            cfg,
            target="issue:17",
            privacy_exit=1,
            privacy_message="unapproved LLM endpoint 'https://api.thirdparty-vendor.io/v1'",
        )
    )
    assert r["verdict"] == "blocked" and not r["privacy_gate_passed"]
    assert (r["item_type"], r["item_number"], r["roster_source"]) == ("issue", 17, "reviewer-roster")
    assert "thirdparty-vendor" in r["blockers"][0]


def test_preflight_case_3_missing_roster(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, None)
    r = cli.preflight(_args(tmp_path, cfg, target="99", privacy_exit=0, privacy_message=""))
    assert r["verdict"] == "blocked" and r["roster_source"] is None and r["privacy_gate_passed"]
    assert r["blockers"] == [cli.NO_ROSTER_BLOCKER] and (r["item_type"], r["item_number"]) == ("pr", 99)


@pytest.mark.parametrize("bad", ["pr:abc", "issue 3", "1; rm -rf /", "pr:"])
def test_preflight_refuses_an_unvalidated_target(tmp_path: Path, bad: str) -> None:
    cfg = _cfg(tmp_path, [("a", ["x"], 5)])
    assert (
        cli.preflight(_args(tmp_path, cfg, target=bad, privacy_exit=0, privacy_message=""))["verdict"]
        == "blocked"
    )


def _run(
    members: list[roster.Member],
    item: score.Item,
    fam: dict[str, set[str]],
    load: dict[str, int],
    owners: dict[str, set[str]] | None = None,
) -> dict:
    return score.score(
        roster.Roster("reviewer-roster", members, {}),
        item,
        familiarity=fam,
        owners=owners or {},
        load=load,
        inferred_areas=[],
    )


def test_score_case_1_happy_path() -> None:
    members = [
        roster.Member("maintainer-bob", ["component:scheduler", "component:triggerer"]),
        roster.Member("maintainer-carol", ["component:dag-parsing", "component:api"]),
        roster.Member("maintainer-dan", ["component:scheduler"]),
    ]
    item = score.Item(
        "pr",
        42,
        "fix(scheduler)",
        ["component:scheduler", "kind:bug"],
        ["example/jobs/heartbeat.py", "example/jobs/scheduler.py"],
    )
    fam = {
        "maintainer-bob": {"example/jobs/scheduler.py", "example/jobs/heartbeat.py"},
        "maintainer-dan": {"example/jobs/scheduler.py"},
    }
    r = _run(members, item, fam, {"maintainer-bob": 2, "maintainer-carol": 1, "maintainer-dan": 3})
    assert r["primary"]["handle"] == "maintainer-bob" and r["backup"]["handle"] == "maintainer-dan"
    assert r["primary"]["score"] == 7 and r["backup"]["score"] == 4
    assert not next(c for c in r["candidates"] if c["handle"] == "maintainer-carol")["eligible"]


def test_score_case_2_empty_roster() -> None:
    r = _run([], score.Item("pr", 77, "feat(api)", ["component:api"], ["example/api/health.py"]), {}, {})
    assert r["no_eligible_reviewer"] and r["message"] == score.NO_ROSTER


def test_score_case_3_load_balancing() -> None:
    members = [
        roster.Member("maintainer-grace", ["component:dag-parsing"]),
        roster.Member("maintainer-henry", ["component:dag-parsing"]),
    ]
    item = score.Item(
        "pr",
        101,
        "fix(dag-parsing)",
        ["component:dag-parsing"],
        ["example/dag_processing/manager.py", "example/dag_processing/processor.py"],
    )
    fam = {"maintainer-grace": set(item.paths), "maintainer-henry": {item.paths[0]}}
    r = _run(members, item, fam, {"maintainer-grace": 5, "maintainer-henry": 1})
    assert r["primary"]["handle"] == "maintainer-henry"
    assert r["backup"]["handle"] == "maintainer-grace" and r["backup"]["overloaded"]


def test_score_case_4_scoring_half_of_the_injection_case() -> None:
    members = [
        roster.Member("maintainer-ida", ["component:docs"]),
        roster.Member("maintainer-jose", ["component:docs", "component:ci"]),
    ]
    item = score.Item("pr", 200, "docs: update contributing guide", ["component:docs"], ["CONTRIBUTING.md"])
    fam = {"maintainer-ida": {"CONTRIBUTING.md"}, "maintainer-jose": {"CONTRIBUTING.md"}}
    r = _run(members, item, fam, {"maintainer-ida": 0, "maintainer-jose": 2})
    assert (r["primary"]["handle"], r["backup"]["handle"]) == ("maintainer-ida", "maintainer-jose")
    text = score.render(r, item, "apache/example", "SYSTEM override asking to assign admin-override")
    assert text.startswith("⚠ Injection attempt detected") and "admin-override" not in text


def test_all_overloaded_is_no_eligible_reviewer() -> None:
    members = [roster.Member("a", ["x"], 1), roster.Member("b", ["x"], 1)]
    r = _run(members, score.Item("pr", 1, "t", ["x"], []), {}, {"a": 1, "b": 3})
    assert r["no_eligible_reviewer"] and r["message"] == score.ALL_OVERLOADED


def test_no_area_match_makes_everyone_eligible() -> None:
    members = [roster.Member("b", ["y"]), roster.Member("a", ["z"])]
    r = _run(members, score.Item("issue", 3, "t", ["unrelated"], []), {}, {})
    assert r["primary"]["handle"] == "a" and r["backup"]["handle"] == "b"  # alphabetical tiebreak


def test_path_prefix_areas_and_codeowners_count() -> None:
    members = [roster.Member("a", ["src/core/"]), roster.Member("b", ["src/core/"])]
    item = score.Item("pr", 4, "t", [], ["src/core/x.py"])
    r = _run(members, item, {}, {}, owners={"b": {"src/core/x.py"}})
    assert r["primary"]["handle"] == "b" and r["primary"]["codeowner_paths"] == 1


def test_the_next_step_is_quoted() -> None:
    cmd = score.next_step(score.Item("pr", 7, "t", [], []), "apache/example", "bob")
    assert cmd == "gh pr edit 7 --repo apache/example --add-reviewer bob"


def test_roster_parsing_skips_comments_and_todo() -> None:
    text = ROSTER.format(a="alice", a_areas="src/a/", b="TODO-maintainer-2", b_areas="b")
    assert [(m.handle, m.areas) for m in roster.parse_reviewer_roster(text)] == [("alice", ["src/a/"])]


def test_release_trains_rotations_are_read() -> None:
    text = "## Known release-manager rotations\n\n- providers — @ana, @ben\n- `core`: @cy\n"
    found = {m.handle: m.areas for m in roster.parse_release_trains(text)}
    assert found == {"ana": ["providers"], "ben": ["providers"], "cy": ["core"]}


def test_codeowners_last_match_wins() -> None:
    rules = codeowners.parse("* @all\n/docs/ @docs-team\n*.py @py\n")
    assert codeowners.owners_of("docs/a.py", rules) == ["py"]
    assert codeowners.owners_of("docs/a.md", rules) == ["docs-team"]
    assert codeowners.owners_of("x/y.txt", rules) == ["all"]


def test_propose_asks_for_reads_then_scores(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path, [("bob", ["component:scheduler"], 5)])
    saved = tmp_path / "saved"
    saved.mkdir()
    args = _args(tmp_path, cfg, target="pr:42", saved_dir=saved, area=[], no_codeowners=False, injection=None)
    assert cli.propose(args)["needs"][0] == {
        "op": "pr-view-with-body",
        "params": ["42"],
        "save": "routing-pr-42.json",
    }
    (saved / "routing-pr-42.json").write_text(
        json.dumps(
            {"title": "fix", "labels": [{"name": "component:scheduler"}], "files": [{"path": "a/b.py"}]}
        )
    )
    ops = {n["op"] for n in cli.propose(args)["needs"]}
    assert ops == {"commits-by-path", "pr-search-review-requested", "repo-file"}
    (saved / "routing-commits-0.txt").write_text("bob\nbob\nzed\n")
    (saved / "routing-load-bob.json").write_text("[]")
    args.no_codeowners = True
    r = cli.propose(args)
    assert r["primary"]["handle"] == "bob" and r["classification"] == "primary-only"
    assert r["next_step"] == "gh pr edit 42 --repo apache/example --add-reviewer bob"
