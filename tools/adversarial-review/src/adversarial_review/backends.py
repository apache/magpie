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
"""
One adapter per reviewer CLI: its headless, read-only command line, how the
harness it belongs to is recognised, and where its final answer sits in its output.

The command lines are this package's security surface. Each one keeps the
reviewer read-only, and none carries the prompt in argv: the diff can exceed
ARG_MAX, so the prompt goes on stdin, or through a brief file for Copilot, whose
`-p` takes text only. `tests/test_backends.py` snapshots every argv and rejects
known write-granting flags, so a regression that drops a read-only flag fails.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COPILOT_INSTRUCTION = (
    "Read the review brief at {brief} and follow it exactly. Change no file and run no command."
)
STDIN_INSTRUCTION = "Follow the review brief given on standard input exactly. Change no file."
CLAUDE_DENIED_TOOLS = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch"


class BackendOutputError(ValueError):
    """The CLI exited 0, but its output carries no usable final answer."""


@dataclass(frozen=True)
class RunContext:
    repo_dir: Path
    prompt: str
    brief_path: Path
    schema_path: Path
    last_message_path: Path
    model: str | None = None


@dataclass(frozen=True)
class Invocation:
    argv: list[str]
    stdin: str | None


@dataclass(frozen=True)
class Backend:
    name: str
    # (environment variable, required value — None means any non-empty value)
    self_markers: tuple[tuple[str, str | None], ...]
    build: Callable[[RunContext], Invocation]
    extract: Callable[[str, RunContext], str]


def _model(flag: str, ctx: RunContext) -> list[str]:
    return [flag, ctx.model] if ctx.model else []


def _json_envelope(stdout: str, what: str) -> dict[str, Any]:
    try:
        data = json.loads(stdout)
    except ValueError as exc:
        raise BackendOutputError(f"{what} output is not JSON: {exc}") from None
    if not isinstance(data, dict):
        raise BackendOutputError(f"{what} output is not a JSON object")
    return data


def _codex(ctx: RunContext) -> Invocation:
    argv = [
        "codex",
        "exec",
        "-s",
        "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "-C",
        str(ctx.repo_dir),
        "--output-schema",
        str(ctx.schema_path),
        "-o",
        str(ctx.last_message_path),
        *_model("-m", ctx),
        "-",
    ]
    return Invocation(argv, stdin=ctx.prompt)


def _codex_extract(stdout: str, ctx: RunContext) -> str:
    try:
        text = ctx.last_message_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise BackendOutputError("codex wrote no final message") from None
    if not text.strip():
        raise BackendOutputError("codex's final message is empty")
    return text


def _copilot(ctx: RunContext) -> Invocation:
    argv = [
        "copilot",
        "-p",
        COPILOT_INSTRUCTION.format(brief=ctx.brief_path),
        "--add-dir",
        str(ctx.brief_path.parent),
        "--deny-tool",
        "shell",
        "--deny-tool",
        "write",
        "--no-color",
        "--log-level",
        "none",
        *_model("--model", ctx),
    ]
    return Invocation(argv, stdin=None)


def _plain_extract(stdout: str, ctx: RunContext) -> str:
    if not stdout.strip():
        raise BackendOutputError("empty reply")
    return stdout


def _gemini(ctx: RunContext) -> Invocation:
    argv = ["gemini", "--approval-mode", "plan", "-o", "json", *_model("-m", ctx), "-p", STDIN_INSTRUCTION]
    return Invocation(argv, stdin=ctx.prompt)


def _gemini_extract(stdout: str, ctx: RunContext) -> str:
    data = _json_envelope(stdout, "gemini")
    if data.get("error"):
        raise BackendOutputError(f"gemini reported an error: {data['error']}")
    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        raise BackendOutputError("gemini output has no `response` text")
    return response


def _claude(ctx: RunContext) -> Invocation:
    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--disallowedTools",
        CLAUDE_DENIED_TOOLS,
        *_model("--model", ctx),
    ]
    return Invocation(argv, stdin=ctx.prompt)


def _claude_extract(stdout: str, ctx: RunContext) -> str:
    data = _json_envelope(stdout, "claude")
    result = data.get("result")
    if data.get("is_error"):
        raise BackendOutputError(f"claude reported an error: {result}")
    if not isinstance(result, str) or not result.strip():
        raise BackendOutputError("claude output has no `result` text")
    return result


# Order matters for self-detection: a harness started from inside another
# inherits the outer one's variables, so the innermost candidates are checked
# first and Claude Code's widely inherited CLAUDECODE comes last.
BACKENDS: dict[str, Backend] = {
    "codex": Backend("codex", (("CODEX_SANDBOX", None), ("CODEX_THREAD_ID", None)), _codex, _codex_extract),
    "copilot": Backend("copilot", (("COPILOT_CLI", None),), _copilot, _plain_extract),
    "gemini": Backend("gemini", (("GEMINI_CLI", "1"),), _gemini, _gemini_extract),
    "claude": Backend("claude", (("CLAUDECODE", "1"),), _claude, _claude_extract),
}
