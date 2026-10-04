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
"""Build a throwaway adopter repo with `.apache-magpie-overrides/` config files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from release_config.cli import run

BASE_RMC: dict[str, Any] = {
    "project_dist_name": "foo",
    "release_branch_base": "main",
    "version_manifest_files": ["setup.cfg", "foo/__init__.py"],
    "release_dist_backend": "svnpubsub",
    "release_vote_backend": "manual",
    "release_approval_mechanism": "dev-list-vote",
    "release_announce_backend": "announce-list",
    "release_dist_url_template": "https://dist.apache.org/repos/dist/<bucket>/foo/<version>/",
    "archive_url_template": "https://archive.apache.org/dist/foo/",
    "keys_file_url": "https://dist.apache.org/repos/dist/release/foo/KEYS",
    "keyserver": "keys.openpgp.org",
    "rm_key_fingerprint": "*(per-RM; lives in user.md)*",
    "automated_release_signing": "off",
    "vote_dev_list": "dev@foo.apache.org",
    "vote_window_hours": "72",
    "vote_subject_template": "[VOTE] Release Apache Foo <version> from <version>-rcN",
    "result_subject_template": "[RESULT] [VOTE] Release Apache Foo <version> from <version>-rcN",
    "release_approver_roster_path": "<project-config>/pmc-roster.md",
    "announce_list": "announce@apache.org",
    "announce_cc_lists": ["dev@foo.apache.org", "users@foo.apache.org"],
    "announce_subject_template": "[ANNOUNCE] Apache Foo <version> released",
    "site_repo": "apache/foo-site",
    "site_pr_files": ["content/_index.md", "content/announcements/<version>.md"],
    "archive_retention_rule": "latest_of_each_supported_line",
    "audit_log_path": "audit/releases/",
}

BUILD_SOURCE_ONLY = """\
# Apache Foo: release-build configuration

## Source archive

| Key | Value | Notes |
|---|---|---|
| `source_archive_method` | `git-archive` | default |
| `source_archive_format` | `tar.gz` | |
| `source_archive_prefix` | `apache-foo-<version>` | |
| `export_ignore_reviewed` | `1.0.0` | review done in the 1.0.0 prep PR |

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

## Binary-exclude list

None beyond the baseline.

## Apache RAT configuration

- **RAT excludes file:** `.rat-excludes`.
"""

TRAINS = """\
# Apache Foo — release trains

## Release branches currently in flight

- **`main`** — the next minor release.
- **`v1-2-test`** — patch branch for `1.2.x`.

Template guidance — for each branch list:

- the branch name;
"""

ROSTER = """\
# Apache Foo: PMC roster

## Roster

| Apache ID | Name | Primary email | Binding since |
|---|---|---|---|
| `johndoe` | John Doe | `john@example.com` | `2020-01-01` |
| `alice` | Alice | `alice@apache.org` | `2021-01-01` |
"""


def rmc_text(values: dict[str, Any]) -> str:
    rows = ["# Apache Foo: release-management configuration", "", "| Key | Value |", "|---|---|"]
    for key, value in values.items():
        if isinstance(value, list):
            cell = ", ".join(f"`{v}`" for v in value)
        elif isinstance(value, str) and value.startswith("*("):
            cell = value
        else:
            cell = f"`{value}`"
        rows.append(f"| `{key}` | {cell} |")
    return "\n".join(rows) + "\n"


@pytest.fixture
def project(tmp_path: Path) -> Callable[..., Path]:
    """`project(rmc_overrides, build=…, trains=…, roster=…, org=…, drop=[…])` → repo root."""

    def make(
        rmc: dict[str, Any] | None = None,
        *,
        drop: tuple[str, ...] = (),
        build: str | None = BUILD_SOURCE_ONLY,
        trains: str | None = TRAINS,
        roster: str | None = ROSTER,
        org: str = "ASF",
        user: str | None = None,
    ) -> Path:
        values = {**BASE_RMC, **(rmc or {})}
        for key in drop:
            values.pop(key, None)
        config = tmp_path / ".apache-magpie-overrides"
        config.mkdir(exist_ok=True)
        (config / "release-management-config.md").write_text(rmc_text(values), encoding="utf-8")
        (config / "project.md").write_text(f"# Project\n\n| Key | Value |\n|---|---|\n| `organization` | `{org}` |\n", encoding="utf-8")
        for name, text in (("release-build.md", build), ("release-trains.md", trains), ("pmc-roster.md", roster)):
            if text is not None:
                (config / name).write_text(text, encoding="utf-8")
        if user is not None:
            (tmp_path / "user.md").write_text(user, encoding="utf-8")
        return tmp_path

    return make


@pytest.fixture
def preflight() -> Callable[..., dict[str, Any]]:
    def call(root: Path, skill: str, *argv: str) -> dict[str, Any]:
        user = root / "user.md"
        extra = ["--user-config", str(user)] if user.exists() else ["--user-config", str(root / "absent-user.md")]
        return run(["preflight", "--project-root", str(root), *extra, "--skill", skill, *argv])

    return call


@pytest.fixture
def load() -> Callable[..., dict[str, Any]]:
    def call(root: Path, skill: str | None, *argv: str) -> dict[str, Any]:
        user = root / "user.md"
        extra = ["--user-config", str(user)] if user.exists() else ["--user-config", str(root / "absent-user.md")]
        skill_args = ["--skill", skill] if skill else []
        return run(["load", "--project-root", str(root), *extra, *skill_args, *argv])

    return call
