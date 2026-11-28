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
"""Magpie's own committed policy loads, and every grant in it names a real operation.

Two pull requests can each add a valid `[callers]` entry and still merge into an
invalid file (the same key declared twice); git merges the lines cleanly, so only
loading the merged policy catches it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vetted_ops import cli, config, git_ops
from vetted_ops import ops as ops_mod

COMMITTED = (
    Path(__file__).resolve().parents[3] / ".apache-magpie-overrides" / "tools" / "vetted-ops" / "config.toml"
)


def test_the_committed_policy_loads() -> None:
    _ = cli  # importing the CLI registers every operation module
    policy = config.load(COMMITTED)
    assert policy.upstream_repo == "apache/magpie"


def test_every_granted_operation_exists() -> None:
    known = set(ops_mod.OPS) | set(git_ops.OPS)
    policy = config.load(COMMITTED)
    unknown = {caller: sorted(ops - known) for caller, ops in policy.callers.items() if ops - known}
    assert unknown == {}


LABELS_DOC = Path(__file__).resolve().parents[3] / "docs" / "labels-and-capabilities.md"


def _upstream_label(value: str) -> str:
    policy = config.load(COMMITTED)
    key = ops_mod.OPS["pr-add-label"].enums["label"]
    return ops_mod.enum(policy.enum_values(key), policy.enum_patterns(key))(value)


def test_every_taxonomy_label_can_be_set_from_the_sandbox() -> None:
    """The framework-fix callers label their pull requests with `pr-add-label`, one dimension each.

    Labels are listed by name in the policy (a pattern may not widen them), so
    a label added to the taxonomy doc without a policy entry fails here.
    """
    named = set(
        re.findall(r"`((?:family|capability|contract|substrate):[a-z0-9-]+)`", LABELS_DOC.read_text())
    )
    assert {"family:tools", "capability:fix", "contract:source-control"} <= named
    for label in sorted(named):
        assert _upstream_label(label) == label
    for caller in ("setup-upstream-fix", "setup-override-upstream"):
        assert "pr-add-label" in config.load(COMMITTED).callers[caller]


@pytest.mark.parametrize(
    "value", ["family:not-a-label", "family:Tools", "family:tools,security", "other:thing"]
)
def test_an_unlisted_label_is_refused(value: str) -> None:
    with pytest.raises(ops_mod.ParamError):
        _upstream_label(value)


SETTINGS = Path(__file__).resolve().parents[3] / ".claude" / "settings.json"


def _repo_edit_denies() -> list[str]:
    """The repository paths `.claude/settings.json` keeps the agent from editing."""
    rules = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["deny"]
    paths = []
    for rule in rules:
        if not (rule.startswith("Edit(") and rule.endswith(")")):
            continue
        path = rule[len("Edit(") : -1]
        if path.startswith(("~", "/")) and not path.startswith("//**/"):
            continue  # outside the repository
        path = path.removeprefix("//**/").removesuffix("/**")
        if "**" in path:
            continue  # a pattern inside a VCS directory, never a tracked path
        paths.append(path)
    return paths


def test_git_switch_treats_every_edit_protected_path_as_a_harness_path() -> None:
    """`git-switch` writes outside the sandbox; whatever the sandbox protects, it must check."""
    extra = config.load(COMMITTED).git
    harness = extra.get("harness_paths", []) if isinstance(extra, dict) else []
    paths = _repo_edit_denies()
    assert ".claude/settings.json" in paths
    missing = [path for path in paths if not git_ops.is_harness_path(path, harness)]
    assert missing == [], f"add these to [git] harness_paths in {COMMITTED.name}: {missing}"
