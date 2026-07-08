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
def dispatch(command):
    return agent_guard.dispatch(command, cwd=None)


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
