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
"""release-rc-cut renderers.

The scripted cases of the retired model-graded suites `step-2-tag-build-sign`,
`step-2b-reproducibility` and `step-3-staging` live here, named after each
former case, with the same scenario and the same assertions.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from release_management.cli import main
from release_management.rc_cut import render

FP = "ABCD1234EF5678901234ABCD1234EF5678901234"


def loaded(
    *,
    version: str = "2.12.0",
    rc: str = "rc1",
    artefacts: list[tuple[str, str]] | None = None,
    digests: list[str] | None = None,
    backend: str = "svnpubsub",
    staging_url: str | None = "https://dist.apache.org/repos/dist/dev/airflow/2.12.0-rc1/",
    method: str = "custom",
    fmt: str = "tar.gz",
    prefix: str = "",
    build_command: str | None = "python -m build --sdist",
    repro_source: str = "off",
    repro_binaries: str = "off",
    signing_mode: str = "rm-key",
    remote: str = "origin",
    vote_backend: str = "manual",
    convenience: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artefacts = artefacts or [("apache_airflow-2.12.0.tar.gz", "source")]
    return {
        "config": config or {},
        "build": {"expected_artefacts": [{"name": n, "kind": k} for n, k in artefacts]},
        "metadata": {
            "version": version,
            "rc_number": rc,
            "build_command": build_command,
            "expected_artefacts": [n for n, _ in artefacts],
            "digest_set": digests or ["sha512"],
            "backend": backend,
            "vote_backend": vote_backend,
            "staging_url": staging_url,
            "signing_key_fingerprint": FP,
            "release_branch": "main",
            "git_upstream_remote": remote,
            "source_archive_method": method,
            "source_archive_format": fmt,
            "source_archive_prefix": prefix,
            "reproducibility_source": repro_source,
            "reproducibility_binaries": repro_binaries,
            "signing_mode": signing_mode,
            "convenience_artefacts": convenience or [],
        },
    }


def cut(**kw: Any) -> render.RcCut:
    upstream = kw.pop("upstream", "apache/airflow")
    return render.RcCut.from_load(loaded(**kw), upstream=upstream, project="airflow")


WORKING_TREE_PACK = re.compile(r"zip -r|tar czf|tar -czf|tar cz")


def assert_step2_common(out: dict[str, Any], digests: set[str]) -> None:
    assert "git tag -s" in out["section_1_tag_commands"] and "git push" in out["section_1_tag_commands"]
    assert "SOURCE_DATE_EPOCH" in out["section_2_build_command"]
    assert not WORKING_TREE_PACK.search(out["section_2_build_command"])
    assert out["section_3_sign_commands"] and all(
        c.startswith("gpg --detach-sign --armor ") for c in out["section_3_sign_commands"]
    )
    assert not any("--passphrase" in c for c in out["section_3_sign_commands"])
    sums = " ".join(out["section_4_checksum_commands"])
    assert {d for d in ("sha512", "sha256") if f"{d}sum" in sums} == digests
    assert "md5sum" not in sums and "sha1sum" not in sums
    assert out["prohibited_digests_omitted"] is True and out["proposed"] is True


# --- step-2-tag-build-sign ------------------------------------------------- #


def test_step2_case_1_svnpubsub_sha512() -> None:
    out = render.step2(cut())
    assert_step2_common(out, {"sha512"})
    assert "python -m build --sdist" in out["section_2_build_command"]
    assert (
        'export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct "2.12.0-rc1")"' in out["section_2_build_command"]
    )
    assert out["section_1_tag_commands"].splitlines()[1] == '  -m "Release 2.12.0 RC1" \\'


def test_step2_case_2_sha512_and_sha256() -> None:
    artefacts = [
        ("apache-myproject-2.12.0-source-release.zip", "source"),
        ("apache-myproject-2.12.0-bin.tar.gz", "convenience"),
    ]
    out = render.step2(
        cut(
            artefacts=artefacts,
            digests=["sha512", "sha256"],
            build_command="mvn -Papache-release clean install",
        )
    )
    assert_step2_common(out, {"sha512", "sha256"})
    assert len(out["section_3_sign_commands"]) == 2
    assert (
        "sha256sum apache-myproject-2.12.0-bin.tar.gz > apache-myproject-2.12.0-bin.tar.gz.sha256"
        in out["section_4_checksum_commands"]
    )


def test_step2_case_3_prohibited_digest_refused() -> None:
    artefacts = [
        ("apache-myproject-3.0.0-source-release.zip", "source"),
        ("apache-myproject-3.0.0-bin.tar.gz", "convenience"),
    ]
    out = render.step2(cut(version="3.0.0", rc="rc2", artefacts=artefacts, backend="github-releases"))
    assert_step2_common(out, {"sha512"})
    with pytest.raises(render.RenderError, match="prohibited digest"):
        render.step2(cut(digests=["sha512", "md5"]))
    with pytest.raises(render.RenderError, match="prohibited digest"):
        render.step2(cut(digests=["sha1"]))


def test_step2_case_4_git_archive_reproducible() -> None:
    c = cut(
        version="1.0.0",
        artefacts=[("apache-foo-1.0.0-source.tar.gz", "source")],
        method="git-archive",
        prefix="apache-foo-1.0.0",
        build_command=None,
        repro_source="on",
        remote="apache",
        upstream="apache/foo",
    )
    out = render.step2(c)
    build = out["section_2_build_command"]
    assert "repro-archive build" in build and '--ref "1.0.0-rc1" --format tar.gz' in build
    assert '--prefix "apache-foo-1.0.0"' in build and '-o "apache-foo-1.0.0-source.tar.gz"' in build
    assert '--origin "https://github.com/apache/foo"' in build
    assert "# no convenience artefacts declared" in build
    assert "git push apache 1.0.0-rc1" in out["section_1_tag_commands"]
    assert not WORKING_TREE_PACK.search(build)


def test_step2_warns_when_source_extension_does_not_match_format() -> None:
    out = render.step2(
        cut(method="git-archive", fmt="zip", artefacts=[("apache-foo-1.0.0-source.tar.gz", "source")])
    )
    assert out["warnings"]


def test_step2_ci_automated_omits_sign_and_checksums() -> None:
    out = render.step2(cut(signing_mode="ci-automated"))
    assert out["section_3_sign_commands"] == [] and out["section_4_checksum_commands"] == []
    assert out["next_step"] == "2c"


def test_step2_convenience_artefact_gets_its_own_block() -> None:
    entry = {
        "name": "apache_foo-<version>-py3-none-any.whl",
        "kind": "wheel",
        "build_command": "python -m build --wheel",
    }
    out = render.step2(cut(convenience=[entry]))
    assert (
        "# Convenience artefact: apache_foo-2.12.0-py3-none-any.whl (wheel)" in out["section_2_build_command"]
    )
    assert "python -m build --wheel" in out["section_2_build_command"]


# --- step-2b-reproducibility ------------------------------------------------ #


def test_step2b_case_1_source_only() -> None:
    c = cut(
        version="1.0.0",
        artefacts=[("apache-foo-1.0.0-source.tar.gz", "source")],
        method="git-archive",
        prefix="apache-foo-1.0.0",
        repro_source="on",
    )
    out = render.step2b(c, epoch="1758326400")
    assert (
        out["source_check_enabled"] is True
        and out["binary_check_mode"] == "off"
        and out["mandatory"] is False
    )
    cmds = " ".join(out["source_check_commands"])
    assert "repro-archive check" in cmds and "repro-archive build" in cmds and "repro-archive compare" in cmds
    assert "--require-identical" in cmds and "rebuild/apache-foo-1.0.0-source.tar.gz" in cmds
    assert not WORKING_TREE_PACK.search(cmds)
    assert out["binary_check_commands"] == [] and "differs" in out["stop_on"] and out["proposed"] is True


def test_step2b_case_2_source_and_binaries_ci_signed() -> None:
    build = 'mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean package'
    entry = {
        "name": "apache-foo-3.2.0-bin.tar.gz",
        "kind": "binary-tarball",
        "staging": "dist-dev",
        "reproducibility": "byte-identical",
        "build_command": build,
    }
    c = cut(
        version="3.2.0",
        rc="rc2",
        artefacts=[
            ("apache-foo-3.2.0-source.tar.gz", "source"),
            ("apache-foo-3.2.0-bin.tar.gz", "convenience"),
        ],
        method="git-archive",
        prefix="apache-foo-3.2.0",
        build_command=build,
        repro_source="on",
        repro_binaries="byte-identical",
        signing_mode="ci-automated",
        convenience=[entry],
    )
    out = render.step2b(c, skip=True, epoch="1758412800")  # the RM's --skip-repro-check is ignored here
    assert out["mandatory"] is True and out["skipped"] is False
    assert out["source_check_enabled"] is True and out["binary_check_mode"] == "byte-identical"
    binary = " ".join(out["binary_check_commands"])
    assert 'export SOURCE_DATE_EPOCH="1758412800"' in binary and re.search(
        r"cmp |sha512sum|diffoscope", binary
    )
    assert "differs" in out["stop_on"]


def test_step2b_case_3_checks_off() -> None:
    out = render.step2b(cut())
    assert (
        out["source_check_enabled"] is False
        and out["binary_check_mode"] == "off"
        and out["mandatory"] is False
    )
    assert (
        out["source_check_commands"] == [] and out["binary_check_commands"] == [] and out["proposed"] is True
    )


def test_step2b_skip_flag_skips_under_rm_key() -> None:
    out = render.step2b(cut(repro_source="on", method="git-archive"), skip=True)
    assert out["skipped"] is True and out["source_check_commands"] == []


def test_step2b_documented_divergence_runs_the_verification_command() -> None:
    entry = {
        "name": "foo.whl",
        "reproducibility": "documented-divergence",
        "build_command": "make wheel",
        "verification_command": "diffoscope foo.whl rebuild/foo.whl",
    }
    out = render.step2b(cut(repro_binaries="byte-identical", convenience=[entry]))
    assert "diffoscope foo.whl rebuild/foo.whl" in out["binary_check_commands"]


# --- step-2c --------------------------------------------------------------- #


def test_step2c_ci_signed_flow() -> None:
    c = cut(signing_mode="ci-automated", config={"ci_release_workflow": ".github/workflows/release.yml"})
    out = render.step2c(c)
    assert out["trigger_commands"][0] == "git push origin 2.12.0-rc1"
    assert "--workflow .github/workflows/release.yml" in out["trigger_commands"][1]
    assert out["local_sign_commands_omitted"] is True and out["trusted_hardware_validation_required"] is True
    with pytest.raises(render.RenderError):
        render.step2c(cut())


# --- step-3-staging --------------------------------------------------------- #


def test_step3_case_1_svnpubsub() -> None:
    out = render.step3(cut(), asf_id="rm")
    assert out["backend"] == "svnpubsub" and out["dist_dev_only"] is True and out["proposed"] is True
    assert "https://dist.apache.org/repos/dist/dev/airflow/2.12.0-rc1/" in out["staging_commands"][0]
    assert "--username rm" in out["staging_commands"][0]
    assert "dist/release/" not in out["staging_url"]
    assert out["atr_upload_commands"] == []


def test_step3_case_2_github_releases() -> None:
    artefacts = [("apache-myproject-3.0.0-source-release.zip", "source")]
    out = render.step3(
        cut(
            version="3.0.0",
            artefacts=artefacts,
            backend="github-releases",
            staging_url="github-releases://apache/myproject/3.0.0-rc1",
            upstream="apache/myproject",
        )
    )
    assert out["backend"] == "github-releases" and out["dist_dev_only"] is False
    assert (
        "gh release create 3.0.0-rc1" in out["staging_commands"][0]
        and "--prerelease" in out["staging_commands"][0]
    )
    assert "apache-myproject-3.0.0-source-release.zip.asc" in out["staging_commands"][1]
    assert "dist/release/" not in out["staging_url"]


def test_step3_case_3_injection_attempt_cannot_reach_dist_release() -> None:
    """The planning issue asked to stage straight to dist/release/. The renderer
    only ever reads the configured staging_url, and refuses a dist/release/ one."""
    out = render.step3(cut())
    assert out["dist_dev_only"] is True and "dist/release/" not in json.dumps(out["staging_commands"])
    with pytest.raises(render.RenderError, match="denylist"):
        render.step3(cut(staging_url="https://dist.apache.org/repos/dist/release/airflow/2.12.0/"))


def test_step3_atr_upload_block_without_finish() -> None:
    out = render.step3(cut(vote_backend="atr"))
    joined = "\n".join(out["atr_upload_commands"])
    assert "atr upload airflow 2.12.0 apache_airflow-2.12.0.tar.gz.asc" in joined
    assert "finish" not in joined and "atr check status" in joined


def test_step3_registry_staging_uses_stage_command() -> None:
    entry = {
        "name": "foo.whl",
        "staging": "registry-staging",
        "stage_command": "twine upload -r testpypi foo.whl",
    }
    out = render.step3(cut(convenience=[entry]))
    assert out["registry_staging_commands"] == ["twine upload -r testpypi foo.whl"]


def test_step3_refused_under_ci_automated_and_for_self_hosted_without_template() -> None:
    with pytest.raises(render.RenderError):
        render.step3(cut(signing_mode="ci-automated"))
    with pytest.raises(render.RenderError, match="release_publish_command_template"):
        render.step3(cut(backend="self-hosted"))
    out = render.step3(
        cut(
            backend="self-hosted",
            config={"release_publish_command_template": "rsync -a dist/ host:/rc/<version>-<rcN>/"},
        )
    )
    assert out["staging_commands"] == ["rsync -a dist/ host:/rc/2.12.0-rc1/"]


# --- Step 0 tag check and Step 4 comment ------------------------------------ #


def test_step0_case_6_tag_prefix_not_exact() -> None:
    refs = "refs/tags/2.12.0-rc10\nrefs/tags/2.12.0-rc11\n"
    assert render.tag_exists(refs, "2.12.0-rc1") is False
    assert render.tag_exists(refs + "refs/tags/2.12.0-rc1\n", "2.12.0-rc1") is True


def test_step4_comment_records_the_reproducibility_record() -> None:
    printed = (
        "wrote apache-foo-1.0.0-source.tar.gz\ncommit 1890a13d\nSOURCE_DATE_EPOCH 1758326400\nsha512 abc\n"
        "swhid_rev swh:1:rev:1890;origin=https://github.com/apache/foo\nswhid_dir swh:1:dir:22;origin=x;anchor=y\n"
        "swhid_dir_note identical to the repository tree at the commit (nothing export-ignored)\n"
    )
    out = render.step4(
        cut(upstream="apache/foo"),
        record=render.parse_record(printed),
        allow_unreviewed_archive="first release",
    )
    body = out["comment"]
    for needle in (
        "2.12.0-rc1",
        "dist/dev/airflow/2.12.0-rc1",
        "`1890a13d`",
        "`1758326400`",
        "swh:1:dir:22",
        "rc-staging",
        "not reviewed",
    ):
        assert needle in body
    assert out["record_missing"] == [] and out["proposed_label"] == "rc-staging" and out["proposed"] is True


def test_step4_flags_what_the_rm_has_not_pasted_back() -> None:
    out = render.step4(cut())
    assert set(out["record_missing"]) == {"commit", "SOURCE_DATE_EPOCH", "sha512", "swhid_dir"}


# --- CLI ------------------------------------------------------------------- #


def test_cli_render_and_refusal(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    assert (
        main(
            ["rc-cut", "render", "--step", "3", "--load", str(load), "--project", "airflow", "--asf-id", "rm"]
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["dist_dev_only"] is True
    load.write_text(
        json.dumps(loaded(staging_url="https://dist.apache.org/repos/dist/release/airflow/2.12.0/")),
        encoding="utf-8",
    )
    assert main(["rc-cut", "render", "--step", "3", "--load", str(load)]) == 2
    assert "denylist" in json.loads(capsys.readouterr().out)["refused"]


def test_cli_tag_exists(tmp_path, capsys) -> None:
    refs = tmp_path / "refs.txt"
    refs.write_text("refs/tags/2.12.0-rc10\n", encoding="utf-8")
    assert main(["rc-cut", "tag-exists", "--refs", str(refs), "2.12.0-rc1"]) == 0
    assert json.loads(capsys.readouterr().out)["rc_tag_exists"] is False
