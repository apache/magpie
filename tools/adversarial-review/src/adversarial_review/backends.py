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
ARG_MAX, so the prompt goes on stdin, or through a brief file for Copilot,
Grok and Goose, whose single-turn flags take text or a path. Goose runs in
chat mode, which gives the model no tools at all. Pi takes it on stdin too, which
it prepends to a short instruction argument, and gets a read-only `--tools`
allowlist, so no shell, edit or MCP tool exists in the session. `tests/test_backends.py` snapshots
every argv and rejects known write-granting flags, so a regression that drops a
read-only flag fails.

Read-only also means no MCP tools: a reviewer inherits the user's MCP servers
(Slack, mail, forge writes) unless told otherwise, and an injected instruction
in the diff could reach them. Codex gets an empty `mcp_servers` table and
Claude `--strict-mcp-config` with no config. Grok cannot close its MCP servers
from the CLI, so `--deny MCPTool` auto-denies every MCP tool invocation
instead. Copilot and Antigravity expose no equivalent switch in the versions
this was written against; the README says so.

Antigravity reads its prompt from stdin only in `stream-json` input mode. It
also loads workspace hooks and MCP servers from the reviewed tree's `.agents/`
directory, which would run code the change under review supplies, so it
refuses such a tree instead of reviewing it.

Grok's `--permission-mode plan` is not used: grok accepts it for compatibility
but wires only `bypassPermissions` at spawn, so it would restrict nothing.
Grok is kept read-only by an explicit tool allowlist instead, with deny rules
behind it in case the allowlist is ever loosened.
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
PI_INSTRUCTION = "Follow the review brief above exactly. Change no file."
PI_READ_ONLY_TOOLS = "read,grep,find,ls"
CLAUDE_DENIED_TOOLS = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,Task"
# Grok's read-only built-in tools. `--tools` removes everything else, including
# the shell and the edit tools, but keeps the MCP meta-tools unless denied.
GROK_ALLOWED_TOOLS = "read_file,grep,list_dir"
# Bare permission-rule prefixes match every invocation of that tool class.
# MCPTool covers the MCP tools the CLI cannot disconnect; the rest back up the
# allowlist.
GROK_DENIED_TOOLS = ("Bash", "Edit", "Write", "WebFetch", "MCPTool")


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
    # Variables set for this reviewer on top of the caller's environment.
    env: dict[str, str] | None = None
    # The reviewer's working directory, when it is not the reviewed tree.
    cwd: Path | None = None


@dataclass(frozen=True)
class Backend:
    name: str
    # (environment variable, required value — None means any non-empty value)
    self_markers: tuple[tuple[str, str | None], ...]
    build: Callable[[RunContext], Invocation]
    extract: Callable[[str, RunContext], str]
    # Why this reviewer must not run on ctx.repo_dir, or None when it may.
    refuse: Callable[[RunContext], str | None] | None = None
    # The CLI's executable, when it is not named after the backend.
    cli: str = ""

    @property
    def executable(self) -> str:
        return self.cli or self.name


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
        "-c",
        "mcp_servers={}",
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


def _pi(ctx: RunContext) -> Invocation:
    # `--tools` is an allowlist, so the reviewer has the four read tools and
    # nothing else: no bash, no edit or write, no MCP or extension tools.
    # `--no-approve` ignores the reviewed tree's `.pi/` (settings, extensions,
    # packages), which would otherwise be code the change under review supplies.
    # Pi prepends piped stdin to the first prompt.
    argv = [
        "pi",
        "-p",
        "--no-session",
        "--no-approve",
        "--tools",
        PI_READ_ONLY_TOOLS,
        *_model("--model", ctx),
        PI_INSTRUCTION,
    ]
    return Invocation(argv, stdin=ctx.prompt)


def _plain_extract(stdout: str, ctx: RunContext) -> str:
    if not stdout.strip():
        raise BackendOutputError("empty reply")
    return stdout


# Workspace files Antigravity acts on by itself: hooks run shell commands and
# MCP configs start servers. `.agent/` is its legacy spelling of `.agents/`.
ANTIGRAVITY_EXECUTABLE_CONFIG = tuple(
    f"{d}/{f}" for d in (".agents", ".agent") for f in ("hooks.json", "mcp_config.json")
)


#: Appended to the prompt agy gets. Headless agy cannot ask for approval, and
#: the first tool it denies ends the whole turn with an empty response, so a
#: reviewer that reaches for a shell command loses its review. Asked to list
#: or search, agy also hands the work to a research subagent, which headless
#: mode does not wait for: the turn ends on "waiting for the subagent". And
#: told only "file reads", it reads directories file by file. So the note
#: names the tools that work.
ANTIGRAVITY_TOOL_NOTE = (
    "\n\nUse only these tools: list_dir to list a directory, find_by_name to find files, "
    "grep_search to search text, and view_file or read_file to read a file. "
    "Do not run shell commands, fetch URLs or call MCP tools: "
    "this run cannot approve them, and a denied tool ends the review with no answer. "
    "Do not start or define subagents: this run ends before a subagent reports back, "
    "so its work is lost.\n"
)

#: Step types and tools that hand the turn to a subagent.
ANTIGRAVITY_SUBAGENT_TOOLS = frozenset({"invoke_subagent", "define_subagent", "manage_subagents"})


def _antigravity(ctx: RunContext) -> Invocation:
    # No --dangerously-skip-permissions: headless agy denies every tool that
    # needs approval, so plan mode under request-review stays read-only.
    argv = [
        "agy",
        "--mode",
        "plan",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        # 0 waits for the turn to finish: the runner's timeout decides, where
        # agy's own would return a partial answer still marked SUCCESS.
        "--print-timeout",
        "0",
        *_model("--model", ctx),
    ]
    message = {"event": "user", "message": {"content": ctx.prompt + ANTIGRAVITY_TOOL_NOTE}}
    return Invocation(argv, stdin=json.dumps(message) + "\n")


#: Permission modes a review may run under. agy takes the mode only from
#: settings. Under request-review and strict, headless agy denies every
#: shell, write and web tool, and ends the turn at the first one;
#: proceed-in-sandbox (Magpie's own profile) also runs sandboxed commands, which reach no network and write only inside the
#: exported tree under review. always-proceed approves everything.
ANTIGRAVITY_READ_ONLY_MODES = ("request-review", "strict", "proceed-in-sandbox")


def _antigravity_extract(stdout: str, ctx: RunContext) -> str:
    result = None
    mode = None
    subagent = False
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("event") == "init" and isinstance(event.get("init"), dict):
            mode = event["init"].get("permission_mode")
        if (
            isinstance(event, dict)
            and event.get("event") == "step_update"
            and isinstance(event.get("step_update"), dict)
        ):
            step = event["step_update"]
            if step.get("step_type") == "subagent" or step.get("tool_name") in ANTIGRAVITY_SUBAGENT_TOOLS:
                subagent = True
        if isinstance(event, dict) and event.get("event") == "result":
            result = event.get("result")
    # The mode comes from the user's settings, not this command line, so a
    # review run under a mode that auto-approves tools is discarded. The
    # check is after the fact: say so, so the user inspects the tree.
    if mode not in ANTIGRAVITY_READ_ONLY_MODES:
        raise BackendOutputError(
            f"agy ran with permission mode {mode!r}, not one of {', '.join(ANTIGRAVITY_READ_ONLY_MODES)}: "
            "its tools were not confined, so the review is discarded; check the reviewed tree and "
            "set toolPermission in ~/.gemini/antigravity-cli/settings.json"
        )
    if not isinstance(result, dict):
        raise BackendOutputError("antigravity output has no `result` event")
    status = result.get("status")
    if status != "SUCCESS":
        raise BackendOutputError(f"antigravity reported status {status!r}: {result.get('error')}")
    response = result.get("response")
    if subagent:
        # Whatever came back was written before the subagent reported: at
        # best a "waiting for the subagent" note, never the review.
        raise BackendOutputError(
            "agy handed the review to a subagent, and headless mode ends the turn before a subagent "
            "reports back, so there is no review"
        )
    if not isinstance(response, str) or not response.strip():
        denied = [
            str(d.get("display_name") or d.get("action"))
            for d in result.get("denied_actions") or []
            if isinstance(d, dict) and (d.get("display_name") or d.get("action"))
        ]
        if denied:
            raise BackendOutputError(
                f"agy ended without an answer after headless mode denied its {', '.join(denied)} tool; "
                "toolPermission proceed-in-sandbox in ~/.gemini/antigravity-cli/settings.json "
                "lets it run commands inside the terminal sandbox"
            )
        raise BackendOutputError("antigravity output has no `response` text")
    return response


def _antigravity_refuse(ctx: RunContext) -> str | None:
    # agy may take an enclosing directory (a git root) as the workspace, so a
    # config in any ancestor would run as well.
    root = ctx.repo_dir.resolve()
    found = [
        str(d / rel)
        for d in (root, *root.parents)
        for rel in ANTIGRAVITY_EXECUTABLE_CONFIG
        if (d / rel).exists()
    ]
    if found:
        return f"the reviewed tree has {', '.join(found)}, which agy would execute"
    return None


def _goose(ctx: RunContext) -> Invocation:
    # GOOSE_MODE=chat runs the model with no tools at all, so the reviewer can
    # read only the brief. `--no-profile` skips the user's configured
    # extensions, so no MCP server starts either. The brief goes in as the
    # instructions file: `-i` takes a path, and a diff can exceed ARG_MAX.
    argv = [
        "goose",
        "run",
        "--no-session",
        "--no-profile",
        "--quiet",
        *_model("--model", ctx),
        "-i",
        str(ctx.brief_path),
    ]
    # Run from the brief's own directory, not the reviewed tree: a chat-only
    # reviewer needs no files, and Goose would otherwise load the tree's
    # project plugins, hooks and context files from its working directory.
    return Invocation(argv, stdin=None, env={"GOOSE_MODE": "chat"}, cwd=ctx.brief_path.parent)


def _claude(ctx: RunContext) -> Invocation:
    argv = [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--strict-mcp-config",
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


def _grok(ctx: RunContext) -> Invocation:
    # No shell, edit, web or subagent tools: subagents escape the parent's
    # gates, and web search runs unprompted, which makes it an egress channel.
    argv = [
        "grok",
        "--tools",
        GROK_ALLOWED_TOOLS,
        "--no-subagents",
        "--disable-web-search",
        *(arg for tool in GROK_DENIED_TOOLS for arg in ("--deny", tool)),
        "--output-format",
        "json",
        "--prompt-file",
        str(ctx.brief_path),
        *_model("-m", ctx),
    ]
    return Invocation(argv, stdin=None)


def _grok_extract(stdout: str, ctx: RunContext) -> str:
    data = _json_envelope(stdout, "grok")
    stop = data.get("stopReason")
    if stop != "end_turn":
        raise BackendOutputError(f"grok did not finish its review (stopReason {stop!r})")
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise BackendOutputError("grok output has no `text`")
    return text


# Order matters for self-detection: a harness started from inside another
# inherits the outer one's variables, so the innermost candidates are checked
# first and Claude Code's widely inherited CLAUDECODE comes last.
BACKENDS: dict[str, Backend] = {
    "codex": Backend("codex", (("CODEX_SANDBOX", None), ("CODEX_THREAD_ID", None)), _codex, _codex_extract),
    "copilot": Backend("copilot", (("COPILOT_CLI", None),), _copilot, _plain_extract),
    "antigravity": Backend(
        "antigravity",
        (("ANTIGRAVITY_CONVERSATION_ID", None),),
        _antigravity,
        _antigravity_extract,
        _antigravity_refuse,
        cli="agy",
    ),
    "pi": Backend("pi", (("PI_SESSION_ID", None),), _pi, _plain_extract),
    "grok": Backend("grok", (("GROK_SESSION_ID", None),), _grok, _grok_extract),
    # Goose's marker has a generic name, so it is checked after every
    # harness-specific one, just before Claude Code's widely inherited one.
    "goose": Backend("goose", (("AGENT_SESSION_ID", None),), _goose, _plain_extract),
    "claude": Backend("claude", (("CLAUDECODE", "1"),), _claude, _claude_extract),
}
