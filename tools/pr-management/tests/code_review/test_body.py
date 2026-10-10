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
"""Composing what gets posted. Mirrors the retired `step-8-mention-scan` and
`step-7b-review-body-attribution` suites case by case.
"""

from __future__ import annotations

import json

import pytest

from pr_management.code_review import body, diff

URL = "https://github.com/apache/airflow/blob/main/contributing-docs/05_pull_requests.rst"

# --- step-8 mention scan --------------------------------------------------------------------------


def test_mention_case_1_clean_escaped_body() -> None:
    text = (
        "Approach looks reasonable.\n\n### Worth a second look from\n\n- `@alice-maint` — owner\n"
        "- `@bob-active` — authored 6 of the last 20 commits\n"
    )
    assert body.mention_scan(text) == []


def test_mention_case_2_stray_live_mention() -> None:
    text = "- There are 2 unresolved review threads on this PR from @ashb — please\n  address those first.\n"
    assert [h["handle"] for h in body.mention_scan(text)] == ["ashb"]


def test_mention_case_3_code_spans_fences_cron_and_decorators() -> None:
    text = (
        "```text\nAs discussed with @ashb and @potiuk on the private thread.\n```\n\n"
        "Also note `sched@daily` in the DAG definition, and @daily alone, is a cron alias.\n"
        "@pytest.fixture(autouse=True)\n1. `tests/test_heartbeat.py:12` — `@pytest.fixture(autouse=True)` here.\n"
    )
    assert body.mention_scan(text) == []


def test_escape_handles_backticks_live_mentions_only() -> None:
    assert body.escape_handles("thanks @alice and `@bob`") == "thanks `@alice` and `@bob`"


# --- step-7b footer -----------------------------------------------------------------------------------


def _with(footer: str) -> str:
    return "**REQUEST_CHANGES**\n\n- [major] api/client.py: keep the parameter.\n\n" + footer


def test_footer_case_1_present() -> None:
    result = body.verify_footer(_with(body.footer("request-changes", "Airflow", URL)))
    assert (result["footer_present"], result["action"]) == (True, "post")


def test_footer_case_2_missing() -> None:
    assert body.verify_footer(_with("(End of review body — no footer follows.)"))["action"] == "block"


def test_footer_case_3_paraphrased() -> None:
    para = "---\n\n> *This review was auto-generated and checked over by one of our\n> maintainers. Reply on the PR if anything looks wrong.*"
    assert body.verify_footer(_with(para)) == {"footer_present": False, "variant": None, "action": "block"}


def test_footer_case_4_role_neutral_comment() -> None:
    result = body.verify_footer(
        _with(body.footer("comment-role-neutral", "Airflow", URL)), "comment-role-neutral"
    )
    assert result["action"] == "post"


def test_footer_reflow_still_verifies() -> None:
    text = body.footer("approve", "Apache Foo", URL).replace("\n> ", " ")
    assert body.verify_footer(_with(text), "approve")["footer_present"]


def test_footer_without_contributing_url_drops_the_link_lines() -> None:
    text = body.footer("approve", "Foo", None)
    assert "Contributing guide" not in text and "More on how" not in text and text.endswith("follow up.*")


# --- picker, anchors, payload -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "keep"),
    [("A", [1, 2, 3]), ("", [1, 2, 3]), ("N", []), ("1,3", [1, 3]), ("-2", [1, 3]), ("-2,-3", [1])],
)
def test_picker_grammar(spec: str, keep: list[int]) -> None:
    assert body.pick(spec, 3)["keep"] == keep


def test_picker_edit_and_errors() -> None:
    assert body.pick("E 2", 3)["edit"] == 2
    for bad in ("4", "-9", "x", "E 7"):
        with pytest.raises(ValueError):
            body.pick(bad, 3)


DIFF = """diff --git a/hook.py b/hook.py
index 1..2 100644
--- a/hook.py
+++ b/hook.py
@@ -10,4 +10,5 @@ def f():
     a = 1
-    b = 2
+    b = 3
+    c = 4
     return a
@@ -40,2 +41,3 @@ def g():
     x = 1
+    y = 2
"""


def test_anchor_uses_line_and_side_and_the_legacy_position() -> None:
    files = diff.parse(DIFF)
    assert diff.anchor(files, "hook.py", 12, "RIGHT") == {
        "path": "hook.py",
        "line": 12,
        "side": "RIGHT",
        "position": 4,
    }
    assert diff.anchor(files, "hook.py", 11, "LEFT") == {
        "path": "hook.py",
        "line": 11,
        "side": "LEFT",
        "position": 2,
    }
    # The second hunk header counts as a line for the legacy position.
    second = diff.anchor(files, "hook.py", 42, "RIGHT")
    assert second is not None and second["position"] == 8
    assert diff.anchor(files, "hook.py", 99) is None


def test_compose_orders_sections_and_folds_dropped_inline_comments() -> None:
    findings = [
        {
            "file": "hook.py",
            "line": 12,
            "severity": "blocking",
            "rule_id": "No SQL from strings",
            "quoted_rule": "Never.",
            "explanation": "Use bound parameters.",
        },
        {
            "file": "hook.py",
            "line": 42,
            "severity": "minor",
            "rule_id": "naming",
            "explanation": "Rename @y please.",
        },
        {"file": "hook.py", "line": 11, "severity": "nit", "rule_id": "style", "explanation": "Spacing."},
    ]
    text = body.compose(
        summary="Found 1 blocking issue.",
        findings=findings,
        inline_kept=[2],
        footer_text=body.footer("request-changes", "Foo", URL),
        reviewers=[{"login": "alice", "reason": "owner"}],
        conflict_note="Rebase needed.",
    )
    assert text.index("Found 1 blocking") < text.index("Rebase needed") < text.index("### Blocking — No SQL")
    assert "See inline comments on `hook.py:42`" in text and "`hook.py:11` — Spacing." in text
    assert "@y" not in text and "`@alice`" in text and body.mention_scan(text) == []
    assert body.verify_footer(text, "request-changes")["footer_present"]


def test_inline_comments_and_payload() -> None:
    files = diff.parse(DIFF)
    findings = [
        {"file": "hook.py", "line": 12, "comment": "ask @bob"},
        {"file": "hook.py", "line": 99, "comment": "x"},
    ]
    result = body.inline_comments(findings, [1, 2], files)
    assert result["threads"][0]["body"] == "ask `@bob`" and result["unanchorable"] == [
        {"index": 2, "file": "hook.py", "line": 99}
    ]
    payload = json.loads(body.review_payload("PR_1", "COMMENT", "Body", result["threads"]))
    assert payload["variables"]["threads"] == [
        {"path": "hook.py", "line": 12, "side": "RIGHT", "body": "ask `@bob`"}
    ]
    assert "addPullRequestReview" in payload["query"]
