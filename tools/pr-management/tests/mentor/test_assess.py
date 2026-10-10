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
"""The pre-draft decision: hand-off triggers, scope, maintainer engagement.

Mirrors the retired `hand-off` suite case by case, and the scripted gates of
the `intervention` suite (cases 4, 6, 8, 9); which template fits a thread stays
the agent's call and that suite keeps those cases.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pr_management.mentor import config, thread
from pr_management.people import Maintainers

VIEWER = "mentor-bot"
WHY = (
    "@{who} — that's covered here: [guide](https://x). The short version is in the first paragraph. If after "
    "reading you still think it shouldn't apply to this PR, drop a comment and a maintainer will weigh in."
)


def _thread(tmp_path: Path, messages: list[tuple[str, str, str]], state: str = "OPEN") -> thread.Thread:
    base = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)
    comments = [
        {
            "author": {"login": who},
            "authorAssociation": assoc,
            "body": body,
            "createdAt": (base + dt.timedelta(hours=i)).isoformat(),
        }
        for i, (who, assoc, body) in enumerate(messages)
    ]
    view = tmp_path / "view.json"
    view.write_text(
        json.dumps(
            {
                "title": "A thread",
                "author": {"login": messages[0][0]},
                "state": state,
                "body": "",
                "comments": comments,
            }
        )
    )
    return thread.load("issue", 1, view, None)


def _assess(
    tmp_path: Path, config_dir: Path, messages: list[tuple[str, str, str]], team: set[str] | None = None
) -> dict:
    cfg = config.load(tmp_path, config_dir)
    people = Maintainers(team=frozenset(team or set()))
    return thread.assess(_thread(tmp_path, messages), cfg, VIEWER, people)


def test_config_resolves(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    assert cfg.missing == [] and cfg.max_agent_turns == 2 and len(cfg.pointers) == 3


def test_a_missing_config_aborts(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    r = thread.assess(
        _thread(tmp_path, [("a", "NONE", "hi")]), config.load(tmp_path, empty), VIEWER, Maintainers()
    )
    assert r["outcome"] == "config_error" and "maintainer_team_handle" in r["missing"]


def test_handoff_case_1_no_trigger(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("alice", "CONTRIBUTOR", "How do I set up the dev environment?"),
            (VIEWER, "MEMBER", "@alice — Run `pip install -e .`."),
            ("alice", "CONTRIBUTOR", "Thanks, that worked! I'll push the fix now."),
        ],
    )
    assert r["outcome"] == "draft"


def test_handoff_case_2_max_turns(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("bob", "CONTRIBUTOR", "Why does CI run everything?"),
            (VIEWER, "MEMBER", "@bob — The full suite catches regressions."),
            ("bob", "CONTRIBUTOR", "OK. But why separate provider jobs?"),
            (VIEWER, "MEMBER", "@bob — So failures don't block unrelated providers."),
            ("bob", "CONTRIBUTOR", "I still don't understand — why not skip unaffected ones?"),
        ],
    )
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 1)


def test_handoff_case_3_contributor_pushback(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("carol", "CONTRIBUTOR", "Why do I need a newsfragment? My change is tiny."),
            (VIEWER, "MEMBER", WHY.format(who="carol")),
            ("carol", "CONTRIBUTOR", "I don't think that applies here — this is an internal refactor."),
        ],
    )
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 2)


def test_handoff_case_4_out_of_scope(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("dave", "CONTRIBUTOR", "I can't find the CHANGELOG format."),
            (VIEWER, "MEMBER", "@dave — Add a file under `newsfragments/`."),
            ("dave", "CONTRIBUTOR", "Also I found what might be a security vulnerability in the scheduler."),
        ],
    )
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 3)


def test_handoff_case_5_wants_human_takes_priority(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("eve", "CONTRIBUTOR", "Why Python 3.9 minimum?"),
            (VIEWER, "MEMBER", WHY.format(who="eve")),
            ("eve", "CONTRIBUTOR", "I don't think that policy makes sense for my use case."),
            (VIEWER, "MEMBER", "@eve — The minimum is project-wide."),
            ("eve", "CONTRIBUTOR", "Can a real person from the team please look at this?"),
        ],
    )
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 4)


def test_intervention_case_6_maintainer_engaged(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("leon-f", "CONTRIBUTOR", "Fixes the crash when the dag bag is empty."),
            ("committer-a", "MEMBER", "The fix looks right. Can you also add a test?"),
            ("leon-f", "CONTRIBUTOR", "Sure, I'll add a unit test. Give me a day."),
        ],
        team={"committer-a"},
    )
    assert r["outcome"] == "maintainer_engaged" and r["maintainers"] == ["committer-a"]


def test_intervention_case_8_out_of_scope_before_any_draft(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(tmp_path, config_dir, [("zed", "NONE", "This input allows RCE through the template loader.")])
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 3)


def test_intervention_case_9_deprecation_decision(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(
        tmp_path,
        config_dir,
        [
            ("yan", "NONE", "The warning spams my logs."),
            (
                "yan",
                "NONE",
                "Could the maintainers decide whether to remove the deprecated parameter in 3.0?",
            ),
        ],
    )
    assert (r["outcome"], r["handoff"]["trigger"]) == ("handoff", 3)


def test_rce_does_not_match_inside_a_word(tmp_path: Path, config_dir: Path) -> None:
    r = _assess(tmp_path, config_dir, [("zed", "NONE", "The source file is missing a header.")])
    assert r["outcome"] == "draft"


def test_a_resolved_thread_does_not_hand_off_on_turns(tmp_path: Path, config_dir: Path) -> None:
    cfg = config.load(tmp_path, config_dir)
    t = _thread(
        tmp_path, [("a", "NONE", "x"), (VIEWER, "MEMBER", "y"), (VIEWER, "MEMBER", "z")], state="CLOSED"
    )
    assert thread.assess(t, cfg, VIEWER, Maintainers(team=frozenset()))["outcome"] == "draft"
