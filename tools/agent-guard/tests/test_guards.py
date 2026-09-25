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

"""Engine + bundled-guard tests. The relocated skill-owned guards (mention,
mark-ready, security-language) are tested in test_skill_guards.py through the
same discovery path a real adopter uses."""

import json

import pytest

import agent_guard


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for name in (
        "MAGPIE_GUARD_OFF",
        "MAGPIE_GUARD_DIRS",
        "MAGPIE_ALLOW_COAUTHOR",
        "MAGPIE_ALLOW_EMPTY_PUSH",
        "MAGPIE_ALLOW_NO_VERIFY",
        "MAGPIE_ALLOW_MENTIONS",
        "MAGPIE_ALLOW_MARK_READY",
        "MAGPIE_ALLOW_SECURITY_LANG",
    ):
        monkeypatch.delenv(name, raising=False)


def fake_run(handler):
    """Install a stub for agent_guard._run that dispatches on the argv."""

    def _stub(args, cwd=None):
        return handler(args)

    return _stub


# --------------------------------------------------------------------------- #
# find_mentions / strip_code (shared helper, stays in the engine)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hello @alice and @bob-1", ["alice", "bob-1"]),
        ("email announce@apache.org is not a mention", []),
        ("team ping @apache/airflow-committers", ["apache/airflow-committers"]),
        ("code span `@alice` does not notify", []),
        ("fenced\n```\n@alice\n```\nblock", []),
        ("user@host.com and plain text", []),
        ("`backtick login` mention of @carol", ["carol"]),
    ],
)
def test_find_mentions(text, expected):
    assert agent_guard.find_mentions(text) == expected


# --------------------------------------------------------------------------- #
# commit-trailer guard (bundled)
# --------------------------------------------------------------------------- #


def test_commit_coauthor_denied():
    reason = dispatch('git commit -m "fix\n\nCo-Authored-By: Someone <x@y.z>"')
    assert reason and "Co-Authored-By" in reason


def test_commit_coauthor_case_insensitive():
    assert dispatch('git commit -m "x\n\nco-authored-by: a"') is not None


def test_commit_generated_by_allowed():
    assert dispatch('git commit -m "fix\n\nGenerated-by: Claude Code"') is None


def test_commit_coauthor_override():
    assert dispatch('MAGPIE_ALLOW_COAUTHOR=1 git commit -m "x\nCo-Authored-By: a"') is None


@pytest.mark.parametrize(
    "command",
    [
        'git -C /tmp commit -m "x\n\nCo-Authored-By: a"',
        'git -c core.editor=true commit -m "x\n\nCo-Authored-By: a"',
        'git --no-pager commit -m "x\n\nCo-Authored-By: a"',
    ],
)
def test_commit_coauthor_denied_past_a_global_flag(command):
    # A global `git` option before the subcommand must not shift it past the
    # guard's fixed check, the same bypass `gh_subcommand` already guards
    # against for `gh --repo ... pr create`.
    reason = dispatch(command)
    assert reason and "Co-Authored-By" in reason


# --------------------------------------------------------------------------- #
# commit-trailer guard: the configured commit-attribution convention
# --------------------------------------------------------------------------- #

COAUTHOR_COMMIT = 'git commit -m "x\n\nCo-Authored-By: a <x@y.z>"'


def _attribution_repo(tmp_path, project=None, local=None):
    """A bare-bones repo with optional project / contributor attribution files.

    ``project`` / ``local`` are the raw TOML text of each layer's file.
    """
    (tmp_path / ".git").mkdir(parents=True)
    for layer, text in ((".apache-magpie-overrides", project), (".apache-magpie-local", local)):
        if text is not None:
            (tmp_path / layer).mkdir()
            (tmp_path / layer / "commit-attribution.toml").write_text(text)
    return tmp_path


@pytest.mark.parametrize(
    "project, local, allowed",
    [
        # Nothing configured: the default, generated-by, keeps the block.
        (None, None, False),
        # The project chose co-authored-by.
        ('convention = "co-authored-by"\n', None, True),
        # The project's choice wins over the contributor's.
        ('convention = "generated-by"\n', 'convention = "co-authored-by"\n', False),
        ('convention = "none"\n', 'convention = "co-authored-by"\n', False),
        # The project leaves it open, explicitly or by not deciding.
        ('convention = "contributor-choice"\n', 'convention = "co-authored-by"\n', True),
        (None, 'convention = "co-authored-by"\n', True),
        ("# no convention key yet\n", 'convention = "co-authored-by"\n', True),
        ('convention = "contributor-choice"\n', None, False),
        ('convention = "contributor-choice"\n', 'convention = "assisted-by"\n', False),
        # Case and whitespace in the value are not a way around the choice.
        ('convention = " Co-Authored-By "\n', None, True),
    ],
)
def test_commit_coauthor_follows_the_resolved_convention(tmp_path, project, local, allowed):
    repo = _attribution_repo(tmp_path, project, local)
    reason = dispatch(COAUTHOR_COMMIT, cwd=str(repo))
    assert (reason is None) is allowed, reason


@pytest.mark.parametrize(
    "project, local",
    [
        # Unparsable project file: fail closed, even though the contributor chose.
        ("convention = [unclosed\n", 'convention = "co-authored-by"\n'),
        # Unknown project value: the default, not the contributor's choice.
        ('convention = "anything-goes"\n', 'convention = "co-authored-by"\n'),
        # contributor-choice is a project-only value.
        (None, 'convention = "contributor-choice"\n'),
        # A non-string value.
        ("convention = 1\n", None),
    ],
)
def test_commit_attribution_fails_closed(tmp_path, project, local):
    repo = _attribution_repo(tmp_path, project, local)
    reason = dispatch(COAUTHOR_COMMIT, cwd=str(repo))
    assert reason and "Co-Authored-By" in reason and "'generated-by'" in reason


def test_commit_attribution_found_from_a_subdirectory(tmp_path):
    repo = _attribution_repo(tmp_path, 'convention = "co-authored-by"\n')
    sub = repo / "src" / "pkg"
    sub.mkdir(parents=True)
    assert dispatch(COAUTHOR_COMMIT, cwd=str(sub)) is None


def test_commit_attribution_follows_git_dash_c(tmp_path):
    # `git -C <repo> commit` commits to <repo>, so its convention is the one
    # that applies, not the one where the command was typed.
    repo = _attribution_repo(tmp_path / "repo", 'convention = "co-authored-by"\n')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".git").mkdir()
    command = f'git -C {repo} commit -m "x\n\nCo-Authored-By: a <x@y.z>"'
    assert dispatch(command, cwd=str(elsewhere)) is None
    assert dispatch(COAUTHOR_COMMIT, cwd=str(elsewhere)) is not None


def test_commit_attribution_trailer_flag_is_seen(tmp_path):
    # The trailer added the way the convention docs prescribe is still caught.
    repo = _attribution_repo(tmp_path, 'convention = "generated-by"\n')
    command = "git commit -F msg.txt --trailer 'Co-authored-by: a <x@y.z>'"
    assert dispatch(command, cwd=str(repo)) is not None


@pytest.mark.parametrize(
    "flag",
    ["-F {path}", "--file {path}", "--file={path}"],
)
def test_commit_coauthor_in_message_file_denied(tmp_path, flag):
    # AGENTS.md sends commit bodies through a file; the trailer inside it is
    # what the commit will say, so the guard has to read it.
    repo = _attribution_repo(tmp_path)
    msg = repo / "msg.txt"
    msg.write_text("subject\n\nbody\n\nCo-Authored-By: a <x@y.z>\n")
    reason = dispatch(f"git commit {flag.format(path=msg)}", cwd=str(repo))
    assert reason and "Co-Authored-By" in reason


def test_commit_message_file_relative_to_git_dash_c(tmp_path):
    repo = _attribution_repo(tmp_path / "repo")
    (repo / "msg.txt").write_text("subject\n\nCo-authored-by: a <x@y.z>\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    reason = dispatch(f"git -C {repo} commit -F msg.txt", cwd=str(elsewhere))
    assert reason and "Co-Authored-By" in reason


def test_commit_message_file_follows_the_convention(tmp_path):
    repo = _attribution_repo(tmp_path, 'convention = "co-authored-by"\n')
    (repo / "msg.txt").write_text("subject\n\nCo-Authored-By: a <x@y.z>\n")
    assert dispatch("git commit -F msg.txt", cwd=str(repo)) is None


@pytest.mark.parametrize(
    "command",
    [
        "git commit -F msg.txt",  # clean message file
        "git commit -F missing.txt",  # git would fail on it itself
        "git commit -F -",  # stdin: nothing to read ahead of time
    ],
)
def test_commit_message_file_without_coauthor_allowed(tmp_path, command):
    repo = _attribution_repo(tmp_path)
    (repo / "msg.txt").write_text("subject\n\nGenerated-by: Claude Code\n")
    assert dispatch(command, cwd=str(repo)) is None


def test_resolve_commit_attribution_outside_a_repo():
    assert agent_guard.resolve_commit_attribution(None) == "generated-by"


# --------------------------------------------------------------------------- #
# empty-rebase guard (bundled)
# --------------------------------------------------------------------------- #


def _push_handler(count):
    def handler(args):
        if args[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return "origin/main"
        if args[:2] == ["git", "merge-base"]:
            return "base1234"
        if args[:3] == ["git", "rev-list", "--count"]:
            return count
        if args[:3] == ["git", "rev-parse", "--verify"]:
            return "sha"
        return None

    return handler


def test_empty_rebase_denied(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    reason = dispatch("git push --force-with-lease origin mybranch:mybranch")
    assert reason and "0 commits" in reason


def test_nonempty_force_push_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("3")))
    assert dispatch("git push --force-with-lease origin mybranch") is None


def test_non_force_push_allowed(monkeypatch):
    def boom(args):
        raise AssertionError("non-force push is not guarded")

    monkeypatch.setattr(agent_guard, "_run", fake_run(boom))
    assert dispatch("git push origin mybranch") is None


def test_empty_rebase_failopen_no_base(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(lambda a: None))
    assert dispatch("git push --force origin mybranch") is None


def test_empty_rebase_override(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    assert dispatch("MAGPIE_ALLOW_EMPTY_PUSH=1 git push --force origin b:b") is None


def test_empty_rebase_denied_past_a_global_flag(monkeypatch):
    # Same global-flag bypass as test_commit_coauthor_denied_past_a_global_flag,
    # for the other bundled guard: `git -C <dir> push --force ...` must still
    # resolve the subcommand as `push`, and the src ref must still be read
    # relative to the subcommand rather than a fixed argv[2:] slice.
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    reason = dispatch("git -C /tmp push --force-with-lease origin mybranch:mybranch")
    assert reason and "0 commits" in reason


# --------------------------------------------------------------------------- #
# bundled example contributed guard (guards.d/no_verify_commit.py)
# --------------------------------------------------------------------------- #


def test_bundled_no_verify_guard_discovered():
    reason = dispatch('git commit -m "x" --no-verify')
    assert reason and "no-verify" in reason


def test_no_verify_override():
    assert dispatch('MAGPIE_ALLOW_NO_VERIFY=1 git commit -n -m "x"') is None


def test_plain_commit_not_blocked_by_no_verify_guard():
    assert dispatch('git commit -m "ordinary commit"') is None


def test_no_verify_guard_denied_past_a_global_flag():
    # The guard's own ctx.argv[:2] check had the same bypass as the two
    # bundled guards; command_kinds' TRIGGERS = ["git:commit"] pre-filter
    # had it too, so a global flag used to skip calling guard() at all.
    reason = dispatch('git -C /tmp commit -m "x" --no-verify')
    assert reason and "no-verify" in reason


# --------------------------------------------------------------------------- #
# contributed-guard discovery
# --------------------------------------------------------------------------- #


def test_contributed_guard_from_env_dir(monkeypatch, tmp_path):
    gdir = tmp_path / "guards.d"
    gdir.mkdir()
    (gdir / "block_merge_admin.py").write_text(
        'TRIGGERS = ["gh"]\n'
        "def guard(ctx):\n"
        "    sub = ctx.gh_subcommand()\n"
        "    if sub == ('pr', 'merge') and any(t in ('--admin',) for t in ctx.argv):\n"
        "        if ctx.override('MAGPIE_ALLOW_ADMIN_MERGE'):\n"
        "            return None\n"
        "        return 'contributed[admin-merge]: refusing gh pr merge --admin'\n"
        "    return None\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MAGPIE_GUARD_DIRS", str(gdir))
    assert dispatch("gh pr merge 5 --admin") is not None
    assert dispatch("MAGPIE_ALLOW_ADMIN_MERGE=1 gh pr merge 5 --admin") is None
    assert dispatch("gh pr view 5 --json title") is None


def test_broken_contributed_guard_fails_open(monkeypatch, tmp_path):
    gdir = tmp_path / "guards.d"
    gdir.mkdir()
    (gdir / "broken.py").write_text("this is not valid python !!!", encoding="utf-8")
    monkeypatch.setenv("MAGPIE_GUARD_DIRS", str(gdir))
    assert dispatch("gh pr view 5") is None


# --------------------------------------------------------------------------- #
# dispatch / fast path / compound commands
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "git status",
        "git log --oneline -5",
        "grep -r foo .",
        "gh pr view 5 --json title",
        "",
    ],
)
def test_fast_path_allows(command):
    assert dispatch(command) is None


def test_compound_command_guarded():
    # The commit-trailer guard (bundled) fires on the second segment.
    assert dispatch('cd /tmp && git commit -m "x\nCo-Authored-By: a"') is not None


def test_compound_command_other_segment_not_denied():
    # The phrase lives in an unrelated earlier segment, not in the commit's
    # own message, so the commit segment must not inherit it.
    command = 'echo "note: never add a Co-Authored-By: trailer" && git commit -m "clean fix"'
    assert dispatch(command) is None


def test_malformed_command_allows():
    assert dispatch('gh pr comment 5 --body "oops') is None


def test_global_off(monkeypatch):
    assert dispatch('MAGPIE_GUARD_OFF=1 git commit -m "x\nCo-Authored-By: a"') is None


# --------------------------------------------------------------------------- #
# main() stdin contract
# --------------------------------------------------------------------------- #


def test_main_emits_deny(monkeypatch, capsys):
    event = {
        "tool_name": "Bash",
        "tool_input": {"command": 'git commit -m "x\nCo-Authored-By: a"'},
    }
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(event)))
    rc = agent_guard.main()
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_main_allows_non_bash(monkeypatch, capsys):
    event = {"tool_name": "Read", "tool_input": {"file_path": "x"}}
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(event)))
    assert agent_guard.main() == 0
    assert capsys.readouterr().out == ""


def test_main_allows_malformed_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", _Stdin("not json"))
    assert agent_guard.main() == 0
    assert capsys.readouterr().out == ""


# Convenience wrapper so each test reads cleanly.
def dispatch(command, cwd=None):
    return agent_guard.dispatch(command, cwd=cwd)


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


# Regression: a path-qualified command head (e.g. the documented
# ``--exec /usr/bin/git`` wrapper install) must be guarded identically to the
# bare name. Segment normalises argv[0] to its basename, so the guard cannot be
# bypassed by invoking the real binary by absolute or relative path.
def test_abs_path_git_commit_coauthor_denied():
    assert dispatch('/usr/bin/git commit -m "x\n\nCo-Authored-By: a <x@y.z>"') is not None


def test_relative_path_git_commit_coauthor_denied():
    assert dispatch('./git commit -m "x\n\nCo-Authored-By: a <x@y.z>"') is not None


def test_abs_path_plain_commit_still_allowed():
    assert dispatch('/usr/bin/git commit -m "ordinary commit"') is None


# ---------------------------------------------------------------------------
# gh argv parsing
#
# ``gh`` parses flags interspersed, so a flag may legitimately precede the
# command group. A parser that only drops tokens starting with ``-`` keeps
# their values, turning ``gh --repo apache/airflow pr create`` into
# ``("apache/airflow", "pr")`` — every guard keyed on ``("pr", "create")``
# then silently stops running.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv, expected",
    [
        # Conventional ordering.
        (["gh", "pr", "create", "--title", "x"], ("pr", "create")),
        (["gh", "pr", "edit", "123", "--repo", "o/r"], ("pr", "edit")),
        (["gh", "issue", "comment", "5", "--body", "hi"], ("issue", "comment")),
        # Flag before the command group — the regression.
        (["gh", "--repo", "o/r", "pr", "create", "--title", "x"], ("pr", "create")),
        (["gh", "-R", "o/r", "pr", "create", "--title", "x"], ("pr", "create")),
        (["gh", "--repo", "o/r", "pr", "edit", "1"], ("pr", "edit")),
        (["gh", "--repo", "o/r", "issue", "comment", "5"], ("issue", "comment")),
        (["gh", "-R", "o/r", "pr", "comment", "7"], ("pr", "comment")),
        # ``--flag=value`` keeps its value in one token.
        (["gh", "--repo=o/r", "pr", "create"], ("pr", "create")),
        # A repo whose name collides with a command group must not win.
        (["gh", "--repo", "acme/pr", "pr", "create"], ("pr", "create")),
        (["gh", "--repo", "acme/issue", "issue", "edit", "3"], ("issue", "edit")),
        # Several pre-command flags.
        (["gh", "-R", "o/r", "--hostname", "git.example", "pr", "create"], ("pr", "create")),
        # Non-gh and malformed input.
        (["git", "commit", "-m", "x"], None),
        (["gh"], None),
        (["gh", "pr"], None),
        ([], None),
    ],
)
def test_gh_subcommand_consumes_flag_values(argv, expected):
    assert agent_guard.gh_subcommand(argv) == expected


# ---------------------------------------------------------------------------
# git_subcommand_index: the same fail-open shape as gh_subcommand above, for
# the two BUILTIN_GUARDS (guard_commit_trailer, guard_empty_rebase), which
# used to anchor on a fixed argv[:2] slice.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv, expected_index",
    [
        (["git", "commit", "-m", "x"], 1),
        (["git", "push", "origin", "b"], 1),
        # A global flag before the subcommand: the regression.
        (["git", "-C", "/tmp", "commit", "-m", "x"], 3),
        (["git", "-c", "core.editor=true", "commit", "-m", "x"], 3),
        (["git", "--no-pager", "commit", "-m", "x"], 2),
        (["git", "--work-tree", "/tmp", "push"], 3),
        # Several pre-subcommand flags.
        (["git", "-C", "/tmp", "-c", "a=b", "commit"], 5),
        # No subcommand at all: only global flags, or nothing after `git`.
        (["git", "-C", "/tmp"], None),
        (["git"], None),
        # Non-git and empty input.
        (["gh", "pr", "create"], None),
        ([], None),
    ],
)
def test_git_subcommand_index_consumes_flag_values(argv, expected_index):
    assert agent_guard.git_subcommand_index(argv) == expected_index
