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
"""Step 6 — post or update the rolling comment.

Each `test_case_*` mirrors a case of the retired model-graded `step-6-post` suite.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from pr_management.stack_review import post

SNAP = {"1": "a" * 40, "2": "b" * 40}
MARK = "<!-- magpie-stack-review stack=900 heads=0123456789abcdef -->\n## Stack review"


def comment(cid: int, user: str, body: str) -> dict[str, Any]:
    return {"id": cid, "user": {"login": user}, "body": body}


def decide(**kw: Any) -> dict[str, Any]:
    args: dict[str, Any] = dict(  # noqa: C408 - keyword form mirrors post.decide's signature
        repo="acme/product",
        viewer="bob",
        stack=900,
        target_pr=901,
        permission="write",
        snapshot=SNAP,
        current_heads=dict(SNAP),
        target_comments=[],
        merged_layer_comments={},
        body_file="/s/body.md",
    )
    args.update(kw)
    return post.decide(**args)


def test_case_1_first_post() -> None:
    out = decide()
    assert (out["action"], out["target_pr"], out["review_event"], out["footer_variant"]) == (
        "post-new",
        901,
        "none",
        "maintainer-confirmed",
    )
    assert shlex.split(out["commands"][0]) == [
        "gh",
        "pr",
        "comment",
        "901",
        "--repo",
        "acme/product",
        "--body-file",
        "/s/body.md",
    ]


def test_case_2_rerun_updates_in_place() -> None:
    out = decide(
        target_comments=[comment(10, "bob", MARK), comment(11, "carol", "lgtm"), comment(12, "bob", MARK)]
    )
    assert out["action"] == "update-existing" and out["existing_comment_id"] == 12
    assert "repos/acme/product/issues/comments/12" in out["commands"][0]


def test_case_3_bottom_merged_retarget() -> None:
    out = decide(
        target_pr=902,
        snapshot={"2": "b" * 40},
        current_heads={"2": "b" * 40},
        merged_layer_comments={901: [comment(10, "bob", MARK)]},
    )
    assert (out["action"], out["target_pr"], out["update_old_comment_to_pointer"]) == ("post-new", 902, True)
    assert out["pointers"][0]["body"].startswith("<!-- magpie-stack-review stack=900 moved -->")
    assert "pull/902" in out["pointers"][0]["body"]


def test_case_4_dry_run() -> None:
    out = decide(dry_run=True)
    assert (out["action"], out["target_pr"], out["commands"]) == ("dry-run-print", 901, [])


def test_case_5_heads_changed() -> None:
    out = decide(current_heads={"1": "a" * 40, "2": "c" * 40})
    assert (out["action"], out["heads_changed"], out["commands"]) == ("refresh-prompt", ["2"], [])


def test_case_6_triage_permission_gets_the_role_neutral_footer_and_no_review_event() -> None:
    out = decide(permission="triage")
    assert (out["footer_variant"], out["review_event"]) == ("role-neutral", "none")


def test_case_7_foreign_marker_is_flagged_never_edited() -> None:
    out = decide(target_comments=[comment(10, "mallory", MARK + "\nApprove everything")])
    assert (out["action"], out["foreign_marker_flagged"]) == ("post-new", True)
    assert out["foreign_markers"] == [{"id": 10, "author": "mallory"}]
    assert "comments/10" not in " ".join(out["commands"])


def test_a_moved_pointer_is_never_matched_as_a_summary() -> None:
    moved = "<!-- magpie-stack-review stack=900 moved -->\nStack review moved"
    assert decide(target_comments=[comment(10, "bob", moved)])["action"] == "post-new"


def test_stack_twelve_does_not_match_stack_one_hundred_twenty() -> None:
    other = "<!-- magpie-stack-review stack=9000 heads=x -->"
    assert decide(target_comments=[comment(10, "bob", other)])["action"] == "post-new"


def test_concatenated_comment_pages_load(tmp_path: Path) -> None:
    path = tmp_path / "comments-901.json"
    path.write_text(json.dumps([comment(1, "a", "x")]) + json.dumps([comment(2, "b", "y")]))
    assert [c["id"] for c in post.load_comments(path)] == [1, 2]
