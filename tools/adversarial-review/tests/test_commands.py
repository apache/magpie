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
import tomllib
from pathlib import Path

import pytest

from adversarial_review import main
from adversarial_review.commands import HARNESSES, render

ROOT = "/plugins/magpie-adversarial-review/0.2.0"


def test_harness_set():
    assert list(HARNESSES) == ["claude", "codex", "gemini", "copilot"]


def test_claude_command_uses_the_plugin_root_variable():
    path, content = render("claude", ROOT)
    assert path == "commands/adversarial-review.md"
    assert content.startswith("---\n# SPDX-License-Identifier: Apache-2.0\n")
    assert 'uvx --from "${CLAUDE_PLUGIN_ROOT}/tools/adversarial-review" adversarial-review run' in content
    assert "$ARGUMENTS" in content
    assert ROOT not in content  # shipped in the plugin: must not pin one install's path


def test_codex_prompt():
    path, content = render("codex", ROOT)
    assert path == "~/.codex/prompts/magpie-adversarial-review.md"
    assert f'uvx --from "{ROOT}/tools/adversarial-review" adversarial-review run' in content
    assert "$ARGUMENTS" in content


def test_gemini_command_is_valid_toml():
    path, content = render("gemini", ROOT)
    assert path == ".gemini/commands/magpie-adversarial-review.toml"
    data = tomllib.loads(content)
    assert set(data) == {"description", "prompt"}
    assert "{{args}}" in data["prompt"] and f"{ROOT}/tools/adversarial-review" in data["prompt"]
    assert (
        "!{" not in data["prompt"]
    )  # the agent runs it through its own shell tool, under its own permissions


def test_copilot_has_no_command_file_only_the_invocation():
    path, content = render("copilot", ROOT)
    assert path == ""
    assert content == f'uvx --from "{ROOT}/tools/adversarial-review" adversarial-review run --target branch\n'


@pytest.mark.parametrize("harness", ["claude", "codex", "gemini"])
def test_every_command_treats_findings_as_untrusted_and_runs_one_line(harness):
    _, content = render(harness, ROOT)
    assert "untrusted" in content
    assert "one line" in content
    assert "--reviewers" not in content  # the configured list decides, never a hard-coded one


def test_commands_subcommand_prints_json(capsys):
    assert main(["commands", "--harness", "codex", "--plugin-root", ROOT], env={}) == 0
    out = json.loads(capsys.readouterr().out)
    assert (
        out["path"] == "~/.codex/prompts/magpie-adversarial-review.md"
        and "adversarial-review run" in out["content"]
    )


def test_commands_subcommand_rejects_unknown_harness(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["commands", "--harness", "vim", "--plugin-root", ROOT], env={})
    assert exc.value.code == 2


SHIPPED = Path(__file__).resolve().parents[1] / "commands" / "adversarial-review.md"


def test_the_shipped_claude_command_is_the_generated_one():
    """The plugin publishes this file as its Claude Code command. Regenerate it with
    `python -m adversarial_review commands --harness claude --plugin-root .` (the `content` field)."""
    assert SHIPPED.read_text(encoding="utf-8") == render("claude", "")[1]
