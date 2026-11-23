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


"""The CODEOWNERS panel resolves owners the way GitHub and code-review do (#2167)."""

from __future__ import annotations

import pytest

from pr_management.code_review import codeowners
from pr_management.stats import reference


def _ready_pr(number: int) -> dict:
    return {
        "number": number,
        "_has_ready": True,
        "_author": "contributor",
        "commits": {"nodes": []},
        "comments": {"nodes": []},
    }


def _panel_owners(codeowners_text: str, path: str) -> set[str]:
    rows = reference.compute_codeowners_panel([_ready_pr(1)], {1: [path]}, codeowners_text)
    return {owner for owner, _prs, _waiting in rows}


@pytest.mark.parametrize(
    ("codeowners_text", "path", "expected"),
    [
        # A bare `*.py` owns .py files at any depth, not only at the root or one level down.
        ("*.py @py\n", "src/pkg/mod.py", {"py"}),
        # A later rule with no owner clears an earlier match.
        ("/build/ @infra\n/build/generated/\n", "build/generated/x.txt", set()),
        # `.` in a pattern is literal.
        ("src/a.b/ @dots\n", "src/aXb/file.txt", set()),
        # `/docs` names the path `docs`, not every path that starts with it.
        ("/docs @docs\n", "docs-internal/x.md", set()),
        ("/docs @docs\n", "docs/x.md", {"docs"}),
    ],
)
def test_panel_owners_follow_github_rules(codeowners_text: str, path: str, expected: set[str]) -> None:
    assert _panel_owners(codeowners_text, path) == expected


def test_panel_agrees_with_code_review() -> None:
    text = "* @everyone\n*.py @py\n/docs/ @docs @org/writers\n/build/generated/\n"
    for path in ("README.md", "src/pkg/mod.py", "docs/guide.md", "build/generated/x.txt"):
        expected = {o.lstrip("@") for o in codeowners.owners_of(codeowners.parse(text), path)}
        assert _panel_owners(text, path) == expected, path


def test_panel_leaves_out_email_owners() -> None:
    assert _panel_owners("*.md @docs owner@example.org\n", "README.md") == {"docs"}
