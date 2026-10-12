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
"""Render from what `release-config load` really prints, end to end."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from release_management.rc_cut import render

release_config_cli = pytest.importorskip("release_config.cli")

RMC = {
    "project_dist_name": "foo",
    "release_branch_base": "main",
    "version_manifest_files": ["setup.cfg"],
    "release_dist_backend": "svnpubsub",
    "release_vote_backend": "manual",
    "release_approval_mechanism": "dev-list-vote",
    "release_announce_backend": "announce-list",
    "release_dist_url_template": "https://dist.apache.org/repos/dist/<bucket>/foo/<version>/",
    "archive_url_template": "https://archive.apache.org/dist/foo/",
    "keys_file_url": "https://dist.apache.org/repos/dist/release/foo/KEYS",
    "keyserver": "keys.openpgp.org",
    "automated_release_signing": "off",
    "vote_dev_list": "dev@foo.apache.org",
    "vote_window_hours": "72",
    "git_upstream_remote": "apache",
}

BUILD = """\
# Apache Foo: release-build configuration

## Source archive

| Key | Value | Notes |
|---|---|---|
| `source_archive_method` | `git-archive` | default |
| `source_archive_format` | `tar.gz` | |
| `source_archive_prefix` | `apache-foo-<version>` | |
| `export_ignore_reviewed` | `1.0.0` | |

## Build invocation

Empty — the source archive comes from `git-archive`.

## Convenience artefacts

None — a source-only project.

## Expected artefact list

- `apache-foo-<version>-source.tar.gz`, canonical source artefact (required, signed, checksummed).

## Digest set

- `sha512`, required.

## Reproducibility checks

| Key | Value | Allowed values |
|---|---|---|
| `reproducibility_source` | `on` | `on`, `off` |
| `reproducibility_binaries` | `off` | `off`, `byte-identical`, `documented-divergence` |
"""


def _rmc(values: dict[str, Any]) -> str:
    rows = []
    for key, value in values.items():
        cell = " ".join(f"`{v}`" for v in value) if isinstance(value, list) else f"`{value}`"
        rows.append(f"| `{key}` | {cell} |")
    return "# Release management\n\n| Key | Value |\n|---|---|\n" + "\n".join(rows) + "\n"


def test_rc_cut_renders_from_a_real_load(tmp_path: Path) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "release-management-config.md").write_text(_rmc(RMC), encoding="utf-8")
    (config / "release-build.md").write_text(BUILD, encoding="utf-8")
    (config / "project.md").write_text(
        "# Project\n\n| Key | Value |\n|---|---|\n| `organization` | `ASF` |\n", encoding="utf-8"
    )
    loaded = release_config_cli.run(
        [
            "load",
            "--project-root",
            str(tmp_path),
            "--user-config",
            str(tmp_path / "absent.md"),
            "--skill",
            "rc-cut",
            "1.0.0",
            "rc1",
        ]
    )
    cut = render.RcCut.from_load(loaded, upstream="apache/foo", project="foo")
    assert cut.source_artefact == "apache-foo-1.0.0-source.tar.gz"
    step2 = render.step2(cut)
    assert "git push apache 1.0.0-rc1" in step2["section_1_tag_commands"]
    assert '--prefix "apache-foo-1.0.0"' in step2["section_2_build_command"]
    assert step2["section_4_checksum_commands"] == [
        "sha512sum apache-foo-1.0.0-source.tar.gz > apache-foo-1.0.0-source.tar.gz.sha512"
    ]
    step3 = render.step3(cut, asf_id="rm")
    assert "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/" in step3["staging_commands"][0]
    assert step3["dist_dev_only"] is True
    assert render.step2b(cut)["source_check_enabled"] is True
