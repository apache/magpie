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


def test_review_body_may_mention_nobody(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch('gh pr review 5 --comment --body "@alice @bob see inline"')
    assert reason and "review body" in reason


def test_review_body_without_mentions_allowed():
    assert dispatch('gh pr review 5 --comment --body "see the inline comments"') is None


def test_graphql_review_payload_is_scanned(tmp_path):
    import json

    payload = tmp_path / "review.json"
    payload.write_text(
        json.dumps(
            {
                "query": "mutation($body: String!) { addPullRequestReview(input: {}) { clientMutationId } }",
                "variables": {
                    "body": "Summary",
                    "threads": [{"body": "ask `@carol`"}, {"body": "@dave look"}],
                },
            }
        ),
        encoding="utf-8",
    )
    reason = dispatch(f"gh api graphql --input {payload}")
    assert reason and "dave" in reason and "carol" not in reason


def test_any_graphql_write_is_scanned_not_just_reviews(tmp_path):
    """No mutation list: any GraphQL call sending an @-mention is refused."""
    import json

    payload = tmp_path / "q.json"
    payload.write_text(
        json.dumps({"query": "mutation { somethingNew(input: {}) { ok } }", "variables": {"note": "@x"}})
    )
    assert dispatch(f"gh api graphql --input {payload}")


def _git(repo, *args):
    import subprocess

    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def served(files, *, author="alice", repo="acme/product"):
    """A `_run` stub whose GitHub serves `files` (name → text) from `repo`'s default branch.

    The guard reads widening config only from there; any other repository,
    or a file not listed, is not found.
    """
    base = gh_stub(author=author)

    def _stub(args, cwd=None):
        for a in args:
            if "/contents/.apache-magpie-overrides/" in a:
                prefix = f"repos/{repo}/contents/.apache-magpie-overrides/"
                return files.get(a[len(prefix) :]) if a.startswith(prefix) else None
        if args[:3] == ["gh", "repo", "view"]:
            return repo
        return base(args)

    return _stub


def _team(handle):
    return {
        "mentoring-config.md": f"| Key | Value | Notes |\n|---|---|---|\n| `maintainer_team_handle` | `{handle}` | x |\n"
    }


def _allow(*handles):
    cell = " ".join(f"`{h}`" for h in handles)
    return {
        "pr-management-config.md": f"| Key | Value | Notes |\n|---|---|---|\n| `mention_allowlist` | {cell} | x |\n"
    }


def _handoff(tmp_path, body, repo_flag="--repo acme/product"):
    f = tmp_path / "b.md"
    f.write_text(body, encoding="utf-8")
    return agent_guard.dispatch(f"gh issue comment 7 {repo_flag} --body-file {f}", cwd=str(tmp_path))


def test_mentoring_handoff_may_mention_the_configured_team(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_team("@acme/committers")))
    assert _handoff(tmp_path, "@acme/committers — handing this off: should this be a plugin?") is None


def test_handoff_exemption_needs_the_template_opening(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_team("@acme/committers")))
    reason = _handoff(tmp_path, "hey @acme/committers look")
    assert reason and "acme/committers" in reason


def test_handoff_exemption_covers_the_team_only(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_team("@acme/committers")))
    reason = _handoff(tmp_path, "@acme/committers — handing this off: also @bob")
    assert reason and "bob" in reason


def test_handoff_never_reaches_another_organisation(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_team("@other-org/committers")))
    assert _handoff(tmp_path, "@other-org/committers — handing this off: q")


def _local_commit(tmp_path, name, text):
    """A config the agent wrote and committed itself, in a checkout it controls."""
    _git(tmp_path, "init", "-q")
    overrides = tmp_path / ".apache-magpie-overrides"
    overrides.mkdir(exist_ok=True)
    (overrides / name).write_text(text, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(
        tmp_path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "-c",
        "commit.gpgsign=false",
        "commit",
        "-q",
        "-m",
        "config",
    )


def test_handoff_ignores_a_team_committed_only_locally(monkeypatch, tmp_path):
    ((name, text),) = _team("@acme/committers").items()
    _local_commit(tmp_path, name, text)
    monkeypatch.setattr(agent_guard, "_run", served({}))
    assert _handoff(tmp_path, "@acme/committers — handing this off: q")


def test_handoff_ignores_a_team_served_by_another_repository(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_team("@acme/committers"), repo="alice/product"))
    assert _handoff(tmp_path, "@acme/committers — handing this off: q")


def test_allowlisted_handle_passes_in_a_comment(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@release-bot", "@acme/docs-team")))
    assert (
        agent_guard.dispatch(
            'gh pr comment 5 --repo acme/product --body "@alice see @release-bot"', cwd=str(tmp_path)
        )
        is None
    )
    reason = agent_guard.dispatch(
        'gh pr comment 5 --repo acme/product --body "@release-bot and @bob"', cwd=str(tmp_path)
    )
    assert reason and "bob" in reason and "release-bot" not in reason


def test_allowlisted_handle_passes_in_reviews_and_api_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@acme/docs-team")))
    assert (
        agent_guard.dispatch(
            'gh pr review 5 -R acme/product --comment --body "cc @acme/docs-team"', cwd=str(tmp_path)
        )
        is None
    )
    assert (
        agent_guard.dispatch(
            'gh api repos/acme/product/issues/5/comments -f body="cc @acme/docs-team"', cwd=str(tmp_path)
        )
        is None
    )


def test_a_locally_committed_allowlist_is_ignored(monkeypatch, tmp_path):
    ((name, text),) = _allow("@bob").items()
    _local_commit(tmp_path, name, text)
    monkeypatch.setattr(agent_guard, "_run", served({}))
    assert agent_guard.dispatch('gh pr comment 5 --repo acme/product --body "@bob"', cwd=str(tmp_path))


def test_the_allowlist_of_the_api_endpoint_repository_governs(monkeypatch, tmp_path):
    """An API write to another repository does not borrow the checkout's allowlist."""
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(
        'gh api repos/victim/other/issues/5/comments -f body="@bob"', cwd=str(tmp_path)
    )


@pytest.mark.parametrize(
    "command",
    [
        'gh pr comment 5 --body "@bob"',
        'gh pr comment https://github.com/victim/other/pull/5 --repo acme/product --body "@bob"',
        'gh pr comment 5 --repo acme/product --repo victim/other --body "@bob"',
        'gh pr comment 5 --repo acme/product -Rvictim/other --body "@bob"',
        'gh api repos/acme/product/../../victim/other/issues/5/comments -f body="@bob"',
        'gh api repos/acme/product%2F..%2F../victim/issues/5/comments -f body="@bob"',
        'gh api repos/{owner}/{repo}/issues/5/comments -f body="@bob"',
        'gh pr comment 5 --body "@bob, see https://github.com/acme/product/pull/1"',
    ],
)
def test_no_allowlist_unless_the_target_is_explicit_and_unambiguous(monkeypatch, tmp_path, command):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(command, cwd=str(tmp_path))


def test_the_attached_short_repo_flag_names_the_target(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert (
        agent_guard.dispatch('gh pr comment 5 -Racme/product --body "@alice @bob"', cwd=str(tmp_path)) is None
    )


def test_a_pr_url_names_the_target(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert (
        agent_guard.dispatch(
            'gh pr comment https://github.com/acme/product/pull/5 --body "@alice @bob"', cwd=str(tmp_path)
        )
        is None
    )


def test_graphql_writes_get_no_allowlist(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(
        'gh api graphql -f query="mutation { x(body: \\"@bob\\") }"', cwd=str(tmp_path)
    )


# --- bodies the guard cannot read, and text posted through `gh api` --------- #


def test_comment_body_on_stdin_is_refused(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch("gh pr comment 5 --body-file -")
    assert reason and "cannot be inspected" in reason


def test_unreadable_body_file_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch(f"gh pr edit 5 --body-file {tmp_path / 'missing.md'}")
    assert reason and "cannot be inspected" in reason


def test_review_body_on_stdin_is_refused():
    reason = dispatch("gh pr review 5 --comment --body-file -")
    assert reason and "cannot be inspected" in reason


def test_rest_comment_through_gh_api_is_scanned(tmp_path):
    body = tmp_path / "c.md"
    body.write_text("ping @bob", encoding="utf-8")
    reason = dispatch(f"gh api repos/acme/product/issues/5/comments -F body=@{body}")
    assert reason and "bob" in reason


def test_rest_review_field_through_gh_api_is_scanned():
    reason = dispatch(
        'gh api -X POST repos/acme/product/pulls/5/reviews -f body="cc @carol" -f event=COMMENT'
    )
    assert reason and "carol" in reason


def test_graphql_comment_mutation_in_a_field_is_scanned():
    reason = dispatch(
        'gh api graphql -f query="mutation { addComment(input: {subjectId: \\"X\\", body: \\"@dave hi\\"}) '
        '{ clientMutationId } }"'
    )
    assert reason and "dave" in reason


def test_graphql_on_stdin_is_refused():
    reason = dispatch("gh api graphql --input -")
    assert reason and "cannot be inspected" in reason


@pytest.mark.parametrize(
    "command",
    [
        'gh api -XPOST repos/acme/product/issues/5/comments -f body="hi @bob"',
        'gh api --method=PATCH repos/acme/product/issues/comments/9 -f body="hi @bob"',
        'gh api repos/acme/product/issues/5/comments -fbody="hi @bob"',
        'gh api repos/acme/product/issues/5/comments --raw-field=body="hi @bob"',
        'gh api repos/acme/product/issues/5/comments --field=body="hi @bob"',
        'gh api repos/acme/product/some/new/endpoint -f note="hi @bob"',
    ],
)
def test_every_spelling_of_a_gh_api_write_is_scanned(command):
    reason = dispatch(command)
    assert reason and "bob" in reason


def test_a_field_file_in_attached_form_is_read(tmp_path):
    body = tmp_path / "c.md"
    body.write_text("ping @bob", encoding="utf-8")
    assert dispatch(f"gh api repos/acme/product/issues/5/comments --field=body=@{body}")


def test_an_explicit_get_is_not_scanned():
    assert dispatch('gh api -X GET search/issues -f q="mentions:@bob"') is None


def test_api_reads_are_not_scanned():
    assert dispatch("gh api repos/acme/product/issues/5/comments") is None
    assert dispatch('gh api graphql -f query="query { viewer { login } }"') is None


def test_api_text_without_mentions_passes():
    assert dispatch('gh api repos/acme/product/issues/5/comments -f body="thanks, merged"') is None


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


@pytest.mark.parametrize(
    "labels",
    [
        pytest.param('--add-label triaged --add-label "ready for maintainer review"', id="repeated-flag"),
        pytest.param('--add-label "triaged,ready for maintainer review"', id="comma-separated"),
        pytest.param('--add-label=triaged --add-label="ready for maintainer review"', id="equals-form"),
        pytest.param("--add-label 'triaged,\"ready for maintainer review\"'", id="csv-quoted"),
        # gh reads the first --add-label as the --body value; the second adds the label.
        pytest.param('--body --add-label --add-label "ready for maintainer review"', id="flag-as-value"),
    ],
)
def test_mark_ready_pending_denied_for_every_add_label_form(monkeypatch, labels):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_mark_ready_handler("2")))
    reason = dispatch(f"gh pr edit 5 --repo o/r {labels}")
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


@pytest.mark.parametrize(
    "body",
    [
        "prevents SSRF in the connection test endpoint",
        "blocks path traversal in the log endpoint",
    ],
)
def test_security_class_names_denied(body):
    # The vulnerability class is embargoed on a public PR (AGENTS.md); the
    # skill's 5c list forbids the same names.
    reason = dispatch(f'gh pr create --title "fix" --body "{body}"')
    assert reason and "security-language" in reason


def test_security_language_in_comment_allowed():
    # Comments are out of scope (avoids colliding with the triage security warning).
    assert dispatch('gh pr comment 5 --body "this looks like a SQL injection risk"') is None


def test_security_override():
    cmd = 'MAGPIE_ALLOW_SECURITY_LANG=1 gh pr create --title "Fix CVE-2026-1234" --body "x"'
    assert dispatch(cmd) is None
