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
from __future__ import annotations

import json
from pathlib import Path

import pytest

from adversarial_review.backends import ANTIGRAVITY_TOOL_NOTE, BACKENDS, BackendOutputError, RunContext

CTX = RunContext(
    repo_dir=Path("/repo"),
    prompt="PROMPT",
    brief_path=Path("/t/brief.md"),
    schema_path=Path("/t/findings.schema.json"),
    last_message_path=Path("/t/codex-last-message.json"),
)
WRITE_GRANTING = {
    "--allow-all-tools",
    "--allow-all-paths",
    "yolo",
    "--yolo",
    "auto_edit",
    "danger-full-access",
    "workspace-write",
    "--full-auto",
    "--dangerously-bypass-approvals-and-sandbox",
    "--dangerously-skip-permissions",
    "bypassPermissions",
    "--always-approve",
    "acceptEdits",
}


def test_backend_set_and_order():
    # Claude Code's widely inherited CLAUDECODE must stay last; grok's marker
    # is narrowly scoped to grok's own children, so it sits just before it.
    assert list(BACKENDS) == ["codex", "copilot", "antigravity", "pi", "grok", "goose", "claude"]


def test_codex_argv():
    inv = BACKENDS["codex"].build(CTX)
    assert inv.argv == [
        "codex",
        "exec",
        "-s",
        "read-only",
        "--ephemeral",
        "-c",
        "mcp_servers={}",
        "--skip-git-repo-check",
        "-C",
        "/repo",
        "--output-schema",
        "/t/findings.schema.json",
        "-o",
        "/t/codex-last-message.json",
        "-",
    ]
    assert inv.stdin == "PROMPT"


def test_copilot_argv():
    inv = BACKENDS["copilot"].build(CTX)
    assert inv.argv == [
        "copilot",
        "-p",
        "Read the review brief at /t/brief.md and follow it exactly. Change no file and run no command.",
        "--add-dir",
        "/t",
        "--deny-tool",
        "shell",
        "--deny-tool",
        "write",
        "--no-color",
        "--log-level",
        "none",
    ]
    assert inv.stdin is None


def test_antigravity_argv():
    inv = BACKENDS["antigravity"].build(CTX)
    assert inv.argv == [
        "agy",
        "--mode",
        "plan",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--print-timeout",
        "0",
    ]
    # agy reads stdin only as stream-json: one NDJSON user message.
    assert inv.stdin is not None and inv.stdin.endswith("\n") and inv.stdin.count("\n") == 1
    assert json.loads(inv.stdin) == {
        "event": "user",
        "message": {"content": "PROMPT" + ANTIGRAVITY_TOOL_NOTE},
    }


def test_antigravity_stdin_keeps_a_multiline_prompt_on_one_ndjson_line():
    ctx = RunContext(**{**CTX.__dict__, "prompt": "line 1\nline 2\n"})
    stdin = BACKENDS["antigravity"].build(ctx).stdin
    assert stdin is not None and stdin.count("\n") == 1
    assert json.loads(stdin)["message"]["content"] == "line 1\nline 2\n" + ANTIGRAVITY_TOOL_NOTE


@pytest.mark.parametrize("name", [n for n in BACKENDS if n != "antigravity"])
def test_only_antigravity_gets_the_tool_note(name):
    inv = BACKENDS[name].build(CTX)
    assert ANTIGRAVITY_TOOL_NOTE not in " ".join(inv.argv) + (inv.stdin or "")


def test_pi_argv():
    inv = BACKENDS["pi"].build(CTX)
    assert inv.argv == [
        "pi",
        "-p",
        "--no-session",
        "--no-approve",
        "--tools",
        "read,grep,find,ls",
        "Follow the review brief above exactly. Change no file.",
    ]
    # Pi prepends piped stdin to the first prompt.
    assert inv.stdin == "PROMPT"


def test_pi_tool_allowlist_has_no_shell_or_write_tool():
    argv = BACKENDS["pi"].build(CTX).argv
    tools = set(argv[argv.index("--tools") + 1].split(","))
    assert tools == {"read", "grep", "find", "ls"}
    assert "-a" not in argv and "--approve" not in argv


def test_goose_argv_runs_chat_mode_with_the_brief_file():
    inv = BACKENDS["goose"].build(CTX)
    assert inv.argv == ["goose", "run", "--no-session", "--no-profile", "--quiet", "-i", str(CTX.brief_path)]
    assert inv.stdin is None
    # Chat mode gives the model no tools: the reviewer can only read the brief.
    assert inv.env == {"GOOSE_MODE": "chat"}


def test_goose_runs_from_the_brief_directory_not_the_reviewed_tree(tmp_path):
    # Goose loads project plugins, hooks and context files from its working
    # directory; a chat-only reviewer needs none of the reviewed tree's files.
    (tmp_path / ".agents" / "plugins" / "evil").mkdir(parents=True)
    ctx = RunContext(**{**CTX.__dict__, "repo_dir": tmp_path})
    inv = BACKENDS["goose"].build(ctx)
    assert inv.cwd == ctx.brief_path.parent
    assert inv.cwd != tmp_path


def test_goose_extract_is_plain_text():
    assert BACKENDS["goose"].extract('{"findings": []}\n', CTX) == '{"findings": []}\n'
    with pytest.raises(BackendOutputError, match="empty reply"):
        BACKENDS["goose"].extract("  \n", CTX)


def test_pi_extract_is_plain_text():
    assert BACKENDS["pi"].extract('{"findings": []}\n', CTX) == '{"findings": []}\n'
    with pytest.raises(BackendOutputError, match="empty reply"):
        BACKENDS["pi"].extract("  \n", CTX)


def test_grok_argv():
    inv = BACKENDS["grok"].build(CTX)
    assert inv.argv == [
        "grok",
        "--tools",
        "read_file,grep,list_dir",
        "--no-subagents",
        "--disable-web-search",
        "--deny",
        "Bash",
        "--deny",
        "Edit",
        "--deny",
        "Write",
        "--deny",
        "WebFetch",
        "--deny",
        "MCPTool",
        "--output-format",
        "json",
        "--prompt-file",
        "/t/brief.md",
    ]
    assert inv.stdin is None


def test_claude_argv():
    inv = BACKENDS["claude"].build(CTX)
    assert inv.argv == [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--strict-mcp-config",
        "--disallowedTools",
        "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Task",
    ]
    assert inv.stdin == "PROMPT"


@pytest.mark.parametrize(
    ("name", "flag"),
    [
        ("codex", "-m"),
        ("copilot", "--model"),
        ("antigravity", "--model"),
        ("pi", "--model"),
        ("grok", "-m"),
        ("goose", "--model"),
        ("claude", "--model"),
    ],
)
def test_model_override_is_passed(name, flag):
    ctx = RunContext(**{**CTX.__dict__, "model": "some-model"})
    argv = BACKENDS[name].build(ctx).argv
    assert argv[argv.index(flag) + 1] == "some-model"


@pytest.mark.parametrize("name", list(BACKENDS))
def test_no_backend_grants_writes_or_carries_the_prompt_in_argv(name):
    ctx = RunContext(**{**CTX.__dict__, "prompt": "DIFF-BODY-MUST-NOT-BE-IN-ARGV"})
    argv = BACKENDS[name].build(ctx).argv
    assert not WRITE_GRANTING & set(argv)
    assert not any("DIFF-BODY-MUST-NOT-BE-IN-ARGV" in a for a in argv)


def test_codex_extract_reads_the_last_message_file(tmp_path):
    ctx = RunContext(**{**CTX.__dict__, "last_message_path": tmp_path / "last.json"})
    (tmp_path / "last.json").write_text('{"findings": []}', encoding="utf-8")
    assert BACKENDS["codex"].extract("ignored stdout", ctx) == '{"findings": []}'


def test_codex_extract_without_file_is_an_output_error(tmp_path):
    ctx = RunContext(**{**CTX.__dict__, "last_message_path": tmp_path / "missing.json"})
    with pytest.raises(BackendOutputError, match="no final message"):
        BACKENDS["codex"].extract("", ctx)


def _agy_stream(*results: dict, mode: str | None = "request-review") -> str:
    events = [{"event": "init", "init": {"permission_mode": mode}}]
    events.append({"event": "step_update", "step_update": {"state": "DONE", "text_delta": "partial"}})
    events += [{"event": "result", "result": r} for r in results]
    return "\n".join(json.dumps(e) for e in events) + "\n"


def test_antigravity_extract_reads_the_last_result_event():
    stdout = _agy_stream({"status": "SUCCESS", "response": "R"})
    assert BACKENDS["antigravity"].extract(stdout, CTX) == "R"


@pytest.mark.parametrize("status", ["ERROR", "CANCELED", "INTERRUPTED", "INVALID", "WAITING", None])
def test_antigravity_extract_rejects_a_status_that_is_not_success(status):
    stdout = _agy_stream({"status": status, "response": "R", "error": "quota"})
    with pytest.raises(BackendOutputError, match="antigravity reported status"):
        BACKENDS["antigravity"].extract(stdout, CTX)


@pytest.mark.parametrize("mode", ["request-review", "strict", "proceed-in-sandbox"])
def test_antigravity_extract_accepts_a_read_only_permission_mode(mode):
    stdout = _agy_stream({"status": "SUCCESS", "response": "R"}, mode=mode)
    assert BACKENDS["antigravity"].extract(stdout, CTX) == "R"


@pytest.mark.parametrize("mode", ["always-proceed", "unknown-mode", None])
def test_antigravity_extract_discards_a_run_whose_tools_were_not_read_only(mode):
    # The mode comes from the user's settings: under one that auto-approves
    # tools the review could have changed the tree, so it is not trusted.
    stdout = _agy_stream({"status": "SUCCESS", "response": "R"}, mode=mode)
    with pytest.raises(BackendOutputError, match="permission mode"):
        BACKENDS["antigravity"].extract(stdout, CTX)


def test_antigravity_extract_without_result_event():
    with pytest.raises(BackendOutputError, match="permission mode"):
        BACKENDS["antigravity"].extract("plain text\n", CTX)


def test_antigravity_extract_names_the_tool_whose_denial_ended_the_turn():
    # As captured from agy 1.4.7: a denied run_command ends the turn, still SUCCESS.
    result = {
        "status": "SUCCESS",
        "response": "",
        "denied_actions": [{"action": "command", "display_name": "RunCommand"}],
    }
    with pytest.raises(BackendOutputError, match=r"denied its RunCommand tool.*proceed-in-sandbox"):
        BACKENDS["antigravity"].extract(_agy_stream(result), CTX)


def test_antigravity_extract_empty_response():
    with pytest.raises(BackendOutputError, match="no `response` text"):
        BACKENDS["antigravity"].extract(_agy_stream({"status": "SUCCESS", "response": " \n"}), CTX)


@pytest.mark.parametrize("config", [".agents/hooks.json", ".agents/mcp_config.json", ".agent/hooks.json"])
def test_antigravity_refuses_a_tree_that_carries_executable_workspace_config(tmp_path, config):
    """agy runs workspace hooks and MCP servers: the change under review must not supply them."""
    (tmp_path / config).parent.mkdir(parents=True)
    (tmp_path / config).write_text("{}", encoding="utf-8")
    ctx = RunContext(**{**CTX.__dict__, "repo_dir": tmp_path})
    refuse = BACKENDS["antigravity"].refuse
    assert refuse is not None
    reason = refuse(ctx)
    assert reason is not None and config in reason


def test_antigravity_refuses_a_subdirectory_of_a_tree_with_executable_config(tmp_path):
    # agy can resolve the enclosing repository as its workspace.
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "hooks.json").write_text("{}", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    ctx = RunContext(**{**CTX.__dict__, "repo_dir": tmp_path / "sub"})
    refuse = BACKENDS["antigravity"].refuse
    assert refuse is not None
    reason = refuse(ctx)
    assert reason is not None and ".agents/hooks.json" in reason


def test_antigravity_accepts_a_tree_without_executable_workspace_config(tmp_path):
    (tmp_path / ".agents" / "skills").mkdir(parents=True)
    ctx = RunContext(**{**CTX.__dict__, "repo_dir": tmp_path})
    refuse = BACKENDS["antigravity"].refuse
    assert refuse is not None and refuse(ctx) is None


@pytest.mark.parametrize("name", [n for n in BACKENDS if n not in ("antigravity", "goose")])
def test_other_backends_refuse_nothing(name):
    assert BACKENDS[name].refuse is None


@pytest.mark.parametrize("name", list(BACKENDS))
def test_executable_is_the_binary_the_backend_runs(name):
    """detect probes `executable`; run spawns argv[0]. They must agree."""
    assert BACKENDS[name].executable == BACKENDS[name].build(CTX).argv[0]


def test_claude_extract_unwraps_result():
    assert BACKENDS["claude"].extract(json.dumps({"result": "R", "is_error": False}), CTX) == "R"


def test_claude_extract_is_error():
    with pytest.raises(BackendOutputError, match="claude reported an error"):
        BACKENDS["claude"].extract(json.dumps({"result": "Invalid API key", "is_error": True}), CTX)


def test_grok_extract_unwraps_text():
    assert BACKENDS["grok"].extract(json.dumps({"text": "R", "stopReason": "end_turn"}), CTX) == "R"


@pytest.mark.parametrize("stop", ["refusal", "cancelled", "max_tokens", None])
def test_grok_extract_rejects_a_stop_that_is_not_end_turn(stop):
    with pytest.raises(BackendOutputError, match="did not finish"):
        BACKENDS["grok"].extract(json.dumps({"text": "R", "stopReason": stop}), CTX)


def test_grok_extract_empty_text():
    with pytest.raises(BackendOutputError, match="no `text`"):
        BACKENDS["grok"].extract(json.dumps({"text": "  ", "stopReason": "end_turn"}), CTX)


@pytest.mark.parametrize("name", ["grok", "claude"])
def test_json_envelope_backends_reject_non_json(name):
    with pytest.raises(BackendOutputError, match="not JSON"):
        BACKENDS[name].extract("plain text", CTX)


def test_copilot_extract_is_plain_stdout_but_not_empty():
    assert BACKENDS["copilot"].extract("text", CTX) == "text"
    with pytest.raises(BackendOutputError, match="empty"):
        BACKENDS["copilot"].extract("  \n", CTX)


@pytest.mark.parametrize(
    ("name", "flags"), [("codex", ["-c", "mcp_servers={}"]), ("claude", ["--strict-mcp-config"])]
)
def test_mcp_servers_are_switched_off(name, flags):
    """A reviewer must not inherit the user's MCP tools (Slack, mail, forge writes)."""
    argv = BACKENDS[name].build(CTX).argv
    i = argv.index(flags[0])
    assert argv[i : i + len(flags)] == flags


def test_grok_denies_every_mcp_tool_invocation():
    """Grok cannot close its MCP servers from the CLI; every invocation is denied instead."""
    argv = BACKENDS["grok"].build(CTX).argv
    denied = {argv[i + 1] for i, arg in enumerate(argv) if arg == "--deny"}
    assert "MCPTool" in denied


def test_grok_is_read_only_by_allowlist_not_by_mode():
    """`--permission-mode plan` is accepted by grok but not enforced, so it must not be relied on."""
    argv = BACKENDS["grok"].build(CTX).argv
    assert "--permission-mode" not in argv
    assert argv[argv.index("--tools") + 1] == "read_file,grep,list_dir"
    assert {"--no-subagents", "--disable-web-search"} <= set(argv)
    denied = {argv[i + 1] for i, arg in enumerate(argv) if arg == "--deny"}
    assert {"Bash", "Edit", "Write", "WebFetch"} <= denied
