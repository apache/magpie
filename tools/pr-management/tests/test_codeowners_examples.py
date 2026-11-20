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

"""GitHub's own CODEOWNERS examples, run against both matcher modules.

The cases come from "About code owners" in the GitHub docs. They pin the
three mismatches from #2203: `docs/*` matched nested files, `apps/` matched
only at the repository root, and `**/logs` missed `logs/x.log`.
"""

from __future__ import annotations

import pytest

from pr_management.code_review import codeowners as code_review
from pr_management.reviewer_routing import codeowners as reviewer_routing

EXAMPLES = (
    ("* @all", "a/b/c.txt", ("all",)),
    ("*.js @js", "src/a/b.js", ("js",)),
    ("docs/* @docs", "docs/getting-started.md", ("docs",)),
    ("docs/* @docs", "docs/build-app/troubleshooting.md", ()),
    ("docs/*.md @docs", "docs/a/b.md", ()),
    ("apps/ @apps", "src/apps/x.py", ("apps",)),
    ("apps/ @apps", "apps/x.py", ("apps",)),
    ("/docs/ @docs", "docs/x.md", ("docs",)),
    ("/docs/ @docs", "a/docs/x.md", ()),
    ("**/logs @logs", "logs/x.log", ("logs",)),
    ("**/logs @logs", "deeply/nested/logs/x.log", ("logs",)),
    ("/apps/ @octocat\n/apps/github @doctocat", "apps/github/x.py", ("doctocat",)),
    ("/apps/ @octocat\n/apps/github", "apps/github/x.py", ()),
    ("/apps/github/docs/ @doctocat", "apps/github/docs/a.md", ("doctocat",)),
    ("/Docs/ @docs", "docs/x.md", ()),
)


def code_review_owners(text: str, path: str) -> tuple[str, ...]:
    return tuple(owner.lstrip("@") for owner in code_review.owners_of(code_review.parse(text), path))


def reviewer_routing_owners(text: str, path: str) -> tuple[str, ...]:
    return tuple(reviewer_routing.owners_of(path, reviewer_routing.parse(text)))


@pytest.mark.parametrize(("text", "path", "expected"), EXAMPLES)
def test_code_review_matches_the_github_examples(text: str, path: str, expected: tuple[str, ...]) -> None:
    assert code_review_owners(text, path) == expected


@pytest.mark.parametrize(("text", "path", "expected"), EXAMPLES)
def test_reviewer_routing_matches_the_github_examples(
    text: str, path: str, expected: tuple[str, ...]
) -> None:
    assert reviewer_routing_owners(text, path) == expected
