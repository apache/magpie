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

"""The derived-wiring merge: what it adds, what it leaves alone, what it refuses."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from setup_preflight import settings_merge

from .conftest import write_lock

FLOOR = """
    method: marketplace
    url: apache/magpie
    min_version: 0.3.0

    plugins:
      - magpie-setup
      - magpie-utilities
      - magpie-agent-guard
      - magpie-vetted-ops
"""

REGISTRY = {
    "servers": {
        "apache-projects": {"families": ["utilities"], "tools": ["project_stats", "get_person"]},
    }
}


def paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    return (
        tmp_path / ".claude" / "settings.json",
        tmp_path / ".apache-magpie.lock",
        tmp_path / "registry.json",
    )


def write_registry(path: Path, registry: dict = REGISTRY) -> None:
    path.write_text(json.dumps(registry), encoding="utf-8")


def test_default_registry_is_shipped_inside_the_package() -> None:
    assert settings_merge.DEFAULT_REGISTRY == settings_merge.HERE / "family-mcp-allows.json"
    assert settings_merge.DEFAULT_REGISTRY.is_file()


def test_copied_package_uses_its_shipped_registry(tmp_path: Path) -> None:
    shutil.copytree(settings_merge.HERE, tmp_path / "setup_preflight")
    project = tmp_path / "project"
    project.mkdir()
    write_lock(project, FLOOR)
    settings_path = project / ".claude" / "settings.json"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            "-P",
            "-m",
            "setup_preflight.settings_merge",
            "--settings",
            str(settings_path),
            "--lock",
            str(project / ".apache-magpie.lock"),
            "--write",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["allows_added"] == []
    assert "permissions" not in json.loads(settings_path.read_text(encoding="utf-8"))


def test_creates_the_file_when_absent(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)

    report = settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert report == {
        "action": "create",
        "keys_preserved": [],
        "plugins_added": [
            "magpie-setup@apache-magpie",
            "magpie-utilities@apache-magpie",
            "magpie-agent-guard@apache-magpie",
            "magpie-vetted-ops@apache-magpie",
        ],
        "allows_added": [
            "mcp__apache-projects__project_stats",
            "mcp__apache-projects__get_person",
        ],
        "plugins_removed": [],
        "marketplace_definition_changed": True,
    }
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["extraKnownMarketplaces"]["apache-magpie"] == {
        "source": {"source": "github", "repo": "apache/magpie"}
    }
    assert written["enabledPlugins"]["magpie-setup@apache-magpie"] is True
    assert written["permissions"]["allow"] == [
        "mcp__apache-projects__project_stats",
        "mcp__apache-projects__get_person",
    ]


def test_omits_permissions_when_the_shipped_registry_derives_no_allows(tmp_path: Path) -> None:
    settings_path, lock_path, _ = paths(tmp_path)
    write_lock(tmp_path, FLOOR)

    report = settings_merge.run(settings_path, lock_path, settings_merge.DEFAULT_REGISTRY, write=True)

    assert report["allows_added"] == []
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "permissions" not in written


def test_does_not_add_permissions_to_an_existing_file_when_no_allows_are_derived(
    tmp_path: Path,
) -> None:
    settings_path, lock_path, _ = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"sandbox": {"enabled": true}}', encoding="utf-8")

    settings_merge.run(settings_path, lock_path, settings_merge.DEFAULT_REGISTRY, write=True)

    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["sandbox"] == {"enabled": True}
    assert "permissions" not in written


def test_preserves_other_keys_and_existing_allows(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "$schema": "https://json.schemastore.org/claude-code-settings.json",
                "sandbox": {"enabled": True},
                "permissions": {"allow": ["Bash(gh:*)"]},
            }
        ),
        encoding="utf-8",
    )

    report = settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert report["action"] == "merge"
    assert report["keys_preserved"] == ["$schema", "sandbox", "permissions"]
    assert report["allows_added"] == [
        "mcp__apache-projects__project_stats",
        "mcp__apache-projects__get_person",
    ]
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["sandbox"] == {"enabled": True}
    assert written["permissions"]["allow"] == [
        "Bash(gh:*)",
        "mcp__apache-projects__project_stats",
        "mcp__apache-projects__get_person",
    ]


def test_preserves_an_existing_file_mode(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{}", encoding="utf-8")
    settings_path.chmod(0o600)

    settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert settings_path.stat().st_mode & 0o777 == 0o600


def test_preserves_non_ascii_values_verbatim(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps({"sandbox": {"note": "café"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    settings_merge.run(settings_path, lock_path, registry_path, write=True)

    written = settings_path.read_text(encoding="utf-8")
    assert '"café"' in written
    assert "\\u00e9" not in written


def test_adds_only_the_missing_plugins(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        json.dumps(
            {
                "enabledPlugins": {
                    "magpie-setup@apache-magpie": True,
                    "magpie-security@apache-magpie": True,
                    "some-other-plugin@vendor-marketplace": True,
                }
            }
        ),
        encoding="utf-8",
    )

    report = settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert report["plugins_added"] == [
        "magpie-utilities@apache-magpie",
        "magpie-agent-guard@apache-magpie",
        "magpie-vetted-ops@apache-magpie",
    ]
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "magpie-security@apache-magpie" in written["enabledPlugins"]
    assert "some-other-plugin@vendor-marketplace" in written["enabledPlugins"]


def test_leaves_a_pinned_marketplace_alone(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    pinned = {"source": {"source": "github", "repo": "apache/magpie@0.2.0"}}
    settings_path.write_text(
        json.dumps({"extraKnownMarketplaces": {"apache-magpie": pinned}, "enabledPlugins": {}}),
        encoding="utf-8",
    )

    report = settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert report["marketplace_definition_changed"] is False
    written = json.loads(settings_path.read_text(encoding="utf-8"))
    assert written["extraKnownMarketplaces"]["apache-magpie"] == pinned


def test_refuses_a_malformed_file_and_leaves_it_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)
    settings_path.parent.mkdir(parents=True)
    broken = '{"permissions": {"allow": [},}'
    settings_path.write_text(broken, encoding="utf-8")

    code = settings_merge.main(
        [
            "--settings",
            str(settings_path),
            "--lock",
            str(lock_path),
            "--registry",
            str(registry_path),
            "--write",
        ]
    )

    assert code == 2
    assert settings_path.read_text(encoding="utf-8") == broken
    report = json.loads(capsys.readouterr().out)
    assert report["action"] == "refuse"
    assert report["plugins_added"] == []
    assert report["allows_added"] == []


def test_ensures_the_vetted_ops_plugin_on_an_older_lock(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(
        tmp_path,
        """
        method: marketplace
        url: apache/magpie
        min_version: 0.1.0

        plugins:
          - magpie-setup
        """,
    )
    write_registry(registry_path)

    report = settings_merge.run(settings_path, lock_path, registry_path, write=True)

    assert report["plugins_added"] == ["magpie-setup@apache-magpie", "magpie-vetted-ops@apache-magpie"]


def test_without_write_the_file_is_not_touched(tmp_path: Path) -> None:
    settings_path, lock_path, registry_path = paths(tmp_path)
    write_lock(tmp_path, FLOOR)
    write_registry(registry_path)

    report = settings_merge.run(settings_path, lock_path, registry_path, write=False)

    assert report["action"] == "create"
    assert report["allows_added"] == [
        "mcp__apache-projects__project_stats",
        "mcp__apache-projects__get_person",
    ]
    assert not settings_path.exists()
