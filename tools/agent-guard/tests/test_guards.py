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
        "MAGPIE_ALLOW_VETTED_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def fake_run(handler):
    """Install a stub for agent_guard._run that dispatches on the argv."""

    def _stub(args, cwd=None):
        return handler(args)

    return _stub


# --------------------------------------------------------------------------- #
# guarded_head (shared helper, stays in the engine)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "head, expected",
    [
        ("lefthook", "lefthook"),
        ("./node_modules/.bin/lefthook", "lefthook"),
        (r"node_modules\.bin\lefthook", "lefthook"),
        (r"C:\tools\lefthook.exe", "lefthook"),
        ("lefthook.exe", "lefthook"),
        ("/usr/bin/gh", "gh"),
        ("curl", None),
    ],
)
def test_guarded_head_recognizes_paths_from_every_platform(head, expected):
    assert agent_guard.guarded_head([head, "install"]) == expected


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


def test_commit_attribution_reads_the_git_dir_home_of_an_unadopted_repo(tmp_path):
    """Not adopted: the contributor's file lives inside `.git/`, not the tree."""
    (tmp_path / ".git" / "apache-magpie").mkdir(parents=True)
    (tmp_path / ".git" / "apache-magpie" / "commit-attribution.toml").write_text(
        'convention = "co-authored-by"\n'
    )
    assert dispatch(COAUTHOR_COMMIT, cwd=str(tmp_path)) is None


def test_commit_attribution_git_dir_home_wins_over_a_legacy_local_dir(tmp_path):
    repo = _attribution_repo(tmp_path, None, 'convention = "co-authored-by"\n')
    (repo / ".git" / "apache-magpie").mkdir()
    (repo / ".git" / "apache-magpie" / "commit-attribution.toml").write_text('convention = "generated-by"\n')
    assert dispatch(COAUTHOR_COMMIT, cwd=str(repo)) is not None


def test_commit_attribution_from_a_linked_worktree_reads_the_shared_home(tmp_path):
    main = tmp_path / "main"
    wt_gitdir = main / ".git" / "worktrees" / "wt"
    wt_gitdir.mkdir(parents=True)
    (wt_gitdir / "commondir").write_text("../..\n")
    (main / ".git" / "apache-magpie").mkdir()
    (main / ".git" / "apache-magpie" / "commit-attribution.toml").write_text(
        'convention = "co-authored-by"\n'
    )
    wt = tmp_path / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {wt_gitdir}\n")
    assert dispatch(COAUTHOR_COMMIT, cwd=str(wt)) is None


def test_commit_attribution_in_an_adopted_repo_ignores_the_git_dir_home(tmp_path):
    (tmp_path / ".git" / "apache-magpie").mkdir(parents=True)
    (tmp_path / ".git" / "apache-magpie" / "commit-attribution.toml").write_text(
        'convention = "co-authored-by"\n'
    )
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")
    assert dispatch(COAUTHOR_COMMIT, cwd=str(tmp_path)) is not None
    (tmp_path / ".apache-magpie-local").mkdir()
    (tmp_path / ".apache-magpie-local" / "commit-attribution.toml").write_text(
        'convention = "co-authored-by"\n'
    )
    assert dispatch(COAUTHOR_COMMIT, cwd=str(tmp_path)) is None


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


def test_empty_rebase_denied_plus_refspec(monkeypatch):
    # `+refspec` is git's other force spelling (git-push(1) documents it as
    # equivalent to --force for that refspec); without it the guard is
    # bypassed by `git push origin +branch` and `git push origin +b:d`.
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    reason = dispatch("git push origin +mybranch:mybranch")
    assert reason and "0 commits" in reason


def test_empty_rebase_denied_plus_refspec_short(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    reason = dispatch("git push origin +mybranch")
    assert reason and "0 commits" in reason


def test_plus_refspec_still_guarded_behind_a_global_flag(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("0")))
    reason = dispatch("git -C /tmp push origin +mybranch:mybranch")
    assert reason and "0 commits" in reason


def test_plus_refspec_nonempty_push_allowed(monkeypatch):
    monkeypatch.setattr(agent_guard, "_run", fake_run(_push_handler("3")))
    assert dispatch("git push origin +mybranch:mybranch") is None


def test_plain_refspec_push_not_guarded_as_force(monkeypatch):
    def boom(args):
        raise AssertionError("non-force push is not guarded")

    monkeypatch.setattr(agent_guard, "_run", fake_run(boom))
    assert dispatch("git push origin mybranch:mybranch") is None


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


def test_gh_group_trigger_fires_past_a_global_flag(monkeypatch, tmp_path):
    gdir = tmp_path / "guards.d"
    gdir.mkdir()
    (gdir / "pr_only.py").write_text(
        'TRIGGERS = ["gh:pr"]\ndef guard(ctx):\n    return "contributed[pr-only]: denied"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MAGPIE_GUARD_DIRS", str(gdir))
    assert dispatch("gh pr edit 5 --add-label x") is not None
    assert dispatch("gh -R o/r pr edit 5 --add-label x") is not None
    assert dispatch("gh -R o/r issue edit 5 --add-label x") is None


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


_TRAILER_COMMIT = 'git commit -m "x\nCo-Authored-By: a"'


@pytest.mark.parametrize(
    "command",
    [
        # A newline ends a command, as `;` does.
        f"echo hi\n{_TRAILER_COMMIT}",
        # Control operators split a command with or without spaces around them.
        f"echo hi;{_TRAILER_COMMIT}",
        f"true&&{_TRAILER_COMMIT}",
        f"false||{_TRAILER_COMMIT}",
        f"echo hi|{_TRAILER_COMMIT}",
        f"sleep 1&{_TRAILER_COMMIT}",
        f"echo hi|&{_TRAILER_COMMIT}",
        # Subshells, groups, reserved words and comments.
        f"({_TRAILER_COMMIT})",
        f"{{ {_TRAILER_COMMIT}; }}",
        f"if true; then {_TRAILER_COMMIT}; fi",
        f"case x in x) {_TRAILER_COMMIT};; esac",
        f"! {_TRAILER_COMMIT}",
        f"echo hi # it's a note\n{_TRAILER_COMMIT}",
        f"f() {{ {_TRAILER_COMMIT}; }}; f",
        # A continued line joins the next: `x#'` is a word, not a comment.
        f"echo x\\\n#'\ncat <<EOF\n'\n{_TRAILER_COMMIT}\nEOF",
        # Substitutions run their command.
        f"echo $({_TRAILER_COMMIT})",
        f'echo "$({_TRAILER_COMMIT})"',
        f"echo `{_TRAILER_COMMIT}`",
        f"cat <({_TRAILER_COMMIT})",
        f"echo ${{x:-$({_TRAILER_COMMIT})}}",
        f"echo $(( $({_TRAILER_COMMIT}) ))",
        # A `case` pattern's `)` inside a substitution or subshell.
        f"echo $(case x in x) echo;; esac; {_TRAILER_COMMIT})",
        f"(case x in x) true;; esac; {_TRAILER_COMMIT})",
        f'echo "$(case x in x) echo;; esac; {_TRAILER_COMMIT})"',
        # A quoted or escaped `>` is no redirection: `&` / `|` still split.
        f"echo '>'&{_TRAILER_COMMIT}",
        f"echo \\>|{_TRAILER_COMMIT}",
        f'echo ">"&{_TRAILER_COMMIT}',
        # A function body behind `function name`.
        f"function f {{ {_TRAILER_COMMIT}; }}; f",
        f"function f() {{ {_TRAILER_COMMIT}; }}; f",
        # `time` and `coproc` keep command position for a group.
        f"time {{ {_TRAILER_COMMIT}; }}",
        f"time -p {{ {_TRAILER_COMMIT}; }}",
        f"! time -p -- {{ {_TRAILER_COMMIT}; }}",
        f"coproc {{ {_TRAILER_COMMIT}; }}",
        f"coproc c {{ {_TRAILER_COMMIT}; }}",
        # ANSI-C escapes decode as bash decodes them.
        """$'\\x67it' commit -m "x\nCo-Authored-By: a\"""",
        """$'\\147it' commit -m "x\nCo-Authored-By: a\"""",
        """$'\\u0067it' commit -m "x\nCo-Authored-By: a\"""",
        # A brace is a group only in command position; elsewhere it is a word
        # and does not move a command boundary.
        f"echo {{ x\n{_TRAILER_COMMIT}\n}}",
        f"echo x}} ; {_TRAILER_COMMIT}",
        'git commit -m x } -m "Co-Authored-By: a"',
        'git commit -m x { -m "Co-Authored-By: a"',
        # A NUL from a `$'…'` escape truncates the word in bash.
        """$'git\\0x' commit -m "x\nCo-Authored-By: a\"""",
        """$'git\\x00x' commit -m "x\nCo-Authored-By: a\"""",
        """$'git\\u0000x' commit -m "x\nCo-Authored-By: a\"""",
        # `case` behind any prefix inside a substitution.
        f'echo "$(time case x in x) echo;; esac; {_TRAILER_COMMIT})"',
        f'echo "$(time -p case x in x) echo;; esac; {_TRAILER_COMMIT})"',
        # A heredoc fed to a shell runs its body.
        f"bash <<'EOF'\n{_TRAILER_COMMIT}\nEOF",
        # An unquoted heredoc expands its substitutions.
        f"cat <<EOF > notes.md\n$({_TRAILER_COMMIT})\nEOF",
    ],
)
def test_every_command_of_a_line_is_checked(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "echo 'a;git push' \"b && gh pr merge 5\"",
        "ls 2>&1 | grep x",
        "make >/dev/null 2>&1 &",
        "echo hi &>/dev/null",
        "echo hi >| out.txt",
        "cat <<< 'git notes'",
        "cat <<'EOF' > notes.md\ngit commit -m x\nCo-Authored-By: a\nEOF",
        "echo hi # git commit -m x Co-Authored-By: a",
        "for f in a b; do echo $f; done",
    ],
)
def test_quoted_and_redirection_text_is_not_a_command(command):
    assert dispatch(command) is None


def test_heredoc_body_stays_on_the_commit_it_feeds():
    command = "git commit -F - <<'EOF'\nfix\n\nCo-Authored-By: a\nEOF"
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        'gh pr comment 5 --body "oops',
        "git commit -m 'it''s",
        "cd /tmp && /usr/bin/git push --force \\",
        # Inside a shell `-c` string.
        """bash -c "git commit -m 'oops" """,
        # Quoting and escapes inside the word: bash still runs git / gh.
        "g'i't push --force ; echo 'oops",
        '"g"h pr merge 5 ; echo \'oops',
        "g\\it push --force ; echo 'oops",
        "$'gh' pr merge 5 ; echo 'oops",
        "/usr/bin/gi''t push --force ; echo 'oops",
        "g\\\nit push --force ; echo 'oops",
        "$'g'h pr merge 5 ; echo 'oops",
        '$"g"h pr merge 5 ; echo \'oops',
        # Expansions that may be empty: the guards cannot see the word.
        "g$()it push --force ; echo 'oops",
        "g${x:-}it push --force ; echo 'oops",
        "g``it push --force ; echo 'oops",
        "g$@it push --force ; echo 'oops",
        "$CMD push --force ; echo 'oops",
        # Globs and brace expansion can resolve to git / gh.
        "/usr/bin/gi? push --force ; echo 'oops",
        "/usr/bin/g*t push --force ; echo 'oops",
        "/usr/bin/g[i]t push --force ; echo 'oops",
        "/usr/bin/g{i,}t push --force ; echo 'oops",
    ],
)
def test_untokenisable_command_naming_a_guarded_head_is_refused(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


@pytest.mark.parametrize(
    "command",
    [
        'echo "oops',
        "grep -r 'digit",  # `git` only inside a longer word
        "cat .gitignore 'x",
        "ls github.com/'x",
    ],
)
def test_untokenisable_command_without_a_guarded_head_allows(command):
    assert dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "cat <<'EOF' > notes.md\nThe user's git configuration\nEOF",
        'cat <<-"EOF" > notes.md\n\tThe user\'s gh login\n\tEOF\necho done',
    ],
)
def test_heredoc_body_apostrophe_is_not_quoting(command):
    assert dispatch(command) is None


def test_heredoc_stripped_line_is_still_checked():
    command = "cat <<'EOF' > notes.md\nIt's the user's notes\nEOF\ngit commit -m 'oops"
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


def test_time_keyword_assignments_are_seen_through():
    assert dispatch('time FOO=1 git commit -m "x\nCo-Authored-By: a"') is not None


@pytest.mark.parametrize(
    "command",
    [
        """zsh -oSH_WORD_SPLIT -c 'git commit -m "x\nCo-Authored-By: a"'""",
        """bash -o pipefail -c 'git commit -m "x\nCo-Authored-By: a"'""",
    ],
)
def test_shell_option_values_do_not_hide_the_c_string(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        """bash -oc pipefail 'git commit -m "x\nCo-Authored-By: a"'""",
        """sh -ec 'git commit -m "x\nCo-Authored-By: a"'""",
    ],
)
def test_bash_option_clusters_do_not_hide_the_c_string(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\nit's the user's script\ngit push --force\nEOF\necho 'oops",
        "python3 - <<'EOF'\nit's the user's script, run git\nEOF\necho 'oops",
        "cat <<'EOF' | bash\nit's the user's script\ngit push --force\nEOF\necho 'oops",
        "cat <<'EOF' \\\n| bash\nit's the user's script\ngit push --force\nEOF\necho 'oops",
        "cat <<'EOF'\nthe user's notes\ngit history",
    ],
)
def test_heredoc_that_runs_or_never_closes_is_not_stripped(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


@pytest.mark.parametrize(
    "command",
    [
        # `<<EOF` inside a comment or quotes opens no heredoc: bash runs the
        # next line as a command, and the guards check it.
        f"cat /dev/null # <<EOF it's\n{_TRAILER_COMMIT}\nEOF",
        f"cat /dev/null '<<EOF' # it's\n{_TRAILER_COMMIT}\nEOF",
        f"cat /dev/null \"<<EOF\" $'it\\'s'\n{_TRAILER_COMMIT}\nEOF",
        # A quote opened on an earlier line is still open.
        f"echo 'x\ncat <<EOF' # it's\n{_TRAILER_COMMIT}\nEOF",
    ],
)
def test_heredoc_operator_in_a_comment_or_quotes_is_not_a_heredoc(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        # bash joins `x\` and `#'` into the word `x#'`: the `#` is no comment,
        # and the `'` opens a quote that swallows `cat <<EOF` and closes on
        # the `'` line, so bash runs the line after it as a command. The last
        # line leaves a quote open, so the command reaches heredoc stripping.
        "echo x\\\n#'\ncat <<EOF\n'\ngit push --force\nEOF\necho 'oops",
        "echo x\\\n#'\ncat <<'EOF'\n'\ngit push --force\nEOF\necho 'oops",
        # A continued line that opens no heredoc, ahead of one that does: kept
        # whole too, since this reader does not follow the joined line.
        "echo x \\\n  y\ncat <<'EOF'\ngit push --force\nEOF\necho 'oops",
    ],
)
def test_continued_line_anywhere_keeps_the_command_whole(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


def test_backslash_inside_a_heredoc_body_is_data():
    assert dispatch("cat <<'EOF' > notes.md\nthe user's git notes \\\nEOF") is None


@pytest.mark.parametrize(
    "command",
    [
        "cat <<EOF\nit's $(git push --force)\nEOF",
        "cat <<EOF > notes.md\nit's `gh pr merge 5`\nEOF",
    ],
)
def test_unquoted_heredoc_body_substitution_is_not_stripped(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


def test_quoted_heredoc_body_substitution_is_data():
    assert dispatch("cat <<'EOF' > notes.md\nit's $(git log) in the docs\nEOF") is None


@pytest.mark.parametrize(
    "command",
    [
        # The guards cannot see what an expansion or glob in the command name
        # resolves to, so such a command is refused even when it tokenises.
        "$CMD push --force",
        '"$CMD" push --force',
        "${CMD} push --force",
        "CMD=git; $CMD push --force",
        "$(echo git) push --force",
        "`echo git` push --force",
        "/usr/bin/gi? push --force",
        "/usr/bin/g*t push --force",
        "/usr/bin/g[i]t push --force",
        "/usr/bin/g{i,}t push --force",
        "env $CMD push --force",
        "command $CMD push --force",
        # zsh expands `=cmd` to the command's path and `(…)` as a glob group.
        "=git push --force",
        "/usr/bin/g(i)t push --force",
        "/usr/bin/gi<-> push --force",
        "/usr/bin/g^x push --force",
        "/usr/bin/git~x push --force",
        # The `uv` rule is keyed on the basename, which does not make the
        # head literal: the shell splits `${CMD}` into words.
        'CMD="git push --force"; ${CMD}/uv',
        "${CMD}/uvx",
        "$(echo git)/uv",
    ],
)
def test_expanded_command_name_is_refused(command):
    reason = dispatch(command)
    # `g(i)t` cannot be read as bash at all, so it is refused as unparsable
    assert reason and ("agent-guard[expansion]" in reason or "agent-guard[parse]" in reason)


@pytest.mark.parametrize(
    "command",
    [
        "[ -f README.md ]",
        "[[ -f README.md ]]",
        "echo $HOME",
        "ls *.md",
        "X=$(pwd) ls",
        "git log --format='%h {x}'",
        # Literal names: paths, `~/`, and the characters real tools use.
        "~/.local/bin/uv-tool --version",
        "./scripts/build.sh",
        "/usr/bin/git status",
        "g++ --version",
        "python3.12 -V",
        "docker-compose ps",
    ],
)
def test_expansion_outside_the_command_name_allows(command):
    assert dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        # bash allows redirections before the command name; the command after
        # them is the one that runs.
        f">/dev/null {_TRAILER_COMMIT}",
        f"> /dev/null {_TRAILER_COMMIT}",
        f"2>&1 {_TRAILER_COMMIT}",
        f"</dev/null {_TRAILER_COMMIT}",
        f"&>>log {_TRAILER_COMMIT}",
        f"X=1 2>/dev/null {_TRAILER_COMMIT}",
        f"{{fd}}>log {_TRAILER_COMMIT}",
        f"nohup >log env {_TRAILER_COMMIT}",
        # A detached target after `>&` / `N>&` / `<&` is the next word.
        f">& /dev/null {_TRAILER_COMMIT}",
        f"2>& /dev/null {_TRAILER_COMMIT}",
        f"<& 0 {_TRAILER_COMMIT}",
        f"&> /dev/null {_TRAILER_COMMIT}",
        f">| /dev/null {_TRAILER_COMMIT}",
    ],
)
def test_command_after_leading_redirections_is_checked(command):
    reason = dispatch(command)
    assert reason and "Co-Authored-By" in reason


@pytest.mark.parametrize(
    "command",
    [
        # bash removes a redirection wherever it stands, so one between a
        # wrapper's options is not the command.
        f"env 2>/dev/null -i {_TRAILER_COMMIT}",
        f"env -i 2>/dev/null -0 {_TRAILER_COMMIT}",
        f"command -p 2>/dev/null -- {_TRAILER_COMMIT}",
        f"exec -c 2>/dev/null -a name {_TRAILER_COMMIT}",
        f"time -p 2>/dev/null {_TRAILER_COMMIT}",
        f"nohup 2>/dev/null -- {_TRAILER_COMMIT}",
    ],
)
def test_redirections_between_wrapper_options_are_skipped(command):
    reason = dispatch(command)
    assert reason and "Co-Authored-By" in reason


@pytest.mark.parametrize(
    "command",
    [
        # Where an option takes a value, a redirection-shaped word is either a
        # redirection before the value or, quoted, the value itself; tokens
        # cannot tell which, and reading the wrong one shifts the command.
        "env -u 2>/dev/null NAME git push --force",
        "env -u '>x' git push --force",
        "env --unset > /dev/null NAME git push --force",
        "env -C 2>/dev/null /tmp git push --force",
        "exec -a 2>/dev/null name git push --force",
        "exec -a '>' x git push --force",
        "time -o 2>/dev/null out.txt git push --force",
        "time --output '>x' git push --force",
    ],
)
def test_a_redirection_shaped_option_value_is_refused(command):
    reason = dispatch(command)
    assert reason and "agent-guard[wrapper]" in reason


def test_a_quoted_redirection_shaped_value_does_not_hide_the_command():
    """`env -u '>x' git …` unsets `>x` and runs git: never read `git` as the value."""
    assert dispatch("env -u '>x' git status") is not None


def test_wrappers_and_redirections_past_the_limit_are_refused():
    command = "nohup >log " * 80 + _TRAILER_COMMIT
    reason = dispatch(command)
    assert reason and "agent-guard[wrapper]" in reason


@pytest.mark.parametrize("command", ["exec 3>&1", "2>/dev/null git status", ">out.txt echo hi"])
def test_leading_redirections_on_a_clean_command_allow(command):
    assert dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        # `<<` as a shift operator opens no heredoc.
        f"cat /dev/null $((1<<x)) # it's\n{_TRAILER_COMMIT}\nx",
        f"cat /dev/null $[1<<x] # it's\n{_TRAILER_COMMIT}\nx",
        f"cat /dev/null ${{a[1<<x]}} # it's\n{_TRAILER_COMMIT}\nx",
        # A `<<` inside arithmetic opened on an earlier line.
        f"echo $((1 +\ncat <<x)) # it's\n{_TRAILER_COMMIT}\nx",
    ],
)
def test_shift_operator_is_not_a_heredoc(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        # bash's delimiter is the whole word after quote removal: `E-O:F`,
        # `EOF`; a shorter one would close the body too late.
        f"cat <<E-O:F # it's\nE-O:F\n{_TRAILER_COMMIT}\nE-O",
        f"cat <<'E'OF # it's\nEOF\n{_TRAILER_COMMIT}\nE",
        f'cat <<E"O"F # it\'s\nEOF\n{_TRAILER_COMMIT}\nE',
    ],
)
def test_heredoc_delimiter_is_the_whole_word(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "cat <<'E'OF > notes.md\nthe user's git notes\nEOF",
        "cat <<\\EOF > notes.md\nthe user's git notes\nEOF",
        "tee -a notes.md <<'EOF'\nthe user's git notes\nEOF",
    ],
)
def test_heredoc_with_a_quoted_delimiter_word_is_data(command):
    assert dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        # A body naming git / gh is stripped only for a bare `cat` / `tee`.
        "cat $(echo x) <<'EOF'\nthe user's git notes\nEOF",
        "cat <<'EOF' > \"$f\"\nthe user's git notes\nEOF",
        "x/cat <<'EOF'\nthe user's git notes\nEOF",
        # The intro continues the previous line: `bash -s` runs stdin.
        "bash -s \\\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        # `cat` redefined as a function or alias.
        "cat() { bash; }\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        "alias cat=bash\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        # The cat output is run: substitution, process substitution, eval,
        # or a group piped to a shell.
        "$(cat <<'EOF'\nit's\ngit push --force\nEOF\n)",
        "`cat <<'EOF'\nit's\ngit push --force\nEOF\n`",
        "eval \"$(cat <<'EOF'\nit's\ngit push --force\nEOF\n)\"",
        "bash <(cat <<'EOF'\nit's\ngit push --force\nEOF\n)",
        "(\ncat <<'EOF'\nit's\ngit push --force\nEOF\n) | bash",
        "{\ncat <<'EOF'\nit's\ngit push --force\nEOF\n} | bash",
    ],
)
def test_heredoc_sink_must_be_a_bare_cat_or_tee(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


def test_eval_string_is_checked_like_a_shell_c_string():
    assert dispatch("""eval 'git commit -m "x\nCo-Authored-By: a"'""") is not None


@pytest.mark.parametrize(
    "command",
    [
        """eval -- 'git commit -m "x\nCo-Authored-By: a"'""",
        """builtin eval 'git commit -m "x\nCo-Authored-By: a"'""",
        """command eval 'git commit -m "x\nCo-Authored-By: a"'""",
    ],
)
def test_eval_spellings_are_checked_like_eval(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        """builtin command -- eval 'git commit -m "x\nCo-Authored-By: a"'""",
        """command -p eval 'git commit -m "x\nCo-Authored-By: a"'""",
    ],
)
def test_eval_behind_a_prefix_chain_is_checked(command):
    assert dispatch(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "eval -x 'git push --force'",
        "command -x eval 'git push --force'",
        "builtin -x eval 'git push --force'",
    ],
)
def test_eval_with_an_option_is_refused(command):
    reason = dispatch(command)
    assert reason and "agent-guard[wrapper]" in reason


def test_command_lookup_is_not_an_eval():
    assert dispatch("command -v gh") is None


@pytest.mark.parametrize(
    "command",
    [
        # Anywhere in the rest of the command, after quote removal.
        "cat <<'EOF' > s\nit's\ngit push --force\nEOF\nxargs e'v'al < s",
        "cat <<'EOF' > s\nit's\ngit push --force\nEOF\nenv source s",
        "cat <<'EOF' > s\nit's\ngit push --force\nEOF\nenv . s",
        "hash -p /bin/bash cat\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        "enable -f x.so cat\ncat <<'EOF'\nit's\ngit push --force\nEOF",
    ],
)
def test_heredoc_body_is_kept_next_to_eval_source_hash_or_enable(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


@pytest.mark.parametrize(
    "command",
    [
        # A non-sink heredoc body redefines `cat` before the stripped one.
        "bash <<'A'\ncat(){ bash; }\nA\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        # `eval` / `source` / `.` behind a prefix.
        "builtin source x\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        "command . x\ncat <<'EOF'\nit's\ngit push --force\nEOF",
        "X=1 eval x\ncat <<'EOF'\nit's\ngit push --force\nEOF",
    ],
)
def test_heredoc_body_is_stripped_only_when_every_heredoc_is_a_sink(command):
    reason = dispatch(command)
    assert reason and "agent-guard[parse]" in reason


def test_shell_option_value_letters_are_not_flags():
    # `c` inside zsh's attached option value is not `-c`
    assert dispatch("zsh -onocorrect script.zsh") is None


def test_untokenisable_command_honours_the_hook_env_kill_switch(monkeypatch):
    monkeypatch.setenv("MAGPIE_GUARD_OFF", "1")
    assert dispatch('gh pr comment 5 --body "oops') is None


def test_global_off_from_the_hook_environment(monkeypatch):
    monkeypatch.setenv("MAGPIE_GUARD_OFF", "1")
    assert dispatch('git commit -m "x\nCo-Authored-By: a"') is None


@pytest.mark.parametrize(
    "command",
    [
        'MAGPIE_GUARD_OFF=1 git commit -m "x\nCo-Authored-By: a"',
        'env MAGPIE_GUARD_OFF=1 git commit -m "x\nCo-Authored-By: a"',
        "MAGPIE_GUARD_OFF=1 bash -c \"git commit -m 'x\nCo-Authored-By: a'\"",
    ],
)
def test_global_off_inline_is_ignored(command):
    reason = dispatch(command)
    assert reason and "Co-Authored-By" in reason


@pytest.mark.parametrize("value", ["", "0", "false", "False"])
def test_global_off_falsy_values_keep_the_guards(monkeypatch, value):
    monkeypatch.setenv("MAGPIE_GUARD_OFF", value)
    assert dispatch('git commit -m "x\nCo-Authored-By: a"') is not None


def test_global_off_inline_does_not_pass_an_unparsable_wrapper():
    reason = dispatch("MAGPIE_GUARD_OFF=1 env -S 'git status'")
    assert reason and "agent-guard[wrapper]" in reason


def test_per_guard_inline_override_still_honoured():
    assert dispatch('MAGPIE_ALLOW_COAUTHOR=1 git commit -m "x\nCo-Authored-By: a"') is None


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


# --------------------------------------------------------------------------- #
# vetted-ops-spelling — dispatchers launched only from the literal ~ path
# --------------------------------------------------------------------------- #

# A harness's own installed plugin directory (another harness's rules decide it).
PLUGIN_CACHE_REVIEW = (
    "~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/0.9.0/tools/adversarial-review"
)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller x pr-view 1",
        "uv run --project ~/.claude/magpie/vetted-ops/ vetted-op-read pr-view 1",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read pr-view 1",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker status",
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op x",
        "uvx --from ~/.claude/magpie/adversarial-review adversarial-review detect",
        # Not a dispatcher launch: tests, builds and other tools stay untouched.
        "uv run --project tools/vetted-ops pytest -k vetted-op-read",
        "uv run --directory tools/vetted-ops --group dev pytest",
        # Another harness's own installed plugin directory is its rules' business.
        f"uvx --from {PLUGIN_CACHE_REVIEW} adversarial-review detect",
        "uvx --from /opt/harness/plugins/magpie/tools/adversarial-review adversarial-review detect",
        "uvx ruff check .",
        "uv sync",
    ],
)
def test_vetted_ops_spelling_allows(command):
    assert agent_guard.dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project /Users/alice/.claude/magpie/vetted-ops vetted-op-read pr-view 1",
        "uvx --from /home/alice/.claude/magpie/vetted-ops vetted-op-read pr-view 1",
        "uv run --project $HOME/.claude/magpie/vetted-ops vetted-op-read pr-view 1",
        "uv run --project tools/vetted-ops vetted-op-read pr-view 1",
        "uv run --project ./tools/vetted-ops vetted-op-tracker status",
        "uv run --project plugins/magpie-vetted-ops/tools/vetted-ops vetted-op x",
        "uvx --from /home/alice/.claude/magpie/adversarial-review adversarial-review detect",
        # The right base for the wrong dispatcher is still the wrong base.
        "uvx --from ~/.claude/magpie/vetted-ops adversarial-review detect",
        "cd /repo && uv run --project /Users/alice/.claude/magpie/vetted-ops vetted-op-read x",
    ],
)
def test_vetted_ops_spelling_denies(command):
    reason = agent_guard.dispatch(command)
    assert reason and "agent-guard[vetted-ops-spelling]" in reason
    assert "~/.claude/magpie/" in reason


def test_vetted_ops_spelling_names_the_fix():
    reason = agent_guard.dispatch("uv run --project /Users/alice/.claude/magpie/vetted-ops vetted-op-read x")
    assert "`uv run --project ~/.claude/magpie/vetted-ops vetted-op-read …`" in reason


def test_vetted_ops_spelling_override():
    command = "MAGPIE_ALLOW_VETTED_PATH=1 uv run --project tools/vetted-ops vetted-op-read pr-view 1"
    assert agent_guard.dispatch(command) is None


def test_vetted_ops_spelling_codex_keeps_its_absolute_rewrite(monkeypatch, tmp_path):
    import os

    pwd = pytest.importorskip("pwd")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))  # no registration: the default root
    home = pwd.getpwuid(os.getuid()).pw_dir
    command = f"uv run --project {home}/.claude/magpie/vetted-ops vetted-op-read pr-view 1"
    assert agent_guard.dispatch(command, harness="codex") is None
    assert agent_guard.dispatch(command) is not None
    # Any other `.claude/magpie` root is one the agent could have built: refused.
    other = "uv run --project /elsewhere/.claude/magpie/vetted-ops vetted-op-read pr-view 1"
    assert agent_guard.dispatch(other, harness="codex") is not None


def _register_codex_hook(codex_home, root):
    """Write the hook registration `vetted-ops-codex-rules --hook --tool-root <root>` renders."""
    import shlex

    command = f"python3 {shlex.quote(root + '/hooks/codex-expand-stable-path.py')} --stable-path {shlex.quote(root)}"
    (codex_home / "config.toml").write_text(
        '[[hooks.PreToolUse]]\nmatcher = "^Bash$"\n\n[[hooks.PreToolUse.hooks]]\n'
        f'type = "command"\ncommand = {json.dumps(command)}\ntimeout = 10\n'
    )


@pytest.mark.parametrize(
    "command, allowed",
    [
        # The trusted `--tool-root` the rewrite hook was registered with.
        ("uv run --project /srv/account/.claude/magpie/vetted-ops vetted-op-read pr-view 1", True),
        ("uvx --from /srv/account/.claude/magpie/vetted-ops/ vetted-op-read pr-view 1", True),
        # The hook rewrites reads only, so a write in that spelling is the agent's.
        ("uv run --project /srv/account/.claude/magpie/vetted-ops vetted-op-tracker status", False),
        # Not the registered root, or a path game around it.
        ("uv run --project /srv/other/.claude/magpie/vetted-ops vetted-op-read x", False),
        ("uv run --project /srv/account/.claude/magpie/vetted-ops/../../../tmp/x vetted-op-read x", False),
        ("uv run --project tools/vetted-ops vetted-op-read x", False),
    ],
)
def test_vetted_ops_spelling_codex_accepts_only_its_registered_root(monkeypatch, tmp_path, command, allowed):
    pytest.importorskip("pwd")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    _register_codex_hook(tmp_path, "/srv/account/.claude/magpie/vetted-ops")
    assert (agent_guard.dispatch(command, harness="codex") is None) is allowed
    # Outside Codex the `~` spelling is the only one.
    assert agent_guard.dispatch(command) is not None


@pytest.mark.parametrize(
    "command, denied",
    [
        ("uv --project tools/vetted-ops run vetted-op-read pr-view 1", True),
        ("uv --directory /tmp --project tools/vetted-ops run vetted-op-tracker status", True),
        ("uv --project=/home/alice/.claude/magpie/vetted-ops run vetted-op-read x", True),
        ("uv --project ~/.claude/magpie/vetted-ops run vetted-op-read pr-view 1", False),
        ("uv --directory /tmp run --project ~/.claude/magpie/vetted-ops vetted-op-read x", False),
        # Another subcommand is not a launch.
        ("uv --project tools/vetted-ops sync", False),
    ],
)
def test_vetted_ops_spelling_reads_options_before_run(command, denied):
    assert (agent_guard.dispatch(command) is not None) is denied


def test_vetted_ops_spelling_reads_a_commented_codex_registration(monkeypatch, tmp_path):
    pytest.importorskip("pwd")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    _register_codex_hook(tmp_path, "/srv/account/.claude/magpie/vetted-ops")
    config = tmp_path / "config.toml"
    # Valid TOML a person might add by hand: an inline comment after the value.
    config.write_text(config.read_text().replace("\ntimeout", "  # reviewed\ntimeout"))
    command = "uv run --project /srv/account/.claude/magpie/vetted-ops vetted-op-read pr-view 1"
    assert agent_guard.dispatch(command, harness="codex") is None


def test_vetted_ops_spelling_finds_the_checkout_from_any_cwd(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / "tools" / "vetted-ops").mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    def stub(args, cwd=None):
        # git answers only inside the repository, as it does for real.
        if args == ["git", "rev-parse", "--show-toplevel"] and cwd and str(cwd).startswith(str(repo)):
            return str(repo)
        return None

    monkeypatch.setattr(agent_guard, "_run", stub)
    command = f"uv --directory {repo} run --project {repo}/tools/vetted-ops vetted-op-read pr-view 1"
    reason = agent_guard.dispatch(command, cwd=str(elsewhere))
    assert reason and "agent-guard[vetted-ops-spelling]" in reason
    # A directory merely named like a plugin cache inside a checkout is not one.
    lookalike = repo / ".claude" / "plugins" / "cache" / "x" / "1.0" / "tools" / "adversarial-review"
    lookalike.mkdir(parents=True)
    monkeypatch.setattr(agent_guard, "_account_home", lambda: str(tmp_path / "home"))
    reason = agent_guard.dispatch(f"uvx --from {lookalike} adversarial-review detect", cwd=str(repo))
    assert reason and "agent-guard[vetted-ops-spelling]" in reason


def test_vetted_ops_spelling_codex_matches_a_symlinked_home_as_spelled(monkeypatch, tmp_path):
    import os

    pwd = pytest.importorskip("pwd")
    real = tmp_path / "real-home"
    real.mkdir()
    linked = tmp_path / "home"
    linked.symlink_to(real)
    entry = pwd.getpwuid(os.getuid())

    class Entry:
        pw_dir = str(linked)

    monkeypatch.setattr(pwd, "getpwuid", lambda uid: Entry if uid == os.getuid() else entry)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))  # no registration: the default root
    # The rewrite hook keeps the database spelling of the home, symlink and all.
    command = f"uv run --project {linked}/.claude/magpie/vetted-ops vetted-op-read pr-view 1"
    assert agent_guard.dispatch(command, harness="codex") is None


def test_vetted_ops_spelling_exempts_the_accounts_own_plugin_cache(monkeypatch, tmp_path):
    # A version-controlled home: the real plugin cache sits inside a git tree.
    home = tmp_path / "home"
    cache = home / ".claude" / "plugins" / "cache" / "apache-magpie" / "1.0" / "tools" / "adversarial-review"
    cache.mkdir(parents=True)
    monkeypatch.setattr(agent_guard, "_account_home", lambda: str(home))
    monkeypatch.setattr(agent_guard, "_run", lambda args, cwd=None: str(home))
    assert agent_guard.dispatch(f"uvx --from {cache} adversarial-review detect", cwd=str(home)) is None


def test_vetted_ops_spelling_refuses_an_absolute_checkout_path(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / "tools" / "vetted-ops").mkdir(parents=True)
    monkeypatch.setattr(
        agent_guard,
        "_run",
        fake_run(lambda args: str(repo) if args[:3] == ["git", "rev-parse", "--show-toplevel"] else None),
    )
    inside = f"uv run --project {repo}/tools/vetted-ops vetted-op-read pr-view 1"
    reason = agent_guard.dispatch(inside, cwd=str(repo))
    assert reason and "agent-guard[vetted-ops-spelling]" in reason
    # A harness's own plugin directory outside the working tree is left alone.
    outside = "uvx --from /opt/harness/plugins/magpie/tools/adversarial-review adversarial-review detect"
    assert agent_guard.dispatch(outside, cwd=str(repo)) is None


# --------------------------------------------------------------------------- #
# Prefix wrappers (#1679): `env …` / `command …` run their argument, so every
# guard sees through them.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "prefix",
    ["env ", "env -i ", "env -u HOME ", "env A=1 B=2 ", "env -- ", "command ", "command -p ", "env command "],
)
def test_prefix_wrappers_reach_the_bundled_guards(prefix):
    reason = agent_guard.dispatch(f'{prefix}git commit -m "x\n\nCo-Authored-By: a"')
    assert reason and "Co-Authored-By" in reason
    reason = agent_guard.dispatch(f"{prefix}uv run --project tools/vetted-ops vetted-op-read pr-view 1")
    assert reason and "agent-guard[vetted-ops-spelling]" in reason


def test_command_lookup_is_not_an_execution():
    assert agent_guard.dispatch("command -v git") is None


def test_an_env_assignment_still_overrides():
    assert (
        agent_guard.dispatch(
            "env MAGPIE_ALLOW_VETTED_PATH=1 uv run --project tools/vetted-ops vetted-op-read x"
        )
        is None
    )


@pytest.mark.parametrize(
    "base",
    [
        '"~/.claude/magpie/vetted-ops"',
        "'~/.claude/magpie/vetted-ops'",
        "\\~/.claude/magpie/vetted-ops",
        # A quote after the `~` stops expansion just the same.
        '~"/.claude/magpie/vetted-ops"',
    ],
)
def test_vetted_ops_spelling_refuses_a_quoted_tilde(base):
    reason = agent_guard.dispatch(f"uv run --project {base} vetted-op-read pr-view 1")
    assert reason and "quoted or escaped" in reason
    reason = agent_guard.dispatch(f"uvx --from={base} vetted-op-read pr-view 1")
    assert reason and "quoted or escaped" in reason


def test_a_bare_tilde_is_still_allowed():
    assert (
        agent_guard.dispatch("uv run --project ~/.claude/magpie/vetted-ops vetted-op-read pr-view 1") is None
    )


# --------------------------------------------------------------------------- #
# Sandbox-excluded user-scope scripts: only the literal `~` spelling matches.
# --------------------------------------------------------------------------- #

EVALS = "tools/skill-evals/evals/setup"


def test_the_eval_wrapper_spelled_with_tilde_is_allowed():
    assert agent_guard.dispatch(f"~/.claude/scripts/magpie-run-evals.sh {EVALS}") is None


@pytest.mark.parametrize(
    "head",
    [
        "/Users/alice/.claude/scripts/magpie-run-evals.sh",
        "/home/alice/.claude/scripts/magpie-run-evals.sh",
        "$HOME/.claude/scripts/magpie-run-evals.sh",
        '"~/.claude/scripts/magpie-run-evals.sh"',
        "\\~/.claude/scripts/magpie-run-evals.sh",
        "tools/skill-evals/magpie-run-evals.sh",
        "./magpie-run-evals.sh",
        # Right spelling behind a wrapper: the exclusion matches the line's start.
        "env ~/.claude/scripts/magpie-run-evals.sh",
        "command ~/.claude/scripts/magpie-run-evals.sh",
    ],
)
def test_the_eval_wrapper_spelled_otherwise_is_refused(head):
    reason = agent_guard.dispatch(f"{head} {EVALS}")
    assert reason and "~/.claude/scripts/magpie-run-evals.sh" in reason


@pytest.mark.parametrize("prefix", ["env ", "command ", "env -i "])
def test_a_wrapped_vetted_launch_is_refused_even_with_the_tilde(prefix):
    reason = agent_guard.dispatch(f"{prefix}uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x")
    assert reason and "whole command" in reason


def test_the_eval_wrapper_override():
    assert (
        agent_guard.dispatch(
            f"MAGPIE_ALLOW_SCRIPT_PATH=1 /Users/a/.claude/scripts/magpie-run-evals.sh {EVALS}"
        )
        is None
    )


def test_vetted_ops_spelling_refuses_the_equals_form_with_a_tilde():
    # `--project=~/…` is not an assignment: the shell leaves the `~` alone.
    reason = agent_guard.dispatch("uv run --project=~/.claude/magpie/vetted-ops vetted-op-read x")
    assert reason and "quoted or escaped" in reason


@pytest.mark.parametrize(
    "command",
    [
        "env " * 70 + "git status",  # deeper than the unwrap limit
        "env --bogus-option git commit -m x",
        "env -X git commit -m x",
        "env -u",  # option missing its value
        # env splits a -S string with escapes shlex does not reproduce.
        "env -S 'git status'",
        "env -S'git status'",
        "env -iS 'git status'",
        "env --split-string='git status'",
        "env --split-string 'git status'",
        """env -S 'git\\_commit -m x'""",
        "command -x git commit -m x",
    ],
)
def test_an_unparsable_wrapper_is_refused(command):
    reason = agent_guard.dispatch(command)
    assert reason and "agent-guard[wrapper]" in reason


@pytest.mark.parametrize(
    "prefix",
    [
        "env -iu HOME ",  # clustered short options, value in the next token
        "env -uHOME ",  # value attached
        "env -iCdir ",
        "env --unset=HOME ",
        "env --chdir /tmp ",
        "env --default-signal ",
        "command -p -- ",
    ],
)
def test_wrapper_option_forms_still_reach_the_guards(prefix):
    reason = agent_guard.dispatch(f'{prefix}git commit -m "x\n\nCo-Authored-By: a"')
    assert reason and "Co-Authored-By" in reason


# --------------------------------------------------------------------------- #
# More prefix wrappers: `exec`, `nohup`, `time`, and a shell's `-c` string.
# --------------------------------------------------------------------------- #

COAUTHOR_COMMIT = 'git commit -m "x\n\nCo-Authored-By: a"'


@pytest.mark.parametrize(
    "prefix",
    [
        "exec ",
        "exec -c ",
        "exec -l ",
        "exec -cl ",
        "exec -a name ",
        "exec -aname ",
        "exec -- ",
        "nohup ",
        "nohup -- ",
        "time ",
        "time -p ",
        "time -v ",
        "time -o out.txt ",
        "time -f %e ",
        "time --format=%e ",
        "time --output out.txt ",
        "/usr/bin/time -l ",
        "env FOO=1 ",
        "nohup env FOO=1 command ",
        "time nohup exec ",
    ],
)
def test_more_prefix_wrappers_reach_the_bundled_guards(prefix):
    reason = agent_guard.dispatch(f"{prefix}{COAUTHOR_COMMIT}")
    assert reason and "Co-Authored-By" in reason


@pytest.mark.parametrize(
    "command",
    [
        "bash -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "sh -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "zsh -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "bash -lc 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "bash -e -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "bash -o pipefail -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "bash --norc -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "/bin/sh -c 'git commit -m \"x\n\nCo-Authored-By: a\"' name arg",
        "env bash -c 'git commit -m \"x\n\nCo-Authored-By: a\"'",
        "cd /tmp && bash -c 'ls && git commit -m \"x\n\nCo-Authored-By: a\"'",
        "bash -c 'env git commit -m \"x\n\nCo-Authored-By: a\"'",
    ],
)
def test_shell_dash_c_string_reaches_the_bundled_guards(command):
    reason = agent_guard.dispatch(command)
    assert reason and "Co-Authored-By" in reason


@pytest.mark.parametrize(
    "command",
    [
        "bash -c 'git status'",
        "sh -c 'ls -la && git log --oneline -5'",
        "bash -c \"git commit -m 'clean fix'\"",
        "bash script.sh -c 'git commit'",  # `-c` after the script is the script's
        "bash",
        "bash -l",
        "nohup --help",
        "exec",
        "exec 3>&1",
        "time",
        "time -p ls",
        "nohup ./build.sh",
    ],
)
def test_wrappers_and_shells_still_allow_clean_commands(command):
    assert agent_guard.dispatch(command) is None


def test_shell_dash_c_inherits_inline_per_guard_overrides():
    command = "MAGPIE_ALLOW_COAUTHOR=1 bash -c 'git commit -m \"x\n\nCo-Authored-By: a\"'"
    assert agent_guard.dispatch(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "bash -c \"bash -c 'git status'\"",
        "sh -c 'zsh -c \"gh pr view 1\"'",
        "exec -x git commit -m x",
        "exec -a",
        "nohup -x git commit -m x",
        "time -Z git commit -m x",
        "time --bogus git commit -m x",
        "time -o",
    ],
)
def test_more_unparsable_wrappers_are_refused(command):
    reason = agent_guard.dispatch(command)
    assert reason and "agent-guard[wrapper]" in reason


def test_nested_shell_without_a_guarded_head_allows():
    assert agent_guard.dispatch("bash -c \"sh -c 'echo hi'\"") is None


def test_wrapped_vetted_launch_behind_the_new_wrappers_is_refused():
    for prefix in ("exec ", "nohup ", "time "):
        reason = agent_guard.dispatch(
            f"{prefix}uv run --project ~/.claude/magpie/vetted-ops vetted-op-read x"
        )
        assert reason and "whole command" in reason


def test_git_run_in_the_opened_tree_ignores_its_fsmonitor_and_hooks(tmp_path):
    """A crafted `.git/config` (a tarball, an svn checkout carrying `.git/`) can
    name a `core.fsmonitor` program git runs on any index refresh; the guard's
    own git calls never run it."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "marker"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\necho ran >> {marker}\nexit 1\n")
    hook.chmod(0o755)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "f.txt").write_text("hi\n")
    subprocess.run(["git", "-C", str(repo), "add", "f.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.fsmonitor", str(hook)], check=True)
    assert agent_guard._run(["git", "status", "--porcelain"], cwd=str(repo)) is not None
    assert not marker.exists()
