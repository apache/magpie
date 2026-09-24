#
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
from __future__ import annotations

from adversarial_review.findings import Finding
from adversarial_review.merge import merge


def f(reviewer, severity="medium", file="app.py", line=10, claim="f() returns the wrong value"):
    return Finding(reviewer, severity, file, line, claim, f"evidence from {reviewer}")


def test_same_problem_from_two_reviewers_merges_and_keeps_both():
    [m] = merge(
        [f("codex", line=10), f("copilot", severity="high", line=12, claim="f returns a wrong value")]
    )
    assert m.reviewers == ["codex", "copilot"]
    assert m.severity == "high" and m.claim == "f returns a wrong value"
    assert [r.evidence for r in m.reports] == ["evidence from codex", "evidence from copilot"]


def test_far_apart_lines_do_not_merge():
    assert len(merge([f("codex", line=10), f("copilot", line=40)])) == 2


def test_different_claims_do_not_merge():
    assert len(merge([f("codex"), f("copilot", claim="missing authorization check on the endpoint")])) == 2


def test_null_lines_merge_on_claim():
    assert len(merge([f("codex", line=None), f("gemini", line=None)])) == 1


def test_sorted_by_severity_then_file_then_line():
    out = merge(
        [
            f("codex", severity="low", file="b.py", claim="one thing"),
            f("codex", severity="critical", file="z.py", claim="another thing entirely"),
            f("codex", severity="low", file="a.py", line=None, claim="third unrelated issue"),
        ]
    )
    assert [(m.severity, m.file) for m in out] == [("critical", "z.py"), ("low", "a.py"), ("low", "b.py")]


def test_as_dict_shape():
    [m] = merge([f("codex")])
    assert m.as_dict() == {
        "severity": "medium",
        "file": "app.py",
        "line": 10,
        "claim": "f() returns the wrong value",
        "reviewers": ["codex"],
        "reports": [
            {
                "reviewer": "codex",
                "severity": "medium",
                "claim": "f() returns the wrong value",
                "evidence": "evidence from codex",
            }
        ],
    }
