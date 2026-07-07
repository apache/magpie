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

"""Tests for the skill-owned guards, exercised end-to-end through the agent-guard
discovery path — exactly how an adopter runs them. ``MAGPIE_GUARD_DIRS`` points
the dispatcher at the real ``skills/<skill>/guards`` directories in this repo, so
these tests fail if a guard file is moved, renamed, or broken."""

import os
from pathlib import Path

import pytest

import agent_guard

REPO_ROOT = Path(__file__).resolve().parents[3]
TRIAGE_GUARDS = REPO_ROOT / "skills" / "pr-management-triage" / "guards"
SECURITY_GUARDS = REPO_ROOT / "skills" / "security-issue-fix" / "guards"


@pytest.fixture(autouse=True)
def _wire_skill_guards(monkeypatch):
    for name in (
        "MAGPIE_GUARD_OFF",
        "MAGPIE_ALLOW_MENTIONS",
        "MAGPIE_ALLOW_MARK_READY",
        "MAGPIE_ALLOW_SECURITY_LANG",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MAGPIE_GUARD_DIRS", f"{TRIAGE_GUARDS}{os.pathsep}{SECURITY_GUARDS}")


def fake_run(handler):
    def _stub(args, cwd=None):
        return handler(args)

    return _stub


def gh_stub(*, author, operator="operator-bot"):
    """Distinguish the guard's two lookups: ``gh api user`` (operator identity)
    vs. ``gh pr/issue view`` (target author). Default operator differs from the
    author so a bare stub keeps the author-only rule in force."""

    def handler(args):
        if "api" in args and "user" in args:
            return operator
        return author

    return handler


def dispatch(command):
    return agent_guard.dispatch(command, cwd=None)


def test_guard_files_exist():
    assert (TRIAGE_GUARDS / "mention.py").is_file()
    assert (TRIAGE_GUARDS / "mark_ready.py").is_file()
    assert (SECURITY_GUARDS / "security_language.py").is_file()


# --- mention guard (skill-owned) ------------------------------------------- #


def test_mention_author_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('gh pr comment 5 --body "@alice thanks"') is None


def test_mention_non_author_denied(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch('gh pr comment 5 --body "@bob please review"')
    assert reason and "bob" in reason and "mention" in reason


def test_mention_own_pr_allows_maintainers(monkeypatch):
    # Operator commenting on their own PR may @-mention maintainers/reviewers.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice", operator="alice")))
    assert dispatch('gh pr comment 5 --body "@bob @carol please take a look"') is None


def test_mention_own_pr_case_insensitive(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="Alice", operator="alice")))
    assert dispatch('gh pr comment 5 --body "@bob review please"') is None


def test_mention_others_pr_still_denied_when_operator_known(monkeypatch):
    # Author is someone else; operator resolving successfully must not relax the rule.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice", operator="carol")))
    reason = dispatch('gh pr comment 5 --body "@bob ping"')
    assert reason and "bob" in reason and "mention" in reason


def test_fold_any_mention_denied(monkeypatch):
    # Hermetic: a non-author maintainer @-mention in a fold edit is denied.
    # Stubbed so it never depends on a real `gh pr view` (and so the own-PR
    # exemption, author == operator, is not accidentally triggered).
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="bob", operator="carol")))
    reason = dispatch('gh pr edit 5 --body "@alice heads up"')
    assert reason and "fold" in reason


def test_fold_clean_allowed():
    assert dispatch('gh pr edit 5 --body "rebased onto main, fixed conflicts"') is None


def test_mention_body_file(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    body = tmp_path / "b.md"
    body.write_text("@bob please look", encoding="utf-8")
    assert dispatch(f"gh pr comment 5 --body-file {body}") is not None


def test_mention_author_unresolved_fails_closed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(lambda a: None))
    reason = dispatch('gh pr comment 5 --body "@bob hi"')
    assert reason and "could not be verified" in reason


def test_mention_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('MAGPIE_ALLOW_MENTIONS=1 gh pr comment 5 --body "@bob ping"') is None


# --- mark-ready guard (skill-owned) ---------------------------------------- #


def _mark_ready_handler(pending):
    def handler(args):
        if "headRefOid" in args:
            return "deadbeefcafebabe1234"
        if any("actions/runs" in a for a in args):
            return pending
        return None

    return handler


def test_mark_ready_pending_denied(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_mark_ready_handler("2")))
    reason = dispatch('gh pr edit 5 --repo o/r --add-label "ready for maintainer review"')
    assert reason and "awaiting approval" in reason


def test_mark_ready_clean_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_mark_ready_handler("0")))
    assert dispatch('gh pr edit 5 --repo o/r --add-label "ready for maintainer review"') is None


def test_mark_ready_other_label_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(lambda a: None))
    assert dispatch('gh pr edit 5 --repo o/r --add-label "area:scheduler"') is None


def test_mark_ready_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_mark_ready_handler("3")))
    cmd = 'MAGPIE_ALLOW_MARK_READY=1 gh pr edit 5 --repo o/r --add-label "ready for maintainer review"'
    assert dispatch(cmd) is None


# --- security-language guard (skill-owned) --------------------------------- #


def test_security_cve_in_pr_create_denied():
    reason = dispatch('gh pr create --title "Fix CVE-2026-1234" --body "patch"')
    assert reason and "security" in reason.lower()


def test_security_keyword_in_pr_body_denied():
    assert dispatch('gh pr create --title "fix" --body "patches a SQL injection"') is not None


def test_security_clean_pr_create_allowed():
    assert dispatch('gh pr create --title "Add retry policy" --body "implements an AIP"') is None


def test_security_language_in_comment_allowed():
    # Comments are out of scope (avoids colliding with the triage security warning).
    assert dispatch('gh pr comment 5 --body "this looks like a SQL injection risk"') is None


def test_security_override():
    cmd = 'MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --title "Fix CVE-2026-1234" --body "x"'
    assert dispatch(cmd) is None
