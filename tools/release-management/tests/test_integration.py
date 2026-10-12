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

import hashlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from release_management.rc_cut import render
from release_management.vote_draft import render as vote_draft
from release_management.vote_tally import render as vote_tally

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


@pytest.mark.parametrize("build_ok", [True, False])
def test_custom_build_emits_a_complete_real_reproducibility_record(
    tmp_path: Path, monkeypatch, build_ok: bool
) -> None:
    def git(*args: str) -> str:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                *args,
            ],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    git("init")
    (tmp_path / "source.txt").write_text("source\n")
    git("add", "source.txt")
    git("commit", "-m", "fixture")
    git("-c", "tag.gpgsign=false", "tag", "1.0.0-rc1")
    if not build_ok:
        # A valid archive from a previous attempt must not get a new record.
        git("archive", "--format=tar.gz", "--prefix=foo/", "1.0.0-rc1", "-o", "source.tar.gz")
    root = Path(__file__).resolve().parents[3]
    script = root / "tools/reproducible-archive/src/reproducible_archive/__init__.py"
    invocation = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
    monkeypatch.setattr(render.RcCut, "repro", property(lambda self: invocation))
    cut = render.RcCut(
        version="1.0.0",
        rc="rc1",
        upstream="apache/foo",
        project="foo",
        meta={
            "source_archive_method": "custom",
            "build_command": "git archive --format=tar.gz --prefix=foo/ <version>-<rcN> -o source.tar.gz"
            if build_ok
            else "false",
            "expected_artefacts": ["source.tar.gz"],
        },
    )
    commands = render.step2(cut)["section_2_build_command"]
    result = subprocess.run(["sh", "-c", commands], cwd=tmp_path, text=True, capture_output=True)
    record = render.parse_record(result.stdout)
    if not build_ok:
        assert result.returncode != 0
        assert record == {}
        return
    assert result.returncode == 0, result.stderr
    assert record["commit"] == git("rev-parse", "HEAD")
    assert record["SOURCE_DATE_EPOCH"] == git("log", "-1", "--format=%ct")
    assert record["sha512"] == hashlib.sha512((tmp_path / "source.tar.gz").read_bytes()).hexdigest()
    assert record["swhid_dir"].startswith("swh:1:dir:")
    assert record["swhid_dir_note"] == "identical to the repository tree"
    assert render.step4(cut, record=record)["record_missing"] == []


def test_verify_rc_reads_a_real_load(tmp_path: Path) -> None:
    from release_management.verify_rc import args as verify_args
    from release_management.verify_rc import checks, repro
    from release_management.verify_rc.common import VerifyRc

    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "release-management-config.md").write_text(_rmc(RMC), encoding="utf-8")
    build = BUILD + "\n## Apache RAT configuration\n\n- **RAT excludes file:** `.rat-excludes`.\n"
    (config / "release-build.md").write_text(build, encoding="utf-8")
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
            "verify-rc",
            "1.0.0-rc1",
        ]
    )
    v = VerifyRc.from_load(loaded)
    assert (v.rc_tag, v.source_artefact, v.is_asf, v.ci_automated) == (
        "1.0.0-rc1",
        "apache-foo-1.0.0-source.tar.gz",
        True,
        False,
    )
    commands = verify_args.invocations(v)["commands"]
    assert '--expect "apache-foo-1.0.0-source.tar.gz"' in commands["inventory"]
    assert "--manifest setup.cfg" in commands["version"]
    assert checks.rat(v, report=None, exit_code=0)["status"] == "PASS"
    assert repro.plan(v, skip_repro=False)["source_enabled"] is True


def _load_for(tmp_path: Path, skill: str, rc_id: str, extra: dict[str, Any]) -> dict[str, Any]:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir(exist_ok=True)
    (config / "release-management-config.md").write_text(_rmc(RMC | extra), encoding="utf-8")
    (config / "release-build.md").write_text(BUILD, encoding="utf-8")
    (config / "project.md").write_text(
        "# Project\n\n| Key | Value |\n|---|---|\n| `organization` | `ASF` |\n", encoding="utf-8"
    )
    return release_config_cli.run(
        [
            "load",
            "--project-root",
            str(tmp_path),
            "--user-config",
            str(tmp_path / "absent.md"),
            "--skill",
            skill,
            rc_id,
        ]
    )


def test_vote_draft_renders_from_a_real_load(tmp_path: Path) -> None:
    loaded = _load_for(
        tmp_path,
        "vote-draft",
        "1.0.0-rc1",
        {
            "vote_subject_template": "[VOTE] Release <Product Name> <version> from <version>-rcN",
            "vote_verification_doc_url": "https://github.com/apache/foo/blob/<version>-rcN/docs/verify.md",
        },
    )
    draft = vote_draft.VoteDraft.from_load(loaded, product_name="Apache Foo")
    out = vote_draft.step2(draft, tag_url="t", changelog_url="c", svn_revision="42")
    assert out["subject"] == "[VOTE] Release Apache Foo 1.0.0 from 1.0.0-rc1"
    assert "To: dev@foo.apache.org" in out["body"]
    assert "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/\n  (SVN revision: r42)" in out["body"]
    assert "https://github.com/apache/foo/blob/1.0.0-rc1/docs/verify.md" in out["body"]
    assert "https://dist.apache.org/repos/dist/release/foo/KEYS" in out["body"]
    assert "open for at least 72 hours" in out["body"]
    assert (
        vote_draft.step3(draft, sent_at="2026-06-11T15:00:00Z")["window_closes_utc"] == "2026-06-14T15:00:00Z"
    )


def test_vote_tally_renders_from_a_real_load(tmp_path: Path) -> None:
    loaded = _load_for(
        tmp_path,
        "vote-tally",
        "1.0.0-rc1",
        {
            "result_subject_template": "[RESULT] [VOTE] Release <Product Name> <version> from <version>-rcN",
            "mail_archive_url_template": "https://lists.apache.org/list.html?<dev-list>",
        },
    )
    assert vote_tally.archive_url(loaded)["url"] == "https://lists.apache.org/list.html?dev@foo.apache.org"
    tallied = {
        "result": "PASSED",
        "pass_rule_applied": "r",
        "binding_plus1": 3,
        "voters": [],
        "ambiguous": [],
    }
    out = vote_tally.result_draft(loaded, tallied, product_name="Apache Foo")
    assert out["subject"] == "[RESULT] [VOTE] Release Apache Foo 1.0.0 from 1.0.0-rc1"
    assert out["body"].startswith("To: dev@foo.apache.org\n")
