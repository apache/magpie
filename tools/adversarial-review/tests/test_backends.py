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

from adversarial_review.backends import BACKENDS, BackendOutputError, RunContext

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
}


def test_backend_set_and_order():
    assert list(BACKENDS) == ["codex", "copilot", "gemini", "claude"]


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


def test_gemini_argv():
    inv = BACKENDS["gemini"].build(CTX)
    assert inv.argv == [
        "gemini",
        "--approval-mode",
        "plan",
        "-o",
        "json",
        "-p",
        "Follow the review brief given on standard input exactly. Change no file.",
    ]
    assert inv.stdin == "PROMPT"


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
    ("name", "flag"), [("codex", "-m"), ("copilot", "--model"), ("gemini", "-m"), ("claude", "--model")]
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


def test_gemini_extract_unwraps_response():
    assert BACKENDS["gemini"].extract(json.dumps({"response": "R"}), CTX) == "R"


def test_gemini_extract_error_envelope():
    with pytest.raises(BackendOutputError, match="gemini reported an error"):
        BACKENDS["gemini"].extract(json.dumps({"error": {"message": "quota"}}), CTX)


def test_claude_extract_unwraps_result():
    assert BACKENDS["claude"].extract(json.dumps({"result": "R", "is_error": False}), CTX) == "R"


def test_claude_extract_is_error():
    with pytest.raises(BackendOutputError, match="claude reported an error"):
        BACKENDS["claude"].extract(json.dumps({"result": "Invalid API key", "is_error": True}), CTX)


@pytest.mark.parametrize("name", ["gemini", "claude"])
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
