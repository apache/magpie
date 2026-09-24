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

import pytest

from adversarial_review import main
from adversarial_review.detect import detect, resolve_self, running_harness


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, None),
        ({"CLAUDECODE": "1"}, "claude"),
        ({"CLAUDECODE": "0"}, None),
        ({"GEMINI_CLI": "1"}, "gemini"),
        ({"CODEX_SANDBOX": "seatbelt"}, "codex"),
        ({"CODEX_THREAD_ID": "abc"}, "codex"),
        ({"COPILOT_CLI": "1"}, "copilot"),
        ({"CLAUDECODE": "1", "CODEX_SANDBOX": "seatbelt"}, "codex"),  # codex started inside Claude Code
    ],
)
def test_running_harness(env, expected):
    assert running_harness(env) == expected


def test_leaked_companion_vars_do_not_mark_codex():
    env = {"CLAUDECODE": "1", "CODEX_COMPANION_SESSION_ID": "x", "CODEX_COMPANION_TRANSCRIPT_PATH": "/x"}
    assert running_harness(env) == "claude"


def test_resolve_self_override():
    assert resolve_self("none", {"CLAUDECODE": "1"}) is None
    assert resolve_self("gemini", {"CLAUDECODE": "1"}) == "gemini"
    assert resolve_self(None, {"CLAUDECODE": "1"}) == "claude"
    with pytest.raises(ValueError, match="unknown harness"):
        resolve_self("vim", {})


def test_detect_with_stub_path(stub_bin):
    bin_dir, make = stub_bin
    make("codex", 'print("codex-cli 0.154.0")')
    make("gemini", 'import sys; sys.stderr.write("boom\\n"); sys.exit(1)')
    make("claude", 'print("2.1.0 (Claude Code)")')
    rows = {d.name: d for d in detect({"PATH": str(bin_dir)}, self_name="claude")}
    assert list(rows) == ["codex", "copilot", "gemini", "claude"]
    assert rows["codex"].available and rows["codex"].version == "codex-cli 0.154.0"
    assert not rows["codex"].is_self
    assert not rows["copilot"].available and rows["copilot"].reason == "not on PATH"
    assert not rows["gemini"].available and "`--version` failed (exit 1): boom" in rows["gemini"].reason
    assert rows["claude"].available and rows["claude"].is_self


def test_detect_probe_timeout(stub_bin):
    bin_dir, make = stub_bin
    make("codex", "import time; time.sleep(5)")
    row = next(d for d in detect({"PATH": str(bin_dir)}, None, probe_timeout=0.5) if d.name == "codex")
    assert not row.available and "timed out" in row.reason


def test_detect_subcommand_prints_json(stub_bin, capsys):
    bin_dir, make = stub_bin
    make("codex", 'print("codex-cli 0.154.0")')
    assert main(["detect"], env={"PATH": str(bin_dir), "CLAUDECODE": "1"}) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["self"] == "claude"
    assert [b["name"] for b in out["backends"]] == ["codex", "copilot", "gemini", "claude"]


def test_detect_subcommand_rejects_unknown_self(capsys):
    assert main(["detect", "--self", "vim"], env={"PATH": ""}) == 2
    assert "unknown harness" in capsys.readouterr().err
