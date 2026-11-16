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
"""The Vulnogram CVE-tool operations: fixed argv, stdin record, scrubbed env."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vetted_ops import cli, config, cve_tool, ops

POLICY = """\
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[callers]
"security-cve-allocate" = ["cve-record-fetch", "cve-record-update", "cve-allocate"]
"""

CVE = "CVE-2026-12345"


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "scratch"
    ws.mkdir()
    ws.chmod(0o700)
    return ws


@pytest.fixture()
def policy_path(tmp_path: Path, workspace: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(POLICY.format(workspace=workspace))
    return path


@pytest.fixture()
def policy(policy_path: Path) -> config.Config:
    return config.load(policy_path)


def _prefix() -> list[str]:
    return [cve_tool.uv_executable(), "run", "--quiet", "--project", str(cve_tool.tool_dir())]


def test_the_client_is_the_one_shipped_beside_vetted_ops() -> None:
    """From the source tree the client is the sibling tools/cve-tool-vulnogram/oauth-api."""
    here = Path(cve_tool.__file__).resolve()
    assert cve_tool.tool_dir() == here.parents[3] / "cve-tool-vulnogram" / "oauth-api"
    assert (cve_tool.tool_dir() / "pyproject.toml").is_file()


def test_fetch_runs_the_record_fetch_command_with_only_the_id(policy: config.Config) -> None:
    op = ops.resolve("cve-record-fetch")
    assert not op.writes
    params, body = cli._validate_params(op, [CVE], policy)
    assert body is None
    assert cli.build_argv(op, params, policy) == [*_prefix(), "vulnogram-api-record-fetch", "--cve-id", CVE]


def test_update_pipes_the_validated_record_on_stdin(policy: config.Config, workspace: Path) -> None:
    """The client reads `-`, so the bytes vetted-ops read are the bytes pushed."""
    record = workspace / "cve.json"
    record.write_text('{"dataType": "CVE_RECORD"}')
    op = ops.resolve("cve-record-update")
    assert op.writes
    params, body = cli._validate_params(op, [CVE, str(record)], policy)
    assert body == b'{"dataType": "CVE_RECORD"}'
    assert cli.build_argv(op, params, policy) == [
        *_prefix(),
        "vulnogram-api-record-update",
        "--cve-id",
        CVE,
        "--json-file",
        "-",
    ]


def test_update_refuses_a_record_outside_the_workspace(policy: config.Config, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}")
    with pytest.raises(ops.ParamError):
        cli._validate_params(ops.resolve("cve-record-update"), [CVE, str(outside)], policy)


def test_allocate_reads_its_title_from_a_workspace_file(policy: config.Config, workspace: Path) -> None:
    title = workspace / "title.txt"
    title.write_text("Config API: section aliases bypass masking\n")
    op = ops.resolve("cve-allocate")
    assert op.writes
    params, _ = cli._validate_params(op, [str(title)], policy)
    assert cli.build_argv(op, params, policy) == [
        *_prefix(),
        "vulnogram-api-allocate",
        "--title",
        "Config API: section aliases bypass masking",
    ]


@pytest.mark.parametrize(
    "bad", ["CVE-2026-1", "cve-2026-12345", "CVE-2026-12345 --allow-state-downgrade", "--credentials"]
)
def test_a_malformed_cve_id_never_reaches_the_client(policy: config.Config, bad: str) -> None:
    with pytest.raises(ops.ParamError):
        cli._validate_params(ops.resolve("cve-record-fetch"), [bad], policy)


def test_no_override_flag_is_reachable() -> None:
    """The caller's values are the only variable parts; no `--allow-*` / `--credentials`."""
    for name in ("cve-record-fetch", "cve-record-update", "cve-allocate"):
        assert set(ops.resolve(name).params) <= {"cve_id", "body", "title"}


def test_a_tampered_argv_is_refused(policy: config.Config) -> None:
    assert Path(cve_tool.uv_executable()).is_absolute()
    assert not cve_tool.is_cve_tool_argv(
        ["uv", "run", "--quiet", "--project", str(cve_tool.tool_dir()), "vulnogram-api-record-fetch"]
    )
    assert not cve_tool.is_cve_tool_argv(
        [cve_tool.uv_executable(), "run", "--quiet", "--project", "/tmp/evil", "x"]
    )
    assert not cve_tool.is_cve_tool_argv([*_prefix(), "vulnogram-api-record-publish"])
    assert cve_tool.is_cve_tool_argv([*_prefix(), "vulnogram-api-record-fetch", "--cve-id", CVE])


@pytest.mark.parametrize(
    "name",
    [
        "VULNOGRAM_SESSION",  # an agent-written session file names its own host
        "VULNOGRAM_ALLOCATE_SESSION",
        "PYTHONPATH",  # would load modules into the out-of-sandbox interpreter
        "PYTHONSTARTUP",
        "UV_INDEX_URL",  # would fetch the build backend from another index
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
        "DYLD_INSERT_LIBRARIES",
        "LD_PRELOAD",
        "HTTPS_PROXY",
        "SOME_UNRELATED_VAR",
    ],
)
def test_the_child_environment_is_an_allowlist(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "/tmp/agent-controlled")
    assert name not in cve_tool.child_env()


def test_the_child_keeps_locale_and_gets_a_trusted_home_and_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from vetted_ops.config import account_home

    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    monkeypatch.setenv("PATH", f"/tmp/evil-bin{os.pathsep}{os.environ['PATH']}")
    env = cve_tool.child_env()
    assert env["LANG"] == "en_US.UTF-8"
    assert env["HOME"] == str(account_home())
    assert "/tmp/evil-bin" not in env["PATH"].split(os.pathsep)
    assert env["PATH"].split(os.pathsep)[0] == str(Path(cve_tool.uv_executable()).parent)


def test_writes_are_unreachable_from_the_read_only_entry_point() -> None:
    assert cli._entry_point_admits(ops.resolve("cve-record-fetch"), read_only=True, tracker_only=False)
    for name in ("cve-record-update", "cve-allocate"):
        assert not cli._entry_point_admits(ops.resolve(name), read_only=True, tracker_only=False)


def test_the_read_runs_with_the_scrubbed_env_and_no_shell(
    policy_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen["command"] = command
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setenv("VULNOGRAM_SESSION", "/tmp/agent-session.json")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    code = cli.main_read(
        ["--caller", "security-cve-allocate", "cve-record-fetch", CVE, "--config", str(policy_path)]
    )
    assert code == 0
    assert seen["command"] == [*_prefix(), "vulnogram-api-record-fetch", "--cve-id", CVE]
    assert "VULNOGRAM_SESSION" not in seen["env"]
    assert "shell" not in seen


def test_a_dry_run_shows_the_title_only_as_its_size(
    policy_path: Path, workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    title = workspace / "title.txt"
    title.write_text("Embargoed title\n")
    code = cli.main(
        [
            "--caller",
            "security-cve-allocate",
            "--dry-run",
            "cve-allocate",
            str(title),
            "--config",
            str(policy_path),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Embargoed title" not in out
    assert "<from file, 15 chars>" in out
