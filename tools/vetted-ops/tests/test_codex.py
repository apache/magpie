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
"""Exercise generated read/write prefixes with Codex's own rule evaluator."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vetted_ops.codex import main, render_rules


def test_rules_keep_stable_path_and_never_allow_writes(tmp_path: Path) -> None:
    target = tmp_path / "versioned-install"
    target.mkdir()
    stable = tmp_path / "stable path"
    stable.symlink_to(target, target_is_directory=True)
    text = render_rules(stable)
    assert str(target) not in text
    assert text.count('decision = "allow"') == 2
    assert text.count('decision = "prompt"') == 4
    assert str(stable) in text


def test_relative_path_refused() -> None:
    with pytest.raises(ValueError, match="absolute"):
        render_rules(Path("repo/tools/vetted-ops"))


def test_cli_prints_without_installing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    absent = tmp_path / "not-created"
    assert main(["--tool-root", str(absent)]) == 0
    assert str(absent) in capsys.readouterr().out
    assert not absent.exists()


@pytest.mark.skipif(shutil.which("codex") is None, reason="native Codex evaluator unavailable")
@pytest.mark.parametrize("launcher", [("uv", "run", "--project"), ("uvx", "--from")])
@pytest.mark.parametrize(
    "entry,decision",
    [("vetted-op-read", "allow"), ("vetted-op", "prompt"), ("vetted-op-tracker", "prompt"), ("python", None)],
)
def test_native_classification(
    tmp_path: Path, launcher: tuple[str, ...], entry: str, decision: str | None
) -> None:
    base = tmp_path / "installed tool"
    rules = tmp_path / "vetted.rules"
    rules.write_text(render_rules(base))
    command = [*launcher, str(base), entry, "--caller", "test", "viewer"]
    proc = subprocess.run(
        ["codex", "execpolicy", "check", "--rules", str(rules), "--", *command],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(proc.stdout).get("decision") == decision


@pytest.mark.skipif(shutil.which("codex") is None, reason="native Codex evaluator unavailable")
@pytest.mark.parametrize(
    "command",
    [
        ["uv", "run", "--with", "untrusted", "--project", "BASE", "vetted-op-read"],
        ["uvx", "--from", "BASE", "--with", "untrusted", "vetted-op-read"],
        ["uv", "run", "--project", "BASE/other", "vetted-op-read"],
    ],
)
def test_extra_launcher_flags_and_other_paths_are_not_allowed(tmp_path: Path, command: list[str]) -> None:
    rules = tmp_path / "vetted.rules"
    rules.write_text(render_rules(tmp_path))
    command = [word.replace("BASE", str(tmp_path)) for word in command]
    proc = subprocess.run(
        ["codex", "execpolicy", "check", "--rules", str(rules), "--", *command],
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(proc.stdout).get("decision") is None
