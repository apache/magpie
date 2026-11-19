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
"""The example CODEOWNERS file in GitHub's "About code owners", rule by rule.

Each case is one rule of that file with the owners its comment there promises
(https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#example-of-a-codeowners-file),
plus the gitignore reading of `**/logs` the page defers to (#2203).
"""

from __future__ import annotations

import pytest

from pr_management.code_review import codeowners

CASES = [
    ("*.js @js-owner", "src/app.js", ("@js-owner",)),
    ("/build/logs/ @doctocat", "build/logs/a.log", ("@doctocat",)),
    ("/build/logs/ @doctocat", "build/logs/sub/b.log", ("@doctocat",)),
    ("/build/logs/ @doctocat", "src/build/logs/a.log", ()),
    ("docs/* docs@example.com", "docs/getting-started.md", ("docs@example.com",)),
    ("docs/* docs@example.com", "docs/build-app/troubleshooting.md", ()),
    ("apps/ @octocat", "apps/x.py", ("@octocat",)),
    ("apps/ @octocat", "src/apps/x.py", ("@octocat",)),
    ("/docs/ @doctocat", "docs/build-app/troubleshooting.md", ("@doctocat",)),
    ("/docs/ @doctocat", "src/docs/a.md", ()),
    ("**/logs @octocat", "build/logs/a.log", ("@octocat",)),
    ("**/logs @octocat", "deeply/nested/logs/a.log", ("@octocat",)),
    ("**/logs @octocat", "logs/x.log", ("@octocat",)),
    ("/apps/ @octocat\n/apps/github", "apps/web/x.py", ("@octocat",)),
    ("/apps/ @octocat\n/apps/github", "apps/github/x.py", ()),
    ("/apps/ @octocat\n/apps/github @doctocat", "apps/github/x.py", ("@doctocat",)),
]


@pytest.mark.parametrize(("text", "path", "expected"), CASES)
def test_documented_example(text: str, path: str, expected: tuple[str, ...]) -> None:
    assert codeowners.owners_of(codeowners.parse(text), path) == expected


def test_a_wildcard_leaf_keeps_its_depth_rules() -> None:
    # Dropping the nested-file tail for `docs/*` must not stop a bare wildcard
    # matching at any depth, or `**` crossing directories.
    rules = codeowners.parse("*.py @py\nsrc/**/gen @gen\n")
    assert codeowners.owners_of(rules, "a/b/c.py") == ("@py",)
    assert codeowners.owners_of(rules, "src/x/y/gen/out.txt") == ("@gen",)
