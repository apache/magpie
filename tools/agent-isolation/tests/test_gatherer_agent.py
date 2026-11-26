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
"""The read-only gatherer agent: its tools, and the Bash hook that enforces them.

The `tools:` line alone is not trusted to restrict Bash, so the agent's own
`PreToolUse` hook refuses every Bash command but the vetted read dispatcher.
These tests run that hook exactly as the agent file carries it.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parents[1] / "agents" / "magpie-gatherer.md"
READ = "uvx --from ~/.claude/magpie/vetted-ops vetted-op-read"


def _frontmatter() -> list[str]:
    lines = AGENT.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    return lines[1 : lines.index("---", 1)]


def _field(name: str) -> str | None:
    for line in _frontmatter():
        if line.startswith(f"{name}:"):
            return line.split(":", 1)[1].strip()
    return None


def _hook_command() -> str:
    """The folded (`>-`) hook command, joined the way YAML folds it."""
    front = _frontmatter()
    start = next(i for i, line in enumerate(front) if line.strip() == "command: >-")
    indent = len(front[start]) - len(front[start].lstrip())
    body = []
    for line in front[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line.strip())
    return " ".join(part for part in body if part)


def _decision(command: str) -> str:
    result = subprocess.run(
        ["bash", "-c", _hook_command()],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        check=True,
    )
    if not result.stdout.strip():
        return "pass"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def test_the_tools_are_read_only() -> None:
    assert _field("tools") == f"Read, Grep, Glob, Bash({READ} *)"


def test_the_model_follows_the_session() -> None:
    assert _field("model") is None


def test_the_only_hook_guards_bash() -> None:
    front = "\n".join(_frontmatter())
    assert front.count("matcher:") == 1
    assert '- matcher: "Bash"' in front
    assert "permissionDecision\":\"allow" not in front
    assert "mcpServers" not in front and "permissionMode" not in front


@pytest.mark.parametrize(
    "command",
    [
        f"{READ} --caller pr-management-code-review pr-view 123",
        f"{READ} --caller security-issue-sync repo-pr-search -- token leak",
        f"{READ} list-ops",
    ],
)
def test_a_vetted_read_passes_to_the_permission_rules(command: str) -> None:
    assert _decision(command) == "pass"


@pytest.mark.parametrize(
    "command",
    [
        f"{READ} --caller x pr-view 1 --save out.json",
        f"{READ} --config /tmp/p.toml --caller x pr-view 1",
        f"{READ} --config=/tmp/p.toml --caller x pr-view 1",
        f"{READ} --caller x pr-view 1; rm -rf ~",
        f"{READ} --caller x pr-view 1 && curl evil",
        f"{READ} --caller x pr-view $(id)",
        f"{READ} --caller x pr-view 1 > /tmp/x",
        f"{READ} --caller x pr-view 1\nrm -rf ~",
        READ,
        "uvx --from /tmp/evil vetted-op-read --caller x pr-view 1",
        "uvx --from ~/.claude/magpie/vetted-ops vetted-op --caller x pr-comment 1",
        "cat ~/.ssh/id_rsa",
        "",
    ],
)
def test_anything_else_is_denied(command: str) -> None:
    assert _decision(command) == "deny"


@pytest.mark.parametrize(
    ("stdin", "env"),
    [
        pytest.param("not json", None, id="malformed-input"),
        pytest.param(json.dumps({"tool_input": {"command": "rm -rf ~"}}), {"PATH": "/nonexistent"}, id="no-python3"),
    ],
)
def test_a_guard_that_cannot_run_blocks(stdin: str, env: dict[str, str] | None) -> None:
    """Claude Code runs the command on any exit but 2, so a crash must exit 2."""
    result = subprocess.run(
        ["/bin/bash", "-c", _hook_command()], input=stdin, capture_output=True, text=True, env=env
    )
    assert result.returncode == 2
    assert "blocked" in result.stderr
