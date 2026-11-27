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
the dispatcher at the canonical plugin or skill guard directories in this repo, so
these tests fail if a guard file is moved, renamed, or broken."""

import os
from pathlib import Path

import pytest

import agent_guard

REPO_ROOT = Path(__file__).resolve().parents[3]
TRIAGE_GUARDS = (
    REPO_ROOT / "plugins" / "magpie-pr-management" / "skills" / "pr-triage" / "guards"
    if (REPO_ROOT / "plugins" / "magpie-pr-management" / "skills" / "pr-triage" / "guards").is_dir()
    else REPO_ROOT / "skills" / "pr-management-triage" / "guards"
)
SECURITY_GUARDS = (
    REPO_ROOT / "plugins" / "magpie-security" / "skills" / "issue-fix" / "guards"
    if (REPO_ROOT / "plugins" / "magpie-security" / "skills" / "issue-fix" / "guards").is_dir()
    else REPO_ROOT / "skills" / "security-issue-fix" / "guards"
)
SETUP_GUARDS = (
    REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "isolated-setup-install" / "guards"
    if (REPO_ROOT / "plugins" / "magpie-setup" / "skills" / "isolated-setup-install" / "guards").is_dir()
    else REPO_ROOT / "skills" / "setup-isolated-setup-install" / "guards"
)


@pytest.fixture(autouse=True)
def _wire_skill_guards(monkeypatch):
    for name in (
        "MAGPIE_GUARD_OFF",
        "MAGPIE_ALLOW_MENTIONS",
        "MAGPIE_ALLOW_MARK_READY",
        "MAGPIE_ALLOW_SECURITY_LANG",
        "MAGPIE_ALLOW_LEFTHOOK_HOOKS_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(
        "MAGPIE_GUARD_DIRS",
        f"{TRIAGE_GUARDS}{os.pathsep}{SECURITY_GUARDS}{os.pathsep}{SETUP_GUARDS}",
    )


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
    assert (SETUP_GUARDS / "lefthook_hooks_path.py").is_file()


# --- mention guard (skill-owned) ------------------------------------------- #


def test_mention_author_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('gh pr comment 5 --body "<!-- pr-triage --> @alice thanks"') is None


def test_mention_non_author_denied(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch('gh pr comment 5 --body "<!-- pr-triage --> @bob please review"')
    assert reason and "bob" in reason and "mention" in reason


def test_mention_own_pr_allows_maintainers(monkeypatch):
    # Operator commenting on their own PR may @-mention maintainers/reviewers.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice", operator="alice")))
    assert dispatch('gh pr comment 5 --body "<!-- pr-triage --> @bob @carol please take a look"') is None


def test_mention_own_pr_case_insensitive(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="Alice", operator="alice")))
    assert dispatch('gh pr comment 5 --body "<!-- pr-triage --> @bob review please"') is None


def test_mention_others_pr_still_denied_when_operator_known(monkeypatch):
    # Author is someone else; operator resolving successfully must not relax the rule.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice", operator="carol")))
    reason = dispatch('gh pr comment 5 --body "<!-- pr-triage --> @bob ping"')
    assert reason and "bob" in reason and "mention" in reason


def test_mention_app_author_allowed(monkeypatch):
    # `gh pr view --json author` reports a GitHub App author as `app/<slug>`,
    # while its @-mention handle is `<slug>`: `@dependabot rebase` on a
    # Dependabot PR addresses the author.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="app/dependabot")))
    assert dispatch('gh pr comment 5 --body "<!-- pr-triage --> @dependabot rebase"') is None


def test_mention_bot_suffix_author_allowed(monkeypatch):
    # The REST spelling of the same author is `dependabot[bot]`.
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="dependabot[bot]")))
    assert dispatch('gh pr comment 5 --body "<!-- pr-triage --> @dependabot rebase"') is None


def test_mention_app_author_others_still_denied(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="app/dependabot")))
    reason = dispatch('gh pr comment 5 --body "<!-- pr-triage --> @dependabot rebase, @bob please merge"')
    # Only the maintainer is refused; the App author stays allowed.
    assert reason and "maintainer(s) ['bob']" in reason


def test_fold_any_mention_denied(monkeypatch):
    # Hermetic: a non-author maintainer @-mention in a fold edit is denied.
    # Stubbed so it never depends on a real `gh pr view` (and so the own-PR
    # exemption, author == operator, is not accidentally triggered).
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="bob", operator="carol")))
    reason = dispatch('gh pr edit 5 --body "<!-- pr-triage --> @alice heads up"')
    assert reason and "fold" in reason


def test_fold_clean_allowed():
    assert dispatch('gh pr edit 5 --body "<!-- pr-triage --> rebased onto main, fixed conflicts"') is None


def test_mention_body_file(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    body = tmp_path / "b.md"
    body.write_text("<!-- pr-triage --> @bob please look", encoding="utf-8")
    assert dispatch(f"gh pr comment 5 --body-file {body}") is not None


def test_mention_author_unresolved_fails_closed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(lambda a: None))
    reason = dispatch('gh pr comment 5 --body "<!-- pr-triage --> @bob hi"')
    assert reason and "could not be verified" in reason


def test_mention_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('MAGPIE_ALLOW_MENTIONS=1 gh pr comment 5 --body "<!-- pr-triage --> @bob ping"') is None


def test_graphql_review_payload_is_scanned(tmp_path):
    import json

    payload = tmp_path / "review.json"
    payload.write_text(
        json.dumps(
            {
                "query": "mutation($body: String!) { addPullRequestReview(input: {}) { clientMutationId } }",
                "variables": {
                    "body": "Summary",
                    "threads": [{"body": "ask `@carol`"}, {"body": "<!-- pr-triage --> @dave look"}],
                },
            }
        ),
        encoding="utf-8",
    )
    reason = dispatch(f"gh api graphql --input {payload.as_posix()}")
    assert reason and "dave" in reason and "carol" not in reason


def test_any_graphql_write_is_scanned_not_just_reviews(tmp_path):
    """No mutation list: any GraphQL call sending an @-mention is refused."""
    import json

    payload = tmp_path / "q.json"
    payload.write_text(
        json.dumps(
            {
                "query": "mutation { somethingNew(input: {}) { ok } }",
                "variables": {"note": "<!-- pr-triage --> @x"},
            }
        )
    )
    assert dispatch(f"gh api graphql --input {payload.as_posix()}")


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


def _allow(*handles):
    cell = " ".join(f"`{h}`" for h in handles)
    return {
        "pr-management-config.md": f"| Key | Value | Notes |\n|---|---|---|\n| `mention_allowlist` | {cell} | x |\n"
    }


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


def test_allowlisted_handle_passes_in_a_comment(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@release-bot", "@acme/docs-team")))
    assert (
        agent_guard.dispatch(
            'gh pr comment 5 --repo acme/product --body "<!-- pr-triage --> @alice see @release-bot"',
            cwd=str(tmp_path),
        )
        is None
    )
    reason = agent_guard.dispatch(
        'gh pr comment 5 --repo acme/product --body "<!-- pr-triage --> @release-bot and @bob"',
        cwd=str(tmp_path),
    )
    assert reason and "bob" in reason and "release-bot" not in reason


def test_allowlisted_handle_passes_in_api_writes(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@acme/docs-team")))
    assert (
        agent_guard.dispatch(
            'gh api repos/acme/product/issues/5/comments -f body="<!-- pr-triage --> cc @acme/docs-team"',
            cwd=str(tmp_path),
        )
        is None
    )


def test_a_locally_committed_allowlist_is_ignored(monkeypatch, tmp_path):
    ((name, text),) = _allow("@bob").items()
    _local_commit(tmp_path, name, text)
    monkeypatch.setattr(agent_guard, "_run", served({}))
    assert agent_guard.dispatch(
        'gh pr comment 5 --repo acme/product --body "<!-- pr-triage --> @bob"', cwd=str(tmp_path)
    )


def test_the_allowlist_of_the_api_endpoint_repository_governs(monkeypatch, tmp_path):
    """An API write to another repository does not borrow the checkout's allowlist."""
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(
        'gh api repos/victim/other/issues/5/comments -f body="<!-- pr-triage --> @bob"', cwd=str(tmp_path)
    )


@pytest.mark.parametrize(
    "command",
    [
        'gh pr comment 5 --body "<!-- pr-triage --> @bob"',
        'gh pr comment https://github.com/victim/other/pull/5 --repo acme/product --body "<!-- pr-triage --> @bob"',
        'gh pr comment 5 --repo acme/product --repo victim/other --body "<!-- pr-triage --> @bob"',
        'gh pr comment 5 --repo acme/product -Rvictim/other --body "<!-- pr-triage --> @bob"',
        'gh pr comment 5 --body "<!-- pr-triage --> -Racme/product @bob"',
        'gh pr comment 5 -b "<!-- pr-triage --> --repo=acme/product @bob"',
        'gh pr comment 5 --repo acme/product --unknown-flag x --body "<!-- pr-triage --> @bob"',
        'gh api --unknown x repos/acme/product/issues/5/comments -f body="<!-- pr-triage --> @bob"',
        'gh api repos/acme/product/issues/5/comments repos/victim/other/x -f body="<!-- pr-triage --> @bob"',
        'gh api repos/acme/product/../../victim/other/issues/5/comments -f body="<!-- pr-triage --> @bob"',
        'gh api repos/acme/product%2F..%2F../victim/issues/5/comments -f body="<!-- pr-triage --> @bob"',
        'gh api repos/{owner}/{repo}/issues/5/comments -f body="<!-- pr-triage --> @bob"',
        'gh pr comment 5 --body "<!-- pr-triage --> @bob, see https://github.com/acme/product/pull/1"',
    ],
)
def test_no_allowlist_unless_the_target_is_explicit_and_unambiguous(monkeypatch, tmp_path, command):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(command, cwd=str(tmp_path))


def test_the_attached_short_repo_flag_names_the_target(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert (
        agent_guard.dispatch(
            'gh pr comment 5 -Racme/product --body "<!-- pr-triage --> @alice @bob"', cwd=str(tmp_path)
        )
        is None
    )


def test_a_pr_url_names_the_target(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert (
        agent_guard.dispatch(
            'gh pr comment https://github.com/acme/product/pull/5 --body "<!-- pr-triage --> @alice @bob"',
            cwd=str(tmp_path),
        )
        is None
    )


def test_graphql_writes_get_no_allowlist(monkeypatch, tmp_path):
    monkeypatch.setattr(agent_guard, "_run", served(_allow("@bob")))
    assert agent_guard.dispatch(
        'gh api graphql -f query="mutation { x(body: \\"<!-- pr-triage --> @bob\\") }"', cwd=str(tmp_path)
    )


# --- bodies the guard cannot read, and text posted through `gh api` --------- #


def test_rest_comment_through_gh_api_is_scanned(tmp_path):
    body = tmp_path / "c.md"
    body.write_text("<!-- pr-triage --> ping @bob", encoding="utf-8")
    reason = dispatch(f"gh api repos/acme/product/issues/5/comments -F body=@{body.as_posix()}")
    assert reason and "bob" in reason


def test_rest_review_field_through_gh_api_is_scanned():
    reason = dispatch(
        'gh api -X POST repos/acme/product/pulls/5/reviews -f body="<!-- pr-triage --> cc @carol" -f event=COMMENT'
    )
    assert reason and "carol" in reason


def test_graphql_comment_mutation_in_a_field_is_scanned():
    reason = dispatch(
        'gh api graphql -f query="mutation { addComment(input: {subjectId: \\"X\\", body: \\"<!-- pr-triage --> @dave hi\\"}) '
        '{ clientMutationId } }"'
    )
    assert reason and "dave" in reason


@pytest.mark.parametrize(
    "command",
    [
        'gh api -XPOST repos/acme/product/issues/5/comments -f body="<!-- pr-triage --> hi @bob"',
        'gh api --method=PATCH repos/acme/product/issues/comments/9 -f body="<!-- pr-triage --> hi @bob"',
        'gh api repos/acme/product/issues/5/comments -fbody="<!-- pr-triage --> <!-- pr-triage --> hi @bob"',
        'gh api repos/acme/product/issues/5/comments --raw-field=body="<!-- pr-triage --> hi @bob"',
        'gh api repos/acme/product/issues/5/comments --field=body="<!-- pr-triage --> hi @bob"',
        'gh api repos/acme/product/some/new/endpoint -f note="<!-- pr-triage --> hi @bob"',
    ],
)
def test_every_spelling_of_a_gh_api_write_is_scanned(command):
    reason = dispatch(command)
    assert reason and "bob" in reason


def test_a_field_file_in_attached_form_is_read(tmp_path):
    body = tmp_path / "c.md"
    body.write_text("<!-- pr-triage --> ping @bob", encoding="utf-8")
    assert dispatch(f"gh api repos/acme/product/issues/5/comments --field=body=@{body}")


def test_an_explicit_get_is_not_scanned():
    assert dispatch('gh api -X GET search/issues -f q="mentions:@bob"') is None


def test_api_reads_are_not_scanned():
    assert dispatch("gh api repos/acme/product/issues/5/comments") is None
    assert dispatch('gh api graphql -f query="query { viewer { login } }"') is None


def test_api_text_without_mentions_passes():
    assert (
        dispatch('gh api repos/acme/product/issues/5/comments -f body="<!-- pr-triage --> thanks, merged"')
        is None
    )


# --- only triage bodies are checked ------------------------------------------ #


def test_a_comment_without_a_triage_marker_may_mention_anyone(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('gh pr comment 5 --body "@bob @carol please take a look"') is None


def test_a_review_is_never_checked(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('gh pr review 5 --request-changes --body "As @dpol1 said, see @bob"') is None


def test_a_body_edit_without_a_fold_may_mention_anyone():
    assert dispatch('gh pr edit 5 --body "Supersedes the work @alice started"') is None


def test_api_text_without_a_triage_marker_may_mention_anyone(tmp_path):
    import json

    payload = tmp_path / "review.json"
    payload.write_text(
        json.dumps({"event": "COMMENT", "body": "cc @carol", "comments": []}), encoding="utf-8"
    )
    assert dispatch(f"gh api repos/acme/product/pulls/5/reviews -X POST --input {payload.as_posix()}") is None


def test_a_mentoring_hand_off_is_not_triage(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch('gh issue comment 7 --body "@acme/committers — handing this off: q"') is None


def test_a_folded_note_is_recognised_by_its_fold_marker(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="bob", operator="carol")))
    reason = dispatch('gh pr edit 5 --body "<!-- pr-triage-fold: triaged=x --> @alice heads up"')
    assert reason and "fold" in reason


@pytest.mark.parametrize(
    "command",
    [
        "gh pr comment 5 --body-file -",
        "gh issue comment 5 --body-file -",
        "gh pr edit 5 --body-file {missing}",
        "gh api graphql --input -",
    ],
)
def test_a_body_the_guard_cannot_read_is_refused_whoever_posts_it(monkeypatch, tmp_path, command):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch(command.format(missing=tmp_path / "missing.md"))
    assert reason and "cannot be inspected" in reason


def test_an_unreadable_body_passes_with_the_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert dispatch("MAGPIE_ALLOW_MENTIONS=1 gh pr comment 5 --body-file -") is None


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


@pytest.mark.parametrize("prefix", ["env ", "env -i ", "env FOO=1 ", "command ", "env command "])
def test_prefix_wrappers_reach_the_mention_guard(monkeypatch, prefix):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    reason = dispatch(f'{prefix}gh pr comment 5 --body "<!-- pr-triage --> @bob please review"')
    assert reason and "bob" in reason and "mention" in reason


def test_an_override_on_env_still_counts(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(gh_stub(author="alice")))
    assert (
        dispatch('env MAGPIE_ALLOW_MENTIONS=1 gh pr comment 5 --body "<!-- pr-triage --> @bob ping"') is None
    )


# --- lefthook hooks-path guard (skill-owned) ------------------------------- #

FRAMEWORK_HOOKS = "~/.claude/git-hooks"


def hooks_path_stub(value):
    def handler(args):
        if args[:2] == ["git", "config"]:
            return value
        return None

    return handler


@pytest.mark.parametrize("hooks_path", [FRAMEWORK_HOOKS, "~/.claude-config/git-hooks"])
@pytest.mark.parametrize(
    "command, flag",
    [
        ("lefthook install --force", "--force"),
        ("lefthook install -f", "--force"),
        ("lefthook install --force=true", "--force"),
        ("lefthook install --force=1", "--force"),
        ("lefthook install --reset-hooks-path", "--reset-hooks-path"),
        ("lefthook install --reset-hooks-path=true", "--reset-hooks-path"),
        ("lefthook install -r", "--reset-hooks-path"),
        ("lefthook install -fr", "--force"),
        ("lefthook install -fr=false", "--force"),
        ("lefthook install -rf=false", "--reset-hooks-path"),
        ("lefthook --verbose install --force", "--force"),
        ("./node_modules/.bin/lefthook install --force", "--force"),
        ("lefthook --colors off install --force", "--force"),
        ("lefthook --colors off install -r", "--reset-hooks-path"),
        ("lefthook install pre-commit --force", "--force"),
        ("npx lefthook install --force", "--force"),
        ("npx -y lefthook@1.11.0 install -f", "--force"),
        ("npx @evilmartians/lefthook install --force", "--force"),
        ("npm exec -- lefthook install --force", "--force"),
        ("pnpm exec lefthook install --reset-hooks-path", "--reset-hooks-path"),
        ("pnpm --filter app exec lefthook install -f", "--force"),
        ("pnpm dlx lefthook install --force", "--force"),
        ("yarn exec lefthook install -f", "--force"),
        ("yarn dlx lefthook install --force", "--force"),
        ("bunx lefthook install -r", "--reset-hooks-path"),
        ("env CI=1 npx lefthook --colors off install --force", "--force"),
        ("npx -c 'lefthook install --force'", "--force"),
        ("npm exec -c 'lefthook install --force'", "--force"),
        ("npm exec --call='lefthook install -f'", "--force"),
        ("pnpm exec --shell-mode 'lefthook install -r'", "--reset-hooks-path"),
        ("pnpm exec bash -c 'lefthook install --force'", "--force"),
        ("npx sh -c 'cd app && lefthook install --force'", "--force"),
        ("corepack pnpm exec lefthook install --force", "--force"),
        ("npx.cmd lefthook install --force", "--force"),
        ("pnpm.CMD exec lefthook install -r", "--reset-hooks-path"),
        ("lefthook.bat install --force", "--force"),
        ("bun -c bunfig.toml x lefthook install --force", "--force"),
        ("pnpm --filter sh exec lefthook install --force", "--force"),
    ],
)
def test_lefthook_destructive_install_denied(monkeypatch, hooks_path, command, flag):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(hooks_path)))
    reason = dispatch(command)
    assert reason and "lefthook-hooks-path" in reason and flag in reason


@pytest.mark.parametrize(
    "command",
    [
        "lefthook install",
        "lefthook install --verbose",
        "lefthook run pre-commit",
        "lefthook --version",
        "lefthook --colors off install",
        "npx lefthook install",
        "npx lefthook run pre-commit --force",
        "npm install --save-dev lefthook --force",
        "pnpm add -D lefthook",
        "npx prettier --write install",
        "npx -c 'lefthook install'",
        "npx -c 'prettier --write .'",
        "pnpm exec bash -c 'lefthook run pre-commit'",
        "corepack pnpm exec lefthook install",
    ],
)
def test_lefthook_plain_invocations_allowed(monkeypatch, command):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(FRAMEWORK_HOOKS)))
    assert dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "lefthook install --force=false",
        "lefthook install --reset-hooks-path=false",
        "lefthook install -f=false",
    ],
)
def test_lefthook_switched_off_destructive_flag_allowed(monkeypatch, command):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(FRAMEWORK_HOOKS)))
    assert dispatch(command) is None


def test_lefthook_destructive_install_allowed_for_another_global_path(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub("/opt/other-hooks")))
    assert dispatch("lefthook install --force") is None


def test_lefthook_destructive_install_allowed_without_a_global_path(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(None)))
    assert dispatch("lefthook install --reset-hooks-path") is None


def test_lefthook_destructive_install_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(FRAMEWORK_HOOKS)))
    assert dispatch("MAGPIE_ALLOW_LEFTHOOK_HOOKS_PATH=1 lefthook install --force") is None


def test_lefthook_framework_path_comparison_ignores_case(monkeypatch):
    monkeypatch.setattr(os.path, "normcase", str.lower)
    monkeypatch.setattr(agent_guard, "_run", fake_run(hooks_path_stub(FRAMEWORK_HOOKS.upper())))
    reason = dispatch("lefthook install --force")
    assert reason and "lefthook-hooks-path" in reason
