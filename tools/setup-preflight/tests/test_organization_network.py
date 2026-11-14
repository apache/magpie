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
#
"""Regression tests for the ASF network-permission selection gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from setup_preflight.organization_network import declares_asf, is_asf_project, selected_asf_network_settings


@pytest.mark.parametrize(
    "content",
    [
        "organization: ASF",
        "| organization | ASF |",
        "| `organization` | `ASF` (derived: apache/ GitHub org) |",
    ],
)
def test_explicit_asf_declaration(content: str) -> None:
    assert declares_asf(content)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "organization: independent",
        "organization: TODO",
        "organization: ASF.example",
        "organization: ASF # example",
        "organization: ASF\norganization: ASF",
        "| organization | ASF |\norganization: independent",
        "<!-- organization: ASF -->",
        "> organization: ASF",
        "```yaml\norganization: ASF\n```",
        "~~~yaml\norganization: ASF\n~~~",
        "Example:\n\n    organization: ASF\n",
        "```markdown\n    ```\norganization: ASF\n```\n",
        "<!-- disabled example\norganization: ASF\n",
        "```markdown\n```yaml\norganization: ASF\n```\n",
        "repository: apache/example",
        "| organization | `TODO` |",
    ],
)
def test_no_implicit_or_ambiguous_asf_grant(content: str) -> None:
    assert not declares_asf(content)


def test_committed_asf_project(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("| organization | ASF |\n")
    assert is_asf_project(tmp_path)


def test_personal_file_overrides_committed_asf(tmp_path: Path) -> None:
    (tmp_path / ".apache-magpie.lock").write_text("method: local\n")

    committed = tmp_path / ".apache-magpie-overrides"
    committed.mkdir()
    (committed / "project.md").write_text("| organization | ASF |\n")

    personal = tmp_path / ".apache-magpie-local"
    personal.mkdir()
    (personal / "project.md").write_text("project_name: example\n")

    assert not is_asf_project(tmp_path)


def test_missing_project_configuration(tmp_path: Path) -> None:
    assert not is_asf_project(tmp_path)


def test_unreadable_project_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    path = config / "project.md"
    path.write_text("organization: ASF\n")

    original = Path.read_text

    def fail_read(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self == path:
            raise PermissionError("denied")
        return original(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", fail_read)
    assert not is_asf_project(tmp_path)


def test_asf_project_selects_network_fragment(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: ASF\n")

    fragment = Path(__file__).resolve().parents[3] / "tools/agent-isolation/claude-settings.asf.fragment.json"

    data = cast(dict[str, Any], selected_asf_network_settings(tmp_path, fragment))

    assert data["sandbox"]["network"]["allowedDomains"] == [
        "lists.apache.org",
        "dist.apache.org",
        "repository.apache.org",
        "downloads.apache.org",
        "archive.apache.org",
        "cveprocess.apache.org",
    ]
    assert data["permissions"]["allow"] == ["WebFetch(domain:lists.apache.org)"]


def test_non_asf_project_never_reads_fragment(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: independent\n")

    # This file deliberately does not exist.
    missing = tmp_path / "missing-fragment.json"

    assert selected_asf_network_settings(tmp_path, missing) == {}


def test_asf_project_rejects_malformed_fragment(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: ASF\n")

    fragment = tmp_path / "fragment.json"
    fragment.write_text('{"sandbox": {"network": {}}}')

    with pytest.raises(ValueError, match="Invalid ASF network fragment"):
        selected_asf_network_settings(tmp_path, fragment)


@pytest.mark.parametrize(
    "domains, permissions",
    [
        (["*.apache.org"], ["WebFetch(domain:lists.apache.org)"]),
        (["evil.example.com"], ["WebFetch(domain:lists.apache.org)"]),
        (["lists.apache.org"], ["WebFetch(domain:evil.example.com)"]),
        ([], []),
    ],
)
def test_asf_fragment_rejects_unreviewed_grants(
    tmp_path: Path, domains: list[str], permissions: list[str]
) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: ASF\n")

    fragment = tmp_path / "fragment.json"
    fragment.write_text(
        json.dumps(
            {
                "sandbox": {"network": {"allowedDomains": domains}},
                "permissions": {"allow": permissions},
            }
        )
    )

    with pytest.raises(ValueError, match="Invalid ASF network fragment"):
        selected_asf_network_settings(tmp_path, fragment)


def test_asf_fragment_rejects_extra_keys(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: ASF\n")

    fragment = Path(__file__).resolve().parents[3] / "tools/agent-isolation/claude-settings.asf.fragment.json"

    data = json.loads(fragment.read_text())
    data["sandbox"]["network"]["allowedDomains"].append("evil.example.com")

    modified = tmp_path / "modified.json"
    modified.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="Invalid ASF network fragment"):
        selected_asf_network_settings(tmp_path, modified)


def test_organization_network_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from setup_preflight.organization_network import main

    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()

    fragment = Path(__file__).resolve().parents[3] / "tools/agent-isolation/claude-settings.asf.fragment.json"

    # Missing organization: output is neutral.
    assert (
        main(
            [
                "--project-root",
                str(tmp_path),
                "--fragment",
                str(fragment),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {}

    # Explicit ASF organization: output the reviewed fragment.
    (config / "project.md").write_text("organization: ASF\n")

    assert (
        main(
            [
                "--project-root",
                str(tmp_path),
                "--fragment",
                str(fragment),
            ]
        )
        == 0
    )

    data = json.loads(capsys.readouterr().out)

    assert set(data["sandbox"]["network"]["allowedDomains"]) == {
        "lists.apache.org",
        "dist.apache.org",
        "repository.apache.org",
        "downloads.apache.org",
        "archive.apache.org",
        "cveprocess.apache.org",
    }
    assert data["permissions"]["allow"] == ["WebFetch(domain:lists.apache.org)"]


def test_bundled_fragment_matches_reviewed_source() -> None:
    from setup_preflight import organization_network

    bundled = Path(organization_network.__file__).with_name("claude-settings.asf.fragment.json")
    canonical = (
        Path(__file__).resolve().parents[3] / "tools/agent-isolation/claude-settings.asf.fragment.json"
    )

    assert bundled.read_bytes() == canonical.read_bytes()


def test_cli_uses_bundled_fragment_by_default(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from setup_preflight.organization_network import main

    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "project.md").write_text("organization: ASF\n")

    assert main(["--project-root", str(tmp_path)]) == 0

    selected = json.loads(capsys.readouterr().out)
    assert set(selected["sandbox"]["network"]["allowedDomains"]) == {
        "lists.apache.org",
        "dist.apache.org",
        "repository.apache.org",
        "downloads.apache.org",
        "archive.apache.org",
        "cveprocess.apache.org",
    }
