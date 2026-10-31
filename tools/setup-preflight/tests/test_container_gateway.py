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

"""When the pre-flight reports container-gateway hooks Claude Code never loads, as tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from setup_preflight import gateway, sections
from setup_preflight.core import container_gateway_findings

SCRIPT = "/home/alice/.claude/scripts/container-gateway-hook.sh"


def hooks(action: str = "start") -> dict:
    return {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": f"{SCRIPT} {action}"}]}]}}


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def wire(project: Path) -> Path:
    """Point the project's container CLIs at its gateway socket, as the install does."""
    sock = project / ".apache-magpie-local" / "run" / "docker.sock"
    write(project / ".claude" / "settings.local.json", {"env": {"DOCKER_HOST": f"unix://{sock}"}})
    return sock


@pytest.fixture
def managed(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A managed-settings directory of the test's own instead of the machine's."""
    directory = tmp_path_factory.mktemp("managed")
    monkeypatch.setattr(gateway, "MANAGED_SETTINGS_DIRS", (directory,))
    return directory


def test_a_project_not_wired_for_the_gateway_is_never_told(project: Path, managed: Path) -> None:
    assert container_gateway_findings(project, "claude") == []


def test_hooks_only_in_the_home_settings_local_file_are_reported(
    project: Path, managed: Path, isolated_home: Path
) -> None:
    sock = wire(project)
    write(isolated_home / ".claude" / "settings.local.json", hooks())

    [finding] = container_gateway_findings(project, "claude")

    assert finding.code == "container-gateway-hooks-not-loaded"
    assert finding.facts == {
        "sockets": [str(sock)],
        "user_settings_readable": True,
        "registered_in_unloaded_file": str(isolated_home / ".claude" / "settings.local.json"),
    }


@pytest.mark.parametrize(
    "where",
    ["managed-settings.d/50-magpie-container-gateway.json", "managed-settings.json"],
)
def test_hooks_in_managed_settings_are_loaded(project: Path, managed: Path, where: str) -> None:
    wire(project)
    write(managed / where, hooks())
    assert container_gateway_findings(project, "claude") == []


def test_hooks_in_the_user_settings_are_loaded(project: Path, managed: Path, isolated_home: Path) -> None:
    wire(project)
    write(isolated_home / ".claude" / "settings.json", hooks())
    assert container_gateway_findings(project, "claude") == []


def test_a_drop_in_running_the_dispatcher_is_loaded(project: Path, managed: Path) -> None:
    wire(project)
    dispatcher = "'/Library/Application Support/ClaudeCode/magpie/container-gateway-dispatch' start"
    hook = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": dispatcher}]}]}}
    write(managed / "managed-settings.d" / "50-magpie-container-gateway.json", hook)
    assert container_gateway_findings(project, "claude") == []


def dispatcher_drop_in(managed: Path) -> None:
    command = "'/Library/Application Support/ClaudeCode/magpie/container-gateway-dispatch' start"
    hook = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": command}]}]}}
    write(managed / "managed-settings.d" / "50-magpie-container-gateway.json", hook)


def test_a_symlinked_hook_behind_the_dispatcher_is_reported(
    project: Path, managed: Path, isolated_home: Path
) -> None:
    wire(project)
    dispatcher_drop_in(managed)
    scripts = isolated_home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    target = isolated_home / "sync-repo" / "container-gateway-hook.sh"
    target.parent.mkdir()
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    (scripts / "container-gateway-hook.sh").symlink_to(target)

    [finding] = container_gateway_findings(project, "claude")

    assert finding.facts["hook_is_symlink"] == str(scripts / "container-gateway-hook.sh")


def test_a_plain_hook_behind_the_dispatcher_is_not_reported(
    project: Path, managed: Path, isolated_home: Path
) -> None:
    wire(project)
    dispatcher_drop_in(managed)
    scripts = isolated_home / ".claude" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "container-gateway-hook.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    assert container_gateway_findings(project, "claude") == []


def test_a_hidden_drop_in_is_not_loaded(project: Path, managed: Path) -> None:
    wire(project)
    write(managed / "managed-settings.d" / ".50-magpie-container-gateway.json", hooks())
    [finding] = container_gateway_findings(project, "claude")
    assert finding.code == "container-gateway-hooks-not-loaded"


def test_only_the_stop_hook_does_not_count_as_wired(project: Path, managed: Path) -> None:
    wire(project)
    write(managed / "managed-settings.d" / "50-magpie-container-gateway.json", hooks("stop"))
    [finding] = container_gateway_findings(project, "claude")
    assert finding.facts["registered_in_unloaded_file"] is None


def test_a_running_gateway_is_not_reported(project: Path, managed: Path) -> None:
    sock = wire(project)
    sock.parent.mkdir(parents=True)
    sock.touch()  # the check only asks whether the wired socket exists
    assert container_gateway_findings(project, "claude") == []


def test_a_socket_outside_the_gateway_run_dir_is_not_gateway_wiring(project: Path, managed: Path) -> None:
    write(project / ".claude" / "settings.json", {"env": {"DOCKER_HOST": "unix:///var/run/docker.sock"}})
    assert container_gateway_findings(project, "claude") == []


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads a chmod 0 file")
def test_unreadable_user_settings_are_reported_as_unknown(
    project: Path, managed: Path, isolated_home: Path
) -> None:
    wire(project)
    user = isolated_home / ".claude" / "settings.json"
    write(user, hooks())
    user.chmod(0)
    try:
        [finding] = container_gateway_findings(project, "claude")
    finally:
        user.chmod(0o644)
    assert finding.facts["user_settings_readable"] is False


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs FIFOs")
def test_a_fifo_at_a_settings_path_is_skipped_rather_than_read(project: Path, managed: Path) -> None:
    wire(project)
    os.mkfifo(project / ".claude" / "settings.json")
    # Reading the FIFO would block with no writer; the check must answer instead.
    [finding] = container_gateway_findings(project, "claude")
    assert finding.code == "container-gateway-hooks-not-loaded"


def test_an_unadopted_projects_git_dir_socket_is_gateway_wiring(project: Path, managed: Path) -> None:
    sock = project / ".git" / "apache-magpie" / "run" / "0123abcd" / "docker.sock"
    write(project / ".claude" / "settings.local.json", {"env": {"DOCKER_HOST": f"unix://{sock}"}})
    [finding] = container_gateway_findings(project, "claude")
    assert finding.facts["sockets"] == [str(sock)]


def linked_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A main checkout and one linked worktree of it, as `git worktree add` lays them out."""
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".git" / "worktrees" / "wt" / "commondir").write_text("../..\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt'}\n", encoding="utf-8")
    return main, worktree


def test_hooks_in_the_main_checkout_count_for_a_linked_worktree(tmp_path: Path, managed: Path) -> None:
    main, worktree = linked_worktree(tmp_path)
    wire(worktree)
    write(main / ".claude" / "settings.local.json", hooks())
    assert container_gateway_findings(worktree, "claude") == []


def test_wiring_inherited_from_the_main_checkout_is_checked(
    tmp_path: Path, managed: Path, isolated_home: Path
) -> None:
    main, worktree = linked_worktree(tmp_path)
    sock = wire(main)
    write(isolated_home / ".claude" / "settings.local.json", hooks())

    [finding] = container_gateway_findings(worktree, "claude")

    assert finding.facts["sockets"] == [str(sock)]
    assert finding.facts["registered_in_unloaded_file"] == str(
        isolated_home / ".claude" / "settings.local.json"
    )


def test_the_main_checkouts_wiring_wins_over_the_worktrees(tmp_path: Path, managed: Path) -> None:
    main, worktree = linked_worktree(tmp_path)
    inherited = wire(main)
    running = wire(worktree)
    running.parent.mkdir(parents=True)
    running.touch()

    [finding] = container_gateway_findings(worktree, "claude")

    assert finding.facts["sockets"] == [str(inherited)]


@pytest.mark.parametrize("harness", ["codex", None])
def test_another_harness_sharing_the_checkout_is_never_told(project: Path, managed: Path, harness) -> None:
    wire(project)
    assert container_gateway_findings(project, harness) == []


def test_platforms_without_the_gateway_are_never_told(
    project: Path, managed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wire(project)
    monkeypatch.setattr(gateway, "SUPPORTED", False)
    assert container_gateway_findings(project, "claude") == []


def test_the_finding_ships_its_rules(project: Path, managed: Path) -> None:
    wire(project)
    [finding] = container_gateway_findings(project, "claude")
    assert "container-gateway-hooks-not-loaded" in sections.load(finding.section)
