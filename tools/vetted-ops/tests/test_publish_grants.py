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
"""Every operation the shared publishing block names is granted to each skill that carries it.

The `vetted-git-publish` block walks a publishing skill from a change to an
open, labelled pull request through vetted operations. Adopters, `setup
reconcile` and the isolated setup derive their policy grants from the
`[callers]` example in the vetted-ops README, so an operation the block names
but the example does not grant that skill is refused on every adopter, and the
step falls back to a pasted command. Magpie's own policy is checked the same
way for the callers it declares.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

from vetted_ops import cli, git_ops
from vetted_ops import ops as ops_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "tools" / "vetted-ops" / "README.md"
OWN_POLICY = REPO_ROOT / ".apache-magpie-overrides" / "tools" / "vetted-ops" / "config.toml"
BLOCK_BEGIN = "<!-- BEGIN MAGPIE BLOCK: vetted-git-publish"
BLOCK_END = "<!-- END MAGPIE BLOCK: vetted-git-publish -->"

#: Operations a caller does not need although the block names them, and why.
#: The draft-PR flows open their pull request as a draft in the browser
#: (`gh pr create --web --draft`), which the block's own fallback paragraph
#: covers, so they never open or label one through the vetted operations.
DRAFT_PR_FLOW = {"git-pr-create", "pr-add-label"}
NOT_NEEDED: dict[str, set[str]] = {
    "issue-fix-workflow": DRAFT_PR_FLOW,
    "audit-finding-fix": DRAFT_PR_FLOW,
    "release-prepare": DRAFT_PR_FLOW,
}


def _blocks() -> dict[str, str]:
    """Caller -> the publishing block as rendered into that skill."""
    found: dict[str, str] = {}
    for path in sorted(REPO_ROOT.glob("plugins/*/skills/*/vetted-git-publish.md")):
        text = path.read_text(encoding="utf-8")
        if BLOCK_BEGIN not in text:
            continue
        block = text[text.index(BLOCK_BEGIN) : text.index(BLOCK_END)]
        callers = set(re.findall(r"--caller ([a-z0-9-]+)", block))
        assert len(callers) == 1, f"{path}: expected one caller in the block, found {sorted(callers)}"
        found[callers.pop()] = block
    return found


def _named_ops(block: str) -> set[str]:
    """The vetted operations a block names, as the catalogues spell them."""
    assert cli  # importing the CLI registers every operation module
    known = set(ops_mod.OPS) | set(git_ops.OPS)
    words = set(re.findall(r"(?<![\w-])((?:git|pr)-[a-z]+(?:-[a-z]+)*)", block))
    return words & known


def _template_grants() -> dict[str, set[str]]:
    grants: dict[str, set[str]] = {}
    for toml in re.findall(r"```toml\n(.*?)```", README.read_text(encoding="utf-8"), re.S):
        if "[callers]" in toml:
            for caller, ops in tomllib.loads(toml).get("callers", {}).items():
                grants.setdefault(caller, set()).update(ops)
    return grants


def test_the_scan_finds_every_publishing_skill() -> None:
    blocks = _blocks()
    assert {"setup-upstream-fix", "pr-management-shepherd", "security-issue-fix"} <= set(blocks)
    assert {"git-commit", "git-push-branch", "git-pr-create", "pr-add-label"} <= _named_ops(
        blocks["setup-upstream-fix"]
    )


@pytest.mark.parametrize("caller", sorted(_blocks()))
def test_the_readme_template_grants_what_the_block_asks(caller: str) -> None:
    needed = _named_ops(_blocks()[caller]) - NOT_NEEDED.get(caller, set())
    missing = sorted(needed - _template_grants().get(caller, set()))
    assert not missing, f"{README.relative_to(REPO_ROOT)} does not grant {caller}: {missing}"


def test_magpies_own_policy_grants_what_the_block_asks() -> None:
    declared = tomllib.loads(OWN_POLICY.read_text(encoding="utf-8"))["callers"]
    missing = {
        caller: sorted(_named_ops(block) - NOT_NEEDED.get(caller, set()) - set(declared[caller]))
        for caller, block in _blocks().items()
        if caller in declared
    }
    assert not {c: m for c, m in missing.items() if m}, f"{OWN_POLICY.name} lacks: {missing}"
