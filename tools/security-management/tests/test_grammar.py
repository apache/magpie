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
"""The confirmation-reply grammar.

The cases of the retired model-graded suite `security-issue-import/step-6-confirm`
live here, named after each former case, with the same scenario and the same
expected plan.
"""

from __future__ import annotations

import pytest

from security_management.shared.grammar import parse_reply

THREE = [{"n": 1, "importable": True}, {"n": 2, "importable": True}, {"n": 3, "importable": True}]
EXPECTED_KEYS = ("action", "import_items", "skip_items", "reject_with_canned", "edits", "ambiguous_tokens")


def subset(plan: dict[str, object]) -> dict[str, object]:
    return {k: plan[k] for k in EXPECTED_KEYS}


def test_case_1_default_import_all() -> None:
    candidates = [*THREE[:2], {"n": 3, "importable": False}]
    plan = parse_reply("go", candidates)
    assert subset(plan) == {
        "action": "import",
        "import_items": [1, 2],
        "skip_items": [],
        "reject_with_canned": [],
        "edits": [],
        "ambiguous_tokens": [],
    }
    assert plan["non_import_confirmed"] == [3]


def test_case_2_skip_and_reject() -> None:
    plan = parse_reply(
        "all skip 1 3:reject-with-canned When someone reports a DoS that requires authenticated access",
        THREE,
    )
    assert subset(plan) == {
        "action": "import",
        "import_items": [2],
        "skip_items": [1],
        "reject_with_canned": [
            {"item": 3, "canned_name": "When someone reports a DoS that requires authenticated access"}
        ],
        "edits": [],
        "ambiguous_tokens": [],
    }


def test_case_3_cancel() -> None:
    plan = parse_reply("hold off", THREE[:2])
    assert subset(plan) == {
        "action": "cancel",
        "import_items": [],
        "skip_items": [],
        "reject_with_canned": [],
        "edits": [],
        "ambiguous_tokens": [],
    }


def test_no_reply_imports_but_confirms_no_non_import_action() -> None:
    plan = parse_reply("", [*THREE[:1], {"n": 2, "importable": False}])
    assert plan["action"] == "import"
    assert plan["import_items"] == [1]
    assert plan["non_import_confirmed"] == []


def test_skip_several_and_keep_and_overrides() -> None:
    plan = parse_reply(
        "skip 1, 3; 2:title Webserver: session cookie missing Secure flag; keep 19d2f402867e957e",
        THREE,
    )
    assert plan["skip_items"] == [1, 3]
    assert plan["import_items"] == [2]
    assert plan["overrides"] == [
        {"item": 2, "field": "title", "value": "Webserver: session cookie missing Secure flag"}
    ]
    assert plan["keep"] == ["19d2f402867e957e"]
    assert plan["action"] == "import"


def test_public_fix_with_two_urls_and_an_edit() -> None:
    plan = parse_reply(
        "1:reject-with-public-fix https://github.com/apache/foo/pull/1, https://github.com/apache/foo/pull/2\n"
        "2:edit use only the first paragraph",
        THREE,
    )
    assert plan["reject_with_public_fix"] == [
        {
            "item": 1,
            "pr_urls": ["https://github.com/apache/foo/pull/1", "https://github.com/apache/foo/pull/2"],
        }
    ]
    assert plan["edits"] == [{"item": 2, "instruction": "use only the first paragraph"}]
    assert plan["import_items"] == [2, 3]


def test_free_text_is_ambiguous_and_holds_back_only_the_item_it_names() -> None:
    plan = parse_reply("hmm not sure about #3", THREE)
    assert plan["action"] == "ambiguous"
    assert plan["ambiguous_tokens"] == ["hmm not sure about #3"]
    assert plan["ambiguous_items"] == [3]
    assert plan["import_items"] == [1, 2]


def test_an_unknown_item_holds_every_action() -> None:
    plan = parse_reply("skip 9; skip 1", THREE)
    assert plan["action"] == "ambiguous"
    assert plan["ambiguous_tokens"] == ["skip 9"]
    assert plan["skip_items"] == []
    assert plan["import_items"] == []


def test_conflicting_dispositions_leave_every_actionable_list() -> None:
    plan = parse_reply("1:reject-with-canned A; skip 1", THREE)
    assert plan["action"] == "ambiguous"
    assert plan["ambiguous_items"] == [1]
    assert plan["skip_items"] == []
    assert plan["reject_with_canned"] == []
    assert plan["import_items"] == [2, 3]
    plan = parse_reply("1:reject-with-canned A; 1:reject-with-canned B", THREE)
    assert (plan["reject_with_canned"], plan["ambiguous_items"]) == ([], [1])
    plan = parse_reply("2:title X; 2:title Y", THREE)
    assert (plan["overrides"], plan["ambiguous_items"], plan["import_items"]) == ([], [2], [1, 3])


def test_identical_duplicates_are_one_action() -> None:
    plan = parse_reply("1:reject-with-canned A; 1:reject-with-canned A; skip 2, 2", THREE)
    assert plan["action"] == "import"
    assert plan["reject_with_canned"] == [{"item": 1, "canned_name": "A"}]
    assert plan["skip_items"] == [2]


@pytest.mark.parametrize(
    "reply", ["do not proceed", "don't go", "no", "yes, but wait", "go?? not yet", "stop"]
)
def test_a_negated_or_partial_go_confirms_nothing(reply: str) -> None:
    plan = parse_reply(reply, THREE)
    assert plan["non_import_confirmed"] == []
    assert plan["import_items"] == [] or plan["action"] == "cancel"


def test_unscoped_free_text_holds_everything() -> None:
    plan = parse_reply("skip 1; hmm, let me think about this", THREE)
    assert plan["action"] == "ambiguous"
    assert (plan["import_items"], plan["skip_items"], plan["non_import_confirmed"]) == ([], [], [])


def test_a_canned_name_may_hold_skip_and_keep() -> None:
    plan = parse_reply("2:reject-with-canned Please keep it short and skip the details", THREE)
    assert plan["reject_with_canned"] == [
        {"item": 2, "canned_name": "Please keep it short and skip the details"}
    ]
    assert plan["action"] == "import"


def test_a_form_the_caller_does_not_allow_is_ambiguous() -> None:
    plan = parse_reply("keep 19d2f402867e957e", THREE, allowed_forms={"go", "skip", "cancel"})
    assert plan["action"] == "ambiguous"
    assert plan["keep"] == []


def test_cancel_wins_over_everything_else() -> None:
    plan = parse_reply("skip 1\ncancel", THREE)
    assert plan["action"] == "cancel"
    assert plan["skip_items"] == []
