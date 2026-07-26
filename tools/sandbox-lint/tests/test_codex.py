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

"""Tests for the Codex project-profile invariants of sandbox-lint."""

from __future__ import annotations

from pathlib import Path

import pytest

from sandbox_lint import main
from sandbox_lint.codex import check_codex_invariants

SAFE_CONFIG = {
    "sandbox_mode": "workspace-write",
    "approval_policy": "on-request",
    "sandbox_workspace_write": {"network_access": False},
}
SAFE_RULES = """
prefix_rule(pattern = ["git", "push"], decision = "prompt")
prefix_rule(pattern = ["gh", "pr", "create"], decision = "prompt")
prefix_rule(pattern = ["gh", "issue", "create"], decision = "prompt")
prefix_rule(pattern = ["gh", "auth", ["token", "refresh"]], decision = "forbidden")
prefix_rule(pattern = ["gh", "pr", "view"], decision = "allow")
prefix_rule(pattern = ["gh", "api"], decision = "prompt")
"""


def test_repository_codex_profile_is_clean(
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = Path(__file__).resolve().parents[3]
    assert main(["--codex", str(repo / ".codex")]) == 0
    assert "OK" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("key", "value", "needle"),
    [
        ("sandbox_mode", "danger-full-access", "sandbox_mode"),
        ("approval_policy", "never", "approval_policy"),
    ],
)
def test_unsafe_top_level_config_is_flagged(key: str, value: str, needle: str) -> None:
    config = dict(SAFE_CONFIG)
    config[key] = value
    errors = check_codex_invariants(config, SAFE_RULES)
    assert any(needle in error for error in errors)


def test_network_access_must_be_false() -> None:
    config = dict(SAFE_CONFIG)
    config["sandbox_workspace_write"] = {"network_access": True}
    errors = check_codex_invariants(config, SAFE_RULES)
    assert any("network_access" in error for error in errors)


def test_required_hitl_rules_are_checked() -> None:
    errors = check_codex_invariants(SAFE_CONFIG, "")
    assert any("prefix_rule" in error for error in errors)


def test_release_download_cannot_be_unconditionally_allowed() -> None:
    rules = SAFE_RULES + ('\nprefix_rule(pattern = ["gh", "release", "download"], decision = "allow")\n')
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("release download" in error for error in errors)


def test_commented_out_rule_does_not_satisfy_invariants() -> None:
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["git", "push"], decision = "prompt")',
        '# prefix_rule(pattern = ["git", "push"], decision = "prompt")',
    )
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("git push" in error for error in errors)


def test_indented_and_multiline_comments_are_ignored() -> None:
    # Indented comments and a fully commented-out multiline declaration
    # must not satisfy the git-push invariant.
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["git", "push"], decision = "prompt")',
        '    # prefix_rule(pattern = ["git", "push"], decision = "prompt")\n'
        "# prefix_rule(\n"
        '#     pattern = ["git", "push"],\n'
        '#     decision = "prompt",\n'
        "# )",
    )
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("git push" in error for error in errors)


def test_multiline_rule_declaration_is_recognized() -> None:
    # The committed magpie.rules uses one-argument-per-line declarations;
    # the block parser must see them exactly like single-line rules.
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["git", "push"], decision = "prompt")',
        'prefix_rule(\n    pattern = ["git", "push"],\n    decision = "prompt",\n)',
    )
    assert check_codex_invariants(SAFE_CONFIG, rules) == []


def test_allow_rule_ending_in_mutation_verb_is_flagged() -> None:
    # Codex most-specific matching means a later allow can silently
    # override a committed prompt rule; the linter must reject it.
    rules = SAFE_RULES + ('\nprefix_rule(pattern = ["gh", "pr", "merge"], decision = "allow")\n')
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("mutation" in error and "merge" in error for error in errors)


def test_allow_rule_with_inner_run_noun_is_clean() -> None:
    # "run" as an inner token is the workflow-run noun, not a verb; only
    # the final element is checked against the mutation-verb set.
    rules = SAFE_RULES + (
        '\nprefix_rule(pattern = ["gh", "run", ["view", "list", "watch"]], decision = "allow")\n'
    )
    assert check_codex_invariants(SAFE_CONFIG, rules) == []


def test_gh_auth_refresh_must_be_forbidden() -> None:
    # Forbidding only the token half of the credential surface is not
    # enough; refresh rotates the credential and must stay forbidden too.
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["gh", "auth", ["token", "refresh"]], decision = "forbidden")',
        'prefix_rule(pattern = ["gh", "auth", "token"], decision = "forbidden")',
    )
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("gh auth refresh" in error for error in errors)


def test_ungoverned_gh_api_is_flagged() -> None:
    # The raw API passthrough can express any mutation; without a rule of
    # its own it skips the descriptive per-action prompt that every other
    # gh mutation gets.
    rules = SAFE_RULES.replace('prefix_rule(pattern = ["gh", "api"], decision = "prompt")\n', "")
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("gh api" in error for error in errors)


def test_justification_wording_cannot_trip_a_check() -> None:
    # A quoted "download" inside a justification string must not trigger
    # the release-download invariant; only pattern tokens count.
    rules = SAFE_RULES + (
        '\nprefix_rule(pattern = ["gh", "release", "list"], decision = "allow",'
        " justification = 'listing releases, excludes \"download\" artifacts')\n"
    )
    assert check_codex_invariants(SAFE_CONFIG, rules) == []


def test_justification_wording_cannot_satisfy_a_check() -> None:
    # Quoted "git" / "push" tokens inside a justification string must not
    # satisfy the git-push prompt invariant on behalf of a missing rule.
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["git", "push"], decision = "prompt")',
        'prefix_rule(pattern = ["gh", "repo", "view"], decision = "prompt",'
        ' justification = \'see the "git" "push" rule in the framework profile\')',
    )
    errors = check_codex_invariants(SAFE_CONFIG, rules)
    assert any("git push" in error for error in errors)


def test_parenthesis_in_justification_does_not_truncate_blocks() -> None:
    # A ')' inside a justification string must not end the rule block early
    # and hide the decision from the invariant checks.
    rules = SAFE_RULES.replace(
        'prefix_rule(pattern = ["git", "push"], decision = "prompt")',
        'prefix_rule(pattern = ["git", "push"], justification = "remote (see docs) mutation", decision = "prompt")',
    )
    assert check_codex_invariants(SAFE_CONFIG, rules) == []
