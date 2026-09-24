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

import fnmatch
import json
import re
import tomllib
from pathlib import Path

import pytest

from adversarial_review import main
from adversarial_review.commands import HARNESSES, PLUGIN_DIR, render

REPO = Path(__file__).resolve().parents[3]
SHIPPED = Path(__file__).resolve().parents[1] / "commands" / "adversarial-review.md"


def _invocation_line(content: str) -> str:
    return next(line.strip() for line in content.splitlines() if line.strip().startswith("uvx --from "))


def test_harness_set():
    assert list(HARNESSES) == ["claude", "codex", "gemini", "copilot"]


def test_claude_command_reads_the_version_from_the_plugin_root():
    path, content = render("claude")
    assert path == "commands/adversarial-review.md"
    assert content.startswith("---\n# SPDX-License-Identifier: Apache-2.0\n")
    assert "$ARGUMENTS" in content and "${CLAUDE_PLUGIN_ROOT}" in content
    assert "unquoted and with a literal `~`" in content


def test_codex_prompt():
    path, content = render("codex")
    assert path == "~/.codex/prompts/magpie-adversarial-review.md"
    assert "$ARGUMENTS" in content and f"newest directory under `{PLUGIN_DIR}/`" in content
    assert "outside it" in content  # the sandbox-escalation hint for Codex's no-network default


def test_gemini_command_is_valid_toml():
    path, content = render("gemini")
    assert path == "~/.gemini/commands/magpie-adversarial-review.toml"
    data = tomllib.loads(content)
    assert set(data) == {"description", "prompt"}
    assert "{{args}}" in data["prompt"]
    assert (
        "!{" not in data["prompt"]
    )  # the agent runs it through its own shell tool, under its own permissions


def test_copilot_has_no_command_file_only_the_invocation():
    path, content = render("copilot")
    assert path == ""
    assert content.startswith(
        f"uvx --from {PLUGIN_DIR}/<version>/tools/adversarial-review adversarial-review run"
    )


def test_no_command_bakes_in_a_version_or_quotes_the_path():
    """A baked-in version goes stale on upgrade; a quoted or expanded path never
    matches the sandbox exclusion."""
    for harness in HARNESSES:
        line = _invocation_line(render(harness)[1])
        assert "/<version>/" in line
        assert '"' not in line.split(" adversarial-review run")[0]


@pytest.mark.parametrize("harness", HARNESSES)
def test_the_invocation_matches_the_sandbox_exclusion(harness):
    excluded = json.loads((REPO / "tools" / "sandbox-lint" / "expected.json").read_text())["sandbox"][
        "excludedCommands"
    ]
    [pattern] = [p for p in excluded if "adversarial-review" in p]
    line = _invocation_line(render(harness)[1]).replace("<version>", "0.2.0.dev202609240000")
    line = re.sub(r"<target>", "branch", line)
    assert fnmatch.fnmatchcase(line, pattern), (line, pattern)


@pytest.mark.parametrize("harness", ["claude", "codex", "gemini"])
def test_every_command_treats_findings_as_untrusted_and_runs_one_line(harness):
    _, content = render(harness)
    assert "untrusted" in content
    assert "one line" in content
    assert "--reviewers" not in content  # the configured list decides, never a hard-coded one


def test_commands_subcommand_prints_json(capsys):
    assert main(["commands", "--harness", "codex"], env={}) == 0
    out = json.loads(capsys.readouterr().out)
    assert (
        out["path"] == "~/.codex/prompts/magpie-adversarial-review.md"
        and "adversarial-review run" in out["content"]
    )


def test_commands_subcommand_takes_another_plugin_dir(capsys):
    assert main(["commands", "--harness", "copilot", "--plugin-dir", "/opt/magpie-ar"], env={}) == 0
    assert (
        "/opt/magpie-ar/<version>/tools/adversarial-review" in json.loads(capsys.readouterr().out)["content"]
    )


def test_commands_subcommand_rejects_unknown_harness():
    with pytest.raises(SystemExit) as exc:
        main(["commands", "--harness", "vim"], env={})
    assert exc.value.code == 2


def test_the_shipped_claude_command_is_the_generated_one():
    """The plugin publishes this file as its Claude Code command. Regenerate it with
    `python -m adversarial_review commands --harness claude` (the `content` field)."""
    assert SHIPPED.read_text(encoding="utf-8") == render("claude")[1]
