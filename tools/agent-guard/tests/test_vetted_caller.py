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

"""The vetted-ops-caller rule: a ``vetted-op*`` launch must pass the running
skill's own ``--caller`` (#2124). Transcripts here are synthetic, in the shape
Claude Code writes: one JSON object per line."""

import io
import json
from pathlib import Path

import pytest

import agent_guard

LAUNCH = "uv run --project ~/.claude/magpie/vetted-ops vetted-op --caller {caller} issue-add-label 1 x"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for name in ("MAGPIE_GUARD_OFF", agent_guard.CALLER_OVERRIDE_ENV):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def skills(monkeypatch, tmp_path):
    """Two skills of one plugin, each naming its own caller in its docs."""
    plugin = tmp_path / "plugins" / "magpie-security" / "skills"
    for name, caller in (
        ("issue-sync", "security-issue-sync"),
        ("cve-allocate", "security-cve-allocate"),
        ("issue-fix", "security-issue-fix"),
    ):
        d = plugin / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: x\n---\n\nSee steps.md.\n")
        (d / "steps.md").write_text(f"Run `vetted-op --caller {caller} issue-add-label <n> <label>`.\n")
    quiet = plugin / "no-vetted-ops"
    quiet.mkdir()
    (quiet / "SKILL.md").write_text("---\nname: no-vetted-ops\n---\n")
    dirs = [("magpie-security", d) for d in sorted(plugin.iterdir())]
    links = tmp_path / "skills"
    links.mkdir()
    (links / "security-issue-sync").symlink_to(plugin / "issue-sync")
    dirs.append(("", links / "security-issue-sync"))
    monkeypatch.setattr(agent_guard, "_skill_dirs", lambda: dirs)
    agent_guard._skill_callers.cache_clear()
    yield
    agent_guard._skill_callers.cache_clear()


def skill_call(name):
    return {
        "type": "assistant",
        "isSidechain": False,
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Running it."},
                {"type": "tool_use", "id": "toolu_1", "name": "Skill", "input": {"skill": name}},
            ],
        },
    }


def slash(name):
    content = f"<command-name>/{name}</command-name>\n<command-message>{name}</command-message>\n<command-args></command-args>"
    return {"type": "user", "message": {"role": "user", "content": content}}


def prompt(text="go on"):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result():
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}],
        },
    }


def write(path: Path, *entries, raw: str = "") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in entries) + raw)
    return str(path)


def check(transcript, caller):
    return agent_guard.dispatch(LAUNCH.format(caller=caller), transcript_path=transcript)


def test_another_skills_caller_is_refused(skills, tmp_path):
    # The case #2124 records: the ID-allocation skill borrowing issue-sync's grants.
    t = write(tmp_path / "s.jsonl", skill_call("magpie-security:cve-allocate"))
    reason = check(t, "security-issue-sync")
    assert reason and "agent-guard[vetted-ops-caller]" in reason
    assert "`magpie-security:cve-allocate`" in reason
    assert "`security-cve-allocate`" in reason
    assert "--caller security-issue-sync" in reason


def test_the_skills_own_caller_is_allowed(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("magpie-security:cve-allocate"))
    assert check(t, "security-cve-allocate") is None


@pytest.mark.parametrize("name", ["issue-sync", "magpie-security:issue-sync"])
def test_a_skill_is_known_bare_and_by_plugin(skills, tmp_path, name):
    t = write(tmp_path / "s.jsonl", skill_call(name))
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_the_equals_form_is_read(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("issue-sync"))
    command = (
        "uv run --project ~/.claude/magpie/vetted-ops vetted-op-read --caller=security-cve-allocate pr-view 1"
    )
    assert agent_guard.dispatch(command, transcript_path=t)


@pytest.mark.parametrize(
    "entry", ["vetted-op-tracker-batch", "vetted-op-tracker-batch-unprompted", "vetted-op-git"]
)
def test_every_vetted_op_entry_point_is_checked(skills, tmp_path, entry):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    command = f"uv run --project ~/.claude/magpie/vetted-ops {entry} --caller security-issue-sync x"
    assert agent_guard.dispatch(command, transcript_path=t)
    assert (
        agent_guard.dispatch(
            command.replace("security-issue-sync", "security-cve-allocate"), transcript_path=t
        )
        is None
    )


def test_a_skill_expires_after_the_turn_cap(skills, tmp_path):
    turns = [prompt(f"step {i}") for i in range(agent_guard._SKILL_TURNS - 1)]
    t = write(tmp_path / "s.jsonl", skill_call("issue-sync"), skill_call("cve-allocate"), *turns)
    assert check(t, "security-issue-sync") is None
    t = write(
        tmp_path / "s.jsonl", skill_call("issue-sync"), *turns, prompt("one more"), skill_call("cve-allocate")
    )
    assert check(t, "security-cve-allocate") is None
    assert check(t, "security-issue-sync")


def test_an_outer_skill_keeps_its_caller_after_the_user_confirms_the_inner_one(skills, tmp_path):
    # issue-fix runs issue-sync, the user confirms its corrections in a chat
    # reply, and issue-fix carries on with its own writes.
    t = write(
        tmp_path / "s.jsonl",
        skill_call("issue-fix"),
        tool_result(),
        skill_call("issue-sync"),
        tool_result(),
        prompt("yes, apply"),
    )
    assert check(t, "security-issue-fix") is None
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_an_outer_skill_keeps_its_caller_after_running_another(skills, tmp_path):
    # security-issue-fix runs security-issue-sync first, then carries on with
    # its own writes.
    t = write(
        tmp_path / "s.jsonl",
        prompt("fix issue 12"),
        skill_call("issue-fix"),
        tool_result(),
        skill_call("issue-sync"),
        tool_result(),
    )
    assert check(t, "security-issue-fix") is None
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_a_skill_keeps_its_caller_across_the_users_answers(skills, tmp_path):
    # The user answers a question the skill asked: the skill is still running.
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), tool_result(), prompt("yes, go ahead"))
    assert check(t, "security-cve-allocate") is None
    assert check(t, "security-issue-sync")


def test_a_tool_result_does_not_start_a_turn(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("issue-fix"), tool_result(), skill_call("issue-sync"))
    assert check(t, "security-issue-fix") is None


def test_a_slash_command_starts_a_turn_with_its_skill(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), slash("magpie-security:issue-sync"))
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_an_unknown_skill_in_the_turn_allows(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), skill_call("someone-elses:skill"))
    assert check(t, "security-issue-sync") is None


def test_a_skill_is_known_by_its_magpie_link_name(skills, tmp_path):
    # Snapshot and self-adoption installs expose skills as .claude/skills/magpie-<link>.
    t = write(tmp_path / "s.jsonl", skill_call("magpie-security-issue-sync"))
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_a_repeated_bookkeeping_copy_is_not_an_invocation(skills, tmp_path):
    # Claude Code repeats a tool call in entries of other types; only the
    # assistant entry is the call.
    blob = {"type": "api-request-blob", "message": skill_call("issue-sync")["message"]}
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), blob)
    assert check(t, "security-cve-allocate") is None


def test_a_slash_command_naming_a_skill_counts(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), slash("magpie-security:issue-sync"))
    assert check(t, "security-issue-sync") is None
    assert check(t, "security-cve-allocate")


def test_a_builtin_slash_command_does_not_end_the_skill(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), slash("model"))
    assert check(t, "security-issue-sync")


def test_a_prompt_quoting_a_command_tag_is_not_an_invocation(skills, tmp_path):
    quoted = {
        "type": "user",
        "message": {"content": "what does <command-name>/issue-sync</command-name> do?"},
    }
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), quoted)
    assert check(t, "security-issue-sync")


@pytest.mark.parametrize(
    "transcript",
    [None, "", "/nonexistent/session.jsonl"],
)
def test_no_readable_transcript_allows(skills, transcript):
    assert check(transcript, "anything") is None


def test_no_skill_invoked_allows(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", {"type": "user", "message": {"content": "hi"}})
    assert check(t, "security-issue-sync") is None


def test_an_unknown_skill_allows(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("some-other-plugin:thing"))
    assert check(t, "security-issue-sync") is None


def test_a_skill_naming_no_caller_allows(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("no-vetted-ops"))
    assert check(t, "security-issue-sync") is None


def test_malformed_lines_are_skipped(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"), raw='{"Skill" not json\n[1, 2]\n')
    assert check(t, "security-issue-sync")


def test_a_subagent_reads_its_parent_session(skills, tmp_path):
    # A gatherer subagent passes its parent skill's caller; its own transcript
    # has no skill invocation, its parent session's does.
    write(tmp_path / "proj" / "abc.jsonl", skill_call("issue-sync"))
    sub = write(
        tmp_path / "proj" / "abc" / "subagents" / "agent-1.jsonl",
        {"type": "user", "message": {"content": "go"}},
    )
    assert check(sub, "security-issue-sync") is None
    assert check(sub, "security-cve-allocate")


def test_other_launches_are_not_checked(skills, tmp_path):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    review = "uvx --from ~/.claude/magpie/adversarial-review adversarial-review detect --caller x"
    assert agent_guard.dispatch(review, transcript_path=t) is None
    assert agent_guard.dispatch("gh issue view 1", transcript_path=t) is None


def test_the_hook_environment_override_allows(skills, tmp_path, monkeypatch):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    monkeypatch.setenv(agent_guard.CALLER_OVERRIDE_ENV, "1")
    assert check(t, "security-issue-sync") is None


def test_an_inline_override_does_not_allow(skills, tmp_path):
    # Written on the command line, the override would be the agent's own choice,
    # the very borrowing the rule stops.
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    command = f"{agent_guard.CALLER_OVERRIDE_ENV}=1 " + LAUNCH.format(caller="security-issue-sync")
    assert agent_guard.dispatch(command, transcript_path=t)


class _Stdin(io.StringIO):
    pass


def test_claude_hook_passes_its_transcript(skills, tmp_path, monkeypatch, capsys):
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    event = {
        "tool_name": "Bash",
        "transcript_path": t,
        "tool_input": {"command": LAUNCH.format(caller="security-issue-sync")},
    }
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(event)))
    assert agent_guard.main() == 0
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "vetted-ops-caller" in out["permissionDecisionReason"]


def test_codex_transcripts_are_not_read(skills, tmp_path, capsys):
    # Codex writes its own transcript format; the rule stays off there.
    t = write(tmp_path / "s.jsonl", skill_call("cve-allocate"))
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "transcript_path": t,
        "tool_input": {"command": LAUNCH.format(caller="security-issue-sync")},
    }
    assert agent_guard._claude_event(event, "codex") == 0
    assert "vetted-ops-caller" not in capsys.readouterr().out


def test_the_shipped_skills_name_their_own_callers(tmp_path):
    # Against the real skill tree this engine runs from: the #2124 case.
    if agent_guard.framework_root() is None:
        pytest.skip("not running from a framework tree")
    assert agent_guard._skill_callers("magpie-security:cve-allocate") == {"security-cve-allocate"}
    assert agent_guard._skill_callers("magpie-security:issue-sync") == {"security-issue-sync"}
    assert agent_guard._skill_callers("magpie-security-issue-sync") == {"security-issue-sync"}
    t = write(tmp_path / "s.jsonl", skill_call("magpie-security:cve-allocate"))
    assert check(t, "security-issue-sync")
    assert check(t, "security-cve-allocate") is None
