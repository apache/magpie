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

from release_management.announce_draft import render as announce
from release_management.promote import render as promote
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


def _project(tmp_path: Path, extra: dict[str, Any] | None = None) -> None:
    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir(exist_ok=True)
    (config / "release-management-config.md").write_text(_rmc(RMC | (extra or {})), encoding="utf-8")
    (config / "release-build.md").write_text(BUILD, encoding="utf-8")
    (config / "project.md").write_text(
        "# Project\n\n| Key | Value |\n|---|---|\n| `organization` | `ASF` |\n", encoding="utf-8"
    )


def _run(tmp_path: Path, command: str, skill: str, *argv: str) -> dict[str, Any]:
    result: dict[str, Any] = release_config_cli.run(
        [
            command,
            "--project-root",
            str(tmp_path),
            "--user-config",
            str(tmp_path / "absent.md"),
            "--skill",
            skill,
            *argv,
        ]
    )
    return result


def test_promote_renders_from_a_real_load(tmp_path: Path) -> None:
    _project(tmp_path)
    pre = _run(tmp_path, "preflight", "promote", "1.0.0-rc1", "--rm", "nobody")
    verdict = promote.verdict(pre, vote_passed=True, target="empty")
    # No roster file: the RM is treated as not on the roster, which is a hand-off.
    assert verdict["verdict"] == "handoff-non-pmc" and verdict["dist_backend"] == "svnpubsub"
    loaded = _run(tmp_path, "load", "promote", "1.0.0-rc1")
    p = promote.Promote.from_load(loaded, upstream="apache/foo", project="foo", product_name="Apache Foo")
    out = promote.step2(
        p, handoff=True, rm="nobody", apache_id="nobody", result_vote_url="u", rc_commit_sha="abc"
    )
    assert "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/ \\" in out["command_block"]
    assert "svn list https://dist.apache.org/repos/dist/release/foo/1.0.0/" in out["command_block"]
    assert "git push apache refs/tags/1.0.0" in out["command_block"]
    assert out["handoff_note"]


def test_announce_draft_renders_from_a_real_load(tmp_path: Path) -> None:
    _project(
        tmp_path,
        {
            "announce_list": "announce@apache.org",
            "announce_cc_lists": ["dev@foo.apache.org"],
            "announce_subject_template": "[ANNOUNCE] Apache Foo <version> released",
            "site_repo": "apache/foo-site",
            "site_pr_files": ["content/announcements/<version>.md"],
        },
    )
    pre = _run(
        tmp_path,
        "preflight",
        "announce-draft",
        "1.0.0",
        "--promote-timestamp",
        "2026-06-10T08:00:00Z",
        "--now",
        "2026-06-11T10:00:00Z",
        "--download-page",
        "https://foo.apache.org/download",
    )
    assert announce.verdict(pre, promoted=True)["verdict"] == "proceed"
    loaded = _run(tmp_path, "load", "announce-draft", "1.0.0", "--promote-timestamp", "2026-06-10T08:00:00Z")
    a = announce.Announce.from_load(loaded, product_name="Apache Foo")
    draft = announce.step2(a, download_page="https://foo.apache.org/download", changelog_url="https://c")
    assert draft["subject"] == "[ANNOUNCE] Apache Foo 1.0.0 released"
    assert "Cc: dev@foo.apache.org" in draft["body"] and "foo/KEYS" in draft["body"]
    site = announce.step3(a)
    assert site["files_in_scope"] == ["content/announcements/1.0.0.md"] and site["proposed"] is True


def test_prepare_decides_from_a_real_preflight_and_load(tmp_path: Path) -> None:
    from release_management.prepare import archive as prepare_archive
    from release_management.prepare import plan as prepare_plan
    from release_management.prepare import prep as prepare_prep
    from release_management.prepare import signing as prepare_signing

    _project(
        tmp_path,
        {
            "release_vote_backend": "atr",
            "changelog_label_categories": ["needs-review=Other changes"],
        },
    )
    (tmp_path / ".apache-magpie-overrides" / "release-trains.md").write_text(
        "# Release trains\n\n## Release branches currently in flight\n\n"
        "- **`main`** — the 1.x train; next release `1.1.0`, Release Manager @rm.\n",
        encoding="utf-8",
    )
    pre = _run(tmp_path, "preflight", "prepare", "prep", "1.1.0")
    url = "https://github.com/apache/foo/issues/1"
    verdict = prepare_plan.verdict(
        pre, planning_issue=url, planning_labels=["release-planning"], gh_access=True
    )
    assert verdict["verdict"] == "proceed" and verdict["train_covered"] is True
    assert prepare_plan.verdict(_run(tmp_path, "preflight", "prepare", "2.0.0"), gh_access=True)[
        "blockers"
    ] == ["release-trains.md has no entry for version 2.0.0 or a 2.x train"]

    loaded = _run(tmp_path, "load", "prepare", "prep", "1.1.0")
    mode = prepare_archive.mode(loaded, previous_tag="1.0.0")
    assert mode["mode"] == "drift" and mode["export_ignore_reviewed"] == "1.0.0"
    cats = prepare_prep.parse_categories(loaded["config"].get("changelog_label_categories"))
    assert cats == {"needs-review": "Other changes"}
    assert loaded["config"]["version_manifest_files"] == ["setup.cfg"]

    signing_load = _run(tmp_path, "load", "prepare", "automated-signing")
    gate = prepare_signing.eligibility(signing_load, verify_rc_identical=True)
    assert gate["eligible"] is True, gate["missing_conditions"]
    assert prepare_signing.eligibility(signing_load)["missing_conditions"] == [
        prepare_signing.NOT_REPRODUCIBLE
    ]


def test_archive_review_protects_the_voter_inputs_of_a_real_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`prepare archive-review --load` reads the RAT paths and validators `release-config load` prints."""
    import json

    from release_management.cli import main

    config = tmp_path / ".apache-magpie-overrides"
    config.mkdir()
    (config / "release-management-config.md").write_text(_rmc(RMC), encoding="utf-8")
    build = (
        BUILD
        + "\n## Apache RAT configuration\n\n- **RAT plugin config:** `dev/rat.yml`.\n"
        + "- **RAT excludes file:** `dev/rat-excludes.txt`.\n"
        + "\n## Source-tree validators\n\n```yaml\nsource_tree_validators:\n"
        + '  - "dev/check-tree.sh --strict"\n```\n'
    )
    (config / "release-build.md").write_text(build, encoding="utf-8")
    (config / "project.md").write_text(
        "# Project\n\n| Key | Value |\n|---|---|\n| `organization` | `ASF` |\n", encoding="utf-8"
    )
    loaded = release_config_cli.run(
        ["load", "--project-root", str(tmp_path), "--user-config", str(tmp_path / "absent.md")]
    )
    assert loaded["build"]["rat_excludes_path"] == "dev/rat-excludes.txt"
    assert loaded["build"]["rat_config_path"] == "dev/rat.yml"
    assert loaded["build"]["source_tree_validators"] == ["dev/check-tree.sh --strict"]
    (tmp_path / "load.json").write_text(json.dumps(loaded), encoding="utf-8")
    tracked = [
        "LICENSE",
        "NOTICE",
        "dev/rat-excludes.txt",
        "dev/rat.yml",
        "dev/check-tree.sh",
        "dev/notes.md",
    ]
    (tmp_path / "tracked.txt").write_text("\n".join(tracked) + "\n", encoding="utf-8")
    voters = ("dev/rat-excludes.txt", "dev/rat.yml", "dev/check-tree.sh")
    argv = ["prepare", "archive-review", "--load", str(tmp_path / "load.json")]
    argv += ["--tracked", str(tmp_path / "tracked.txt")]
    for path in voters:
        argv += ["--exclude", path]
    assert main(argv) == 0
    out = json.loads(capsys.readouterr().out)
    refused = {r["path"]: r["reason"] for r in out["refused"]}
    for path in voters:
        assert refused[path].startswith("an input to the checks voters run"), path
    assert not set(voters) & {p["path"] for p in out["proposed"]}


def test_audit_report_renders_from_a_real_load(tmp_path: Path) -> None:
    from release_management.audit_report import record
    from release_management.audit_report import render as audit_report

    _project(tmp_path, {"audit_log_path": "audit/releases", "product_name": "Apache Foo"})
    roster = (
        "| Apache ID | Name | Primary email |\n|---|---|---|\n| `alice` | Alice | `alice@example.org` |\n"
    )
    (tmp_path / ".apache-magpie-overrides" / "pmc-roster.md").write_text(roster, encoding="utf-8")
    pre = _run(tmp_path, "preflight", "audit-report", "1.0.0")
    verdict = audit_report.verdict(pre, planning_issue="apache/foo#7")
    assert verdict["verdict"] == "proceed", verdict["blockers"]
    assert verdict["planning_issue_url"] == "https://github.com/apache/foo/issues/7"
    assert verdict["audit_log_path"] == "audit/releases"
    loaded = _run(tmp_path, "load", "audit-report", "1.0.0")
    plan = audit_report.gather(loaded, rc="rc1")
    assert plan["product_name"] == "Apache Foo"
    assert plan["promote_revision"]["command"] == (
        "svn info --show-item last-changed-revision https://dist.apache.org/repos/dist/release/foo/1.0.0/"
    )
    assert audit_report.voters(["alice@apache.org"], roster)["binding_voters"] == ["@alice"]
    step1 = {
        "version": "1.0.0",
        "product_name": plan["product_name"],
        "planning_issue_url": verdict["planning_issue_url"],
        **dict.fromkeys(record.ORDERED_FIELDS[1:], "MISSING"),
    }
    out = audit_report.pr(step1, audit_log_path=verdict["audit_log_path"], upstream="apache/foo")
    assert out["target_file"] == "audit/releases/1.0.0.md"
    assert out["pr_title"] == "chore: add release audit record for Apache Foo 1.0.0"


def test_archive_sweep_renders_from_a_real_load(tmp_path: Path) -> None:
    from release_management.archive_sweep import render as archive_sweep
    from release_management.archive_sweep import retention

    _project(tmp_path, {"archive_retention_rule": "latest_of_each_supported_line"})
    (tmp_path / ".apache-magpie-overrides" / "release-trains.md").write_text(
        "# Release trains\n\n## Release branches currently in flight\n\n"
        "- **`v1-x-stable`** — the 1.x train, supported; latest `1.1.0`.\n"
        "- **`main`** — the 2.x train, supported; latest `2.0.0`.\n",
        encoding="utf-8",
    )
    pre = _run(tmp_path, "preflight", "archive-sweep")
    assert archive_sweep.verdict(pre) == {
        "verdict": "proceed",
        "blockers": [],
        "non_asf": False,
        "dist_backend": "svnpubsub",
    }
    loaded = _run(tmp_path, "load", "archive-sweep")
    sweep = archive_sweep.Sweep.from_load(loaded)
    assert (
        archive_sweep.listing(sweep)["command"] == "svn list https://dist.apache.org/repos/dist/release/foo/"
    )
    trains = archive_sweep.trains(sweep)["trains"]
    assert trains == [{"label": "1.x", "pattern": "1.x"}, {"label": "2.x", "pattern": "2.x"}]
    versions, _ = retention.parse_listing("1.0.0/\n1.1.0/\n2.0.0/\nKEYS\n")
    out = archive_sweep.step2(sweep, retention.sweep(versions, trains))
    assert out["archive_count"] == 1
    assert "https://dist.apache.org/repos/dist/release/foo/1.0.0 \\" in out["commands"]
    assert "https://archive.apache.org/dist/foo/1.0.0 \\" in out["commands"]
    assert '-m "Archive foo 1.0.0 per retention policy"' in out["commands"]


def test_keys_sync_renders_from_a_real_load(tmp_path: Path) -> None:
    from release_management.keys_sync import check
    from release_management.keys_sync import render as keys_sync

    _project(tmp_path)
    fpr = "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6ABCD"
    pre = _run(tmp_path, "preflight", "keys-sync", "--fingerprint", fpr)
    assert pre["ok"] and pre["values"]["keyserver"] == "keys.openpgp.org"
    absent = {
        "step": "list-keys",
        "file": "KEYS",
        "keys": [{"fingerprint": "C" * 40, "uids": ["Other <o@apache.org>"]}],
    }
    assert keys_sync.verdict(pre, absent)["verdict"] == "proceed"
    key = {
        "fingerprint": fpr,
        "validity": "-",
        "algo_id": "22",
        "bits": 255,
        "curve": "ed25519",
        "created": "2025-01-01",
        "expiry": None,
        "uids": ["Foo RM <rm@apache.org>"],
        "subkey_fingerprints": [],
    }
    step1 = check.assess(check.find_key([key], fpr), fpr, check.dt.date(2026, 6, 19))
    assert step1["verdict"] == "proceed"
    loaded = _run(tmp_path, "load", "keys-sync")
    block = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nxx\n-----END PGP PUBLIC KEY BLOCK-----"
    out = keys_sync.step2(
        pre, loaded, step1, block, {"step": "list-keys", "file": "fetched.asc", "keys": [key]}
    )
    assert out["backend"] == "svnpubsub"
    assert out["keys_block_to_append"].startswith("# Foo RM <rm@apache.org>\n-----BEGIN")
    assert (
        "svn checkout https://dist.apache.org/repos/dist/release/foo /tmp/foo-keys --depth immediates"
        in out["svn_command_sequence"]
    )
    assert "https://keys.openpgp.org/upload" in out["keyserver_upload_reminder"]
