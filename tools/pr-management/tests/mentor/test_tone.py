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
"""The deterministic tone rules.

One test per case of the retired model-graded `tone-checks` suite
(`tools/skill-evals/evals/pr-management-mentor/tone-checks`), named after it.
Case 14 (jargon, rule 13) stays a model-judgement case in that suite.
"""

from __future__ import annotations

import pytest

from pr_management.mentor import tone

F = "<ai_attribution_footer>"


def run(body: str, author: str | None = None) -> dict:
    return tone.check(body, author=author, footer=None)


def test_case_1_clean_draft() -> None:
    r = run(
        "@alice — Could you add a reproduction script that isolates the failure?\n\n"
        "The [contributing guide](https://x/y#reproduction-scripts)\ncovers the expected format. A minimal script "
        "makes it easier for reviewers\nto confirm the fix independently.\n\n" + F,
        "alice",
    )
    assert r["result"] == "pass" and r["rule"] is None


@pytest.mark.parametrize(
    ("case", "body", "author", "rule", "result"),
    [
        (
            "case-2-praise-sentence",
            "@bob — Great question! The DAG serialization format changed in Airflow 2.4.\n\nSee the [guide](https://x).\n\n"
            + F,
            "bob",
            1,
            "hard_fail",
        ),
        (
            "case-3-ai-self-reference",
            "@carol — As an AI language model, I can help clarify the contributing process.\n\nSee the [guide](https://x).\n\n"
            + F,
            "carol",
            3,
            "hard_fail",
        ),
        (
            "case-4-hedging",
            "@dave — Perhaps you could run `pre-commit run --all-files` locally before\npushing, as it seems like the "
            "static-check failures may be fixable that way.\n\n" + F,
            "dave",
            5,
            "hard_fail",
        ),
        (
            "case-5-multiple-asks",
            "@eve — Could you add a unit test for the new operator class?\n\nAlso, could you update the CHANGELOG?\n\n"
            + F,
            "eve",
            6,
            "hard_fail",
        ),
        (
            "case-6-missing-footer",
            "@frank — Could you run the Breeze environment locally to reproduce the\nfailure before pushing?\n\n"
            "The [quick start guide](https://x) walks through setting up Breeze.",
            "frank",
            7,
            "hard_fail",
        ),
        (
            "case-7-too-long",
            "@grace — Could you add a `CHANGELOG` entry for this change?\n\nThe project tracks user-visible changes in "
            "`newsfragments/`. Each PR that\ntouches user-visible behaviour needs a fragment. The fragment filename\n"
            "should match your PR number. The fragment type should reflect the kind of\nchange: `feature`, `bugfix`, "
            "`doc`, `removal`, or `misc`. The content\nshould be a one-line summary written for an end user, not a "
            "developer.\nYou can find examples of existing fragments in the `newsfragments/` directory.\nRun "
            "`towncrier check` locally to verify the fragment is picked up correctly.\n\n" + F,
            "grace",
            12,
            "soft_fail",
        ),
        (
            "case-8-restating",
            "@henry — If I understand correctly, you're saying the tests are failing\nbecause the fixture data doesn't "
            "match the new schema.\n\nRun `pytest tests/ -x` to confirm.\n\n" + F,
            "henry",
            2,
            "hard_fail",
        ),
        (
            "case-9-speaking-for-maintainer",
            "@irene — Could you add the `CHANGELOG` entry to the `newsfragments/` directory?\n\nThe maintainers will "
            "probably want to see this before approving the PR.\n\n" + F,
            "irene",
            4,
            "hard_fail",
        ),
        (
            "case-10-author-not-tagged",
            "Could you add the Apache license header to the new source file?\n\nEvery file needs it.\n\n" + F,
            "olga",
            8,
            "hard_fail",
        ),
        (
            "case-11-quoted-doc",
            "@james — Could you update the PR description to follow the template?\n\nThe contributing guide says:\n\n"
            "> ## Description\n> A clear and concise description of what this PR does.\n>\n> ## Type of change\n"
            "> - Bug fix\n> - New feature\n> - Refactoring\n\nPlease fill in each section before requesting review.\n\n"
            + F,
            "james",
            9,
            "hard_fail",
        ),
        (
            "case-12-review-prediction",
            "@karen — Could you rebase this onto the current `main` branch?\n\nThe branch has conflicts that need to be "
            "resolved before this can be\nmerged. Once rebased, this should be approved quickly given the CI\nis "
            "otherwise green.\n\n" + F,
            "karen",
            10,
            "hard_fail",
        ),
        (
            "case-13-meta-first-line",
            "@leo — I'm reaching out because the PR is missing a reproduction script.\n\nAdd a minimal script under "
            "`scripts/` that isolates the failure.\n\n" + F,
            "leo",
            11,
            "soft_fail",
        ),
        (
            "case-15-exclamation-body",
            "@nina — Could you add the Apache license header to `hook.py`?\n\nEvery source file needs the standard "
            "header — the\n[license header guide](https://x)\nhas the exact format! Just copy it from any existing "
            "file.\n\n" + F,
            "nina",
            14,
            "soft_fail",
        ),
    ],
)
def test_tone_cases(case: str, body: str, author: str, rule: int, result: str) -> None:
    r = run(body, author)
    assert (r["rule"], r["result"]) == (rule, result), case


def test_case_2_quotes_the_praise_sentence() -> None:
    r = run("@bob — Great question! See the [guide](https://x).\n\n" + F, "bob")
    assert "Great question!" in r["offending_text"]


def test_the_configured_footer_counts_as_present() -> None:
    footer = "---\n\n_Drafted by a tool._"
    r = tone.check("@a — Could you add a test?\n\n" + footer, author="a", footer=footer)
    assert r["result"] == "pass"


def test_text_after_the_footer_fails_rule_7() -> None:
    assert run("@a — Could you add a test?\n\n" + F + "\n\nPS", "a")["rule"] == 7


def test_questions_inside_code_do_not_count() -> None:
    assert run("@a — Could you run `x?` and `y?` here?\n\n" + F, "a")["result"] == "pass"


def test_judgement_rules_are_listed_for_the_agent() -> None:
    assert {j["rule"] for j in run("@a — Could you add a test?\n\n" + F, "a")["judgement"]} == {2, 11, 13}
