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
import subprocess
from pathlib import Path
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
    out = render.step3(cut(), asf_id="rm")
    assert out["dist_dev_only"] is True and "dist/release/" not in json.dumps(out["staging_commands"])
    with pytest.raises(render.RenderError, match="denylist"):
        render.step3(cut(staging_url="https://dist.apache.org/repos/dist/release/airflow/2.12.0/"))


def test_step3_atr_upload_block_without_finish() -> None:
    out = render.step3(cut(vote_backend="atr"), asf_id="rm")
    joined = "\n".join(out["atr_upload_commands"])
    assert "atr upload airflow 2.12.0 apache_airflow-2.12.0.tar.gz.asc" in joined
    assert "finish" not in joined and "atr check status" in joined


def test_step3_registry_staging_uses_stage_command() -> None:
    entry = {
        "name": "foo.whl",
        "staging": "registry-staging",
        "stage_command": "twine upload -r testpypi foo.whl",
    }
    out = render.step3(cut(convenience=[entry]), asf_id="rm")
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
        "wrote apache-foo-1.0.0-source.tar.gz\ncommit 1890a13d\nSOURCE_DATE_EPOCH 1758326400\nsha512 "
        + "ab" * 64
        + "\n"
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


RENDER = ["rc-cut", "render", "--upstream", "apache/airflow", "--project", "airflow", "--step"]


def test_cli_render_and_refusal(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    assert main([*RENDER, "3", "--load", str(load), "--asf-id", "rm"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["dist_dev_only"] is True
    load.write_text(
        json.dumps(loaded(staging_url="https://dist.apache.org/repos/dist/release/airflow/2.12.0/")),
        encoding="utf-8",
    )
    assert main([*RENDER, "3", "--load", str(load)]) == 2
    assert "denylist" in json.loads(capsys.readouterr().out)["refused"]


def test_cli_tag_exists(tmp_path, capsys) -> None:
    refs = tmp_path / "refs.txt"
    refs.write_text("refs/tags/2.12.0-rc10\n", encoding="utf-8")
    assert main(["rc-cut", "tag-exists", "--refs", str(refs), "2.12.0-rc1"]) == 0
    assert json.loads(capsys.readouterr().out)["rc_tag_exists"] is False


def test_a_hostile_config_value_is_quoted_in_every_block() -> None:
    bad = "$(touch pwned)"
    c = cut(method="git-archive", prefix=bad, artefacts=[(f"foo{bad}.tar.gz", "source")], repro_source="on")
    step2 = render.step2(c)
    assert '--prefix "\\$(touch pwned)"' in step2["section_2_build_command"]
    assert "gpg --detach-sign --armor 'foo$(touch pwned).tar.gz'" in step2["section_3_sign_commands"]
    assert (
        "sha512sum 'foo$(touch pwned).tar.gz' > 'foo$(touch pwned).tar.gz.sha512'"
        in step2["section_4_checksum_commands"]
    )
    check = render.step2b(c, epoch="1")["source_check_commands"]
    assert any('check "foo\\$(touch pwned).tar.gz"' in cmd for cmd in check)


# --- Review regressions ---------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "https://dist.apache.org/repos/dist//release/airflow/2.12.0/",
        "https://dist.apache.org/repos/dist/dev/../release/airflow/2.12.0/",
        "https://dist.apache.org/repos/dist/dev/./../../dist/release/airflow/",
        "https://dist.apache.org/repos/dist/airflow/2.12.0-rc1/",
        "https://dist.apache.org/repos/dist/dev/",
        "https://dist.apache.org/elsewhere/dev/airflow/",
    ],
)
def test_step3_svnpubsub_requires_a_normalised_dist_dev_path(url: str) -> None:
    with pytest.raises(render.RenderError, match="Golden rule 5"):
        render.step3(cut(staging_url=url))


def test_step3_svnpubsub_accepts_a_dist_dev_path() -> None:
    url = "https://dist.apache.org/repos/dist/dev/airflow/./2.12.0-rc1/"
    assert render.step3(cut(staging_url=url), asf_id="rm")["dist_dev_only"] is True


@pytest.mark.parametrize("digest", ["sha384", "blake2b", "sha3-512", "crc32"])
def test_step2_refuses_any_digest_outside_the_allowlist(digest: str) -> None:
    with pytest.raises(render.RenderError, match="unsupported digest"):
        render.step2(cut(digests=["sha512", digest]))


def test_step2_digest_names_are_normalised() -> None:
    sums = render.step2(cut(digests=[" SHA512 ", "Sha256"]))["section_4_checksum_commands"]
    assert any(cmd.startswith("sha512sum ") for cmd in sums)
    assert any(cmd.startswith("sha256sum ") for cmd in sums)
    with pytest.raises(render.RenderError, match="prohibited digest"):
        render.step2(cut(digests=[" MD5"]))


def test_step2b_off_artefact_skip_lines_stay_in_text_only() -> None:
    c = cut(
        repro_source="on",
        convenience=[
            {"name": "foo.whl", "kind": "wheel", "build_command": "b", "reproducibility": "off"},
            {"name": "bar.whl", "kind": "wheel", "build_command": "b", "reproducibility": "byte-identical"},
        ],
    )
    out = render.step2b(c, epoch="1")
    assert not any("SKIP" in cmd for cmd in out["binary_check_commands"])
    assert any("bar.whl" in cmd for cmd in out["binary_check_commands"])
    assert "# SKIP: foo.whl (reproducibility off)" in out["text"]
    only_off = cut(
        repro_source="on",
        convenience=[{"name": "foo.whl", "build_command": "b", "reproducibility": "off"}],
    )
    out = render.step2b(only_off, epoch="1")
    assert out["binary_check_commands"] == [] and "# SKIP: foo.whl" in out["text"]


SHA = "a" * 128


def test_parse_record_first_occurrence_wins_and_sha512_must_be_hex() -> None:
    printed = f"commit 1890a13d\nsha512 {SHA}\nsha512 A {'b' * 128}\ncommit evil\n"
    record = render.parse_record(printed)
    assert record["sha512"] == SHA and record["commit"] == "1890a13d"
    assert "sha512" not in render.parse_record("sha512 A deadbeef\n")
    assert "sha512" not in render.parse_record("sha512 abc\n")
    assert render.parse_record(f"sha512 zz\nsha512 {SHA}\n")["sha512"] == SHA


CONVENIENCE = [
    {"name": "foo.whl", "kind": "wheel", "build_command": "b", "reproducibility": "off"},
    {"name": "bar.jar", "kind": "jar", "build_command": "b", "reproducibility": "byte-identical"},
]


def test_step4_convenience_outcomes_do_not_inherit_the_overall_self_check() -> None:
    out = render.step4(cut(convenience=CONVENIENCE), self_check="identical")
    body = out["comment"]
    assert "reproducibility `off` (skipped)" in body
    assert "reproducibility `byte-identical` (unreported)" in body
    assert "(identical)" not in body.split("#### Convenience artefacts")[1]
    out = render.step4(
        cut(convenience=CONVENIENCE), self_check="identical", convenience_outcomes={"bar.jar": "identical"}
    )
    assert "reproducibility `byte-identical` (identical)" in out["comment"]


def test_step4_self_check_has_no_default() -> None:
    assert "Self-check (Step 2b): unreported" in render.step4(cut())["comment"]
    assert "self_check" not in render.step4(cut())["record_missing"]
    for value in (None, "skipped"):
        out = render.step4(cut(signing_mode="ci-automated"), self_check=value)
        assert "self_check" in out["record_missing"]
    out = render.step4(cut(signing_mode="ci-automated"), self_check="identical")
    assert "self_check" not in out["record_missing"]


def test_cli_step4_convenience_outcome_and_self_check(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(
        json.dumps(loaded(signing_mode="ci-automated", convenience=CONVENIENCE)), encoding="utf-8"
    )
    assert main([*RENDER, "4", "--load", str(load), "--convenience-outcome", "bar.jar=identical"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "self_check" in out["record_missing"]
    assert "reproducibility `byte-identical` (identical)" in out["comment"]
    assert main([*RENDER, "4", "--load", str(load), "--convenience-outcome", "bar.jar"]) == 2
    assert "NAME=RESULT" in json.loads(capsys.readouterr().out)["refused"]


@pytest.mark.parametrize("missing", ["--upstream", "--project"])
def test_cli_render_requires_upstream_and_project(tmp_path, missing: str) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    argv = [*RENDER, "3", "--load", str(load)]
    i = argv.index(missing)
    del argv[i : i + 2]
    with pytest.raises(SystemExit):
        main(argv)


def test_tag_exists_unparsable_read_is_none() -> None:
    assert render.tag_exists("", "2.12.0-rc1") is False
    assert render.tag_exists("\n\n", "2.12.0-rc1") is False
    assert render.tag_exists("gh: HTTP 401: Bad credentials\n", "2.12.0-rc1") is None
    assert render.tag_exists("refs/tags/2.12.0-rc10\nerror: truncated\n", "2.12.0-rc1") is None


def test_cli_tag_exists_unparsable_read_blocks(tmp_path, capsys) -> None:
    refs = tmp_path / "refs.txt"
    refs.write_text("gh: HTTP 404: Not Found\n", encoding="utf-8")
    assert main(["rc-cut", "tag-exists", "--refs", str(refs), "2.12.0-rc1"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["rc_tag_exists"] is None and "rerun" in out["blocker"]


# --- Adversarial-review regressions ---------------------------------------- #

# A bare `<word>` in a pasted command is a shell redirect (`< word`), never a value.
BARE_PLACEHOLDER = re.compile(r"(?<![\"'\w])<[A-Za-z][A-Za-z0-9_ -]*>")


def bare_placeholders(commands: list[str] | str) -> list[str]:
    text = commands if isinstance(commands, str) else "\n".join(commands)
    return [
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#") and BARE_PLACEHOLDER.search(line.split(" #")[0])
    ]


def test_step3_svnpubsub_refuses_without_an_asf_id() -> None:
    for asf_id in (None, "", "  ", "<asf-id>"):
        with pytest.raises(render.RenderError, match="--asf-id"):
            render.step3(cut(), asf_id=asf_id)
    assert "--username rm" in render.step3(cut(), asf_id="rm")["staging_commands"][0]


def test_cli_step3_svnpubsub_without_asf_id_is_refused(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    assert main([*RENDER, "3", "--load", str(load)]) == 2
    assert "--asf-id" in json.loads(capsys.readouterr().out)["refused"]
    # Other backends need no ASF id.
    load.write_text(
        json.dumps(
            loaded(backend="github-releases", staging_url="github-releases://apache/airflow/2.12.0-rc1")
        ),
        encoding="utf-8",
    )
    assert main([*RENDER, "3", "--load", str(load)]) == 0


def test_step3_svnpubsub_command_has_no_bare_placeholder() -> None:
    staging = render.step3(cut(), asf_id="rm")["staging_commands"]
    assert bare_placeholders(staging) == []
    assert staging[0].startswith('svn import "<local-artefact-dir>/"')


def test_repro_commands_carry_a_quoted_framework_path_never_a_placeholder() -> None:
    c = render.RcCut.from_load(
        loaded(method="git-archive", repro_source="on", build_command="make bin"),
        upstream="apache/airflow",
        project="airflow",
        framework="/opt/magpie fw",
    )
    build = render.step2(c)["section_2_build_command"]
    tool = '"/opt/magpie fw/tools/reproducible-archive"'
    assert f"uv run --project {tool} repro-archive build" in build
    assert f'export SOURCE_DATE_EPOCH="$(uv run --project {tool} repro-archive epoch' in build
    check = render.step2b(c, epoch="1")
    assert all(tool in cmd for cmd in check["source_check_commands"] if "repro-archive" in cmd)
    assert "<framework>" not in build + check["text"]


def test_framework_defaults_to_the_checkout_the_tool_runs_from() -> None:
    root = render.default_framework()
    assert root is not None
    assert (render.Path(root) / "tools" / "reproducible-archive" / "pyproject.toml").is_file()
    assert cut().framework == root


def test_repro_commands_refuse_when_the_framework_is_unknown(monkeypatch) -> None:
    monkeypatch.setattr(render, "default_framework", lambda: None)
    c = cut(method="git-archive", repro_source="on")
    assert c.framework is None
    with pytest.raises(render.RenderError, match="--framework"):
        render.step2(c)
    with pytest.raises(render.RenderError, match="--framework"):
        render.step2b(c)
    # Custom archives also use repro-archive to record the shipped content's SWHID.
    with pytest.raises(render.RenderError, match="--framework"):
        render.step2(cut())


def test_cli_framework_flag_reaches_the_commands(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded(method="git-archive")), encoding="utf-8")
    assert main([*RENDER, "2", "--load", str(load), "--framework", "/srv/fw"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert 'uv run --project "/srv/fw/tools/reproducible-archive" repro-archive build' in out["text"]


POST1 = {
    "name": "apache_airflow-<version>-py3-none-any.whl",
    "kind": "wheel",
    "version": "<version>.post1",
    "build_command": "python -m build --wheel && echo <version>",
    "staging": "registry-staging",
    "stage_command": "twine upload -r testpypi dist/apache_airflow-<version>-py3-none-any.whl",
    "reproducibility": "documented-divergence",
    "verification_command": (
        "diffoscope apache_airflow-<version>-py3-none-any.whl rebuild/src/apache_airflow-<version>-py3-none-any.whl"
    ),
}


def test_convenience_commands_render_each_entry_with_its_own_version() -> None:
    c = cut(convenience=[POST1])
    assert c.convenience()[0]["name"] == "apache_airflow-2.12.0.post1-py3-none-any.whl"
    build = render.step2(c)["section_2_build_command"]
    assert "python -m build --wheel && echo 2.12.0.post1" in build
    staged = render.step3(c, asf_id="rm")["registry_staging_commands"]
    assert staged == ["twine upload -r testpypi dist/apache_airflow-2.12.0.post1-py3-none-any.whl"]
    binary = render.step2b(c, epoch="1")["binary_check_commands"]
    assert "(\ncd rebuild/src || exit\npython -m build --wheel && echo 2.12.0.post1\n)" in binary
    assert (
        "diffoscope apache_airflow-2.12.0.post1-py3-none-any.whl "
        "rebuild/src/apache_airflow-2.12.0.post1-py3-none-any.whl"
    ) in binary
    # A literal version renders the same way.
    literal = cut(convenience=[POST1 | {"version": "2.12.0.post1"}])
    assert "echo 2.12.0.post1" in render.step2(literal)["section_2_build_command"]
    # The source build keeps the source version.
    assert '%ct "2.12.0-rc1"' in build and "(apache_airflow-2.12.0.tar.gz*)" in build


@pytest.mark.parametrize("mode", ["byte-identical", "documented-divergence"])
def test_step2b_runs_for_an_entry_declaring_its_own_mode_when_both_globals_are_off(mode: str) -> None:
    entry = {"name": "foo.whl", "reproducibility": mode, "build_command": "make wheel"}
    out = render.step2b(cut(repro_source="off", repro_binaries="off", convenience=[entry]), epoch="7")
    assert out["skipped"] is False and out["source_check_commands"] == []
    binary = out["binary_check_commands"]
    assert "(\ncd rebuild/src || exit\nmake wheel\n)" in binary
    if mode == "byte-identical":
        assert any(cmd.startswith('cmp "foo.whl" "rebuild/src/foo.whl"') for cmd in binary)
    else:
        assert 'diffoscope "foo.whl" "rebuild/src/foo.whl"' in binary
    # Every entry off, and both globals off: nothing to check.
    off = render.step2b(cut(convenience=[entry | {"reproducibility": "off"}]))
    assert off["skipped"] is True


def test_step2b_rebuilds_in_a_checkout_of_the_tag_not_an_empty_dir() -> None:
    entry = {"name": "foo-bin.tar.gz", "reproducibility": "byte-identical", "build_command": "make dist"}
    custom = cut(repro_source="on", method="custom", build_command="make sdist", convenience=[entry])
    out = render.step2b(custom, epoch="9")
    prep = out["rebuild_tree_commands"]
    assert prep == ["mkdir -p rebuild", 'git worktree add --detach rebuild/src "2.12.0-rc1"']
    src = out["source_check_commands"]
    assert "(\ncd rebuild/src || exit\nmake sdist\n)" in src
    assert src[-1].endswith(
        '--require-identical "apache_airflow-2.12.0.tar.gz" "rebuild/src/apache_airflow-2.12.0.tar.gz"'
    )
    assert "(\ncd rebuild/src || exit\nmake dist\n)" in out["binary_check_commands"]
    assert out["cleanup_commands"] == ["git worktree remove --force rebuild/src"]
    text = out["text"]
    assert text.index("git worktree add") < text.index("make sdist") < text.index("make dist")
    assert text.index("make dist") < text.index("git worktree remove")
    assert "( cd rebuild && " not in text

    # git-archive: repro-archive rebuilds the source from the ref; binaries still build in the checkout.
    archive = cut(repro_source="on", method="git-archive", convenience=[entry])
    out = render.step2b(archive, epoch="9")
    assert out["rebuild_tree_commands"][1] == 'git worktree add --detach rebuild/src "2.12.0-rc1"'
    assert any('-o "rebuild/apache_airflow-2.12.0.tar.gz"' in cmd for cmd in out["source_check_commands"])
    assert "(\ncd rebuild/src || exit\nmake dist\n)" in out["binary_check_commands"]

    # Source-only git-archive needs no checkout at all.
    only = render.step2b(cut(repro_source="on", method="git-archive"), epoch="9")
    assert only["rebuild_tree_commands"] == [] and only["cleanup_commands"] == []


def test_step3_atr_dist_backend_composes_in_atr_only() -> None:
    c = cut(backend="atr", vote_backend="atr", staging_url=None, digests=["sha512", "sha256"])
    out = render.step3(c)  # no ASF id: the atr client carries the RM's own credentials
    staging = out["staging_commands"]
    assert staging[0] == "atr release start airflow 2.12.0"
    for suffix in ("", ".asc", ".sha512", ".sha256"):
        name = f"apache_airflow-2.12.0.tar.gz{suffix}"
        assert f"atr upload airflow 2.12.0 {name} {name}" in staging
    assert any(cmd.startswith("atr check status") for cmd in staging)
    assert out["atr_upload_commands"] == []  # the staging is the ATR upload: no second copy
    assert not any("finish" in cmd.lower() or cmd.startswith("svn ") for cmd in staging)
    assert out["dist_dev_only"] is False and out["backend"] == "atr"
    assert "Compose in ATR" in out["text"]


def test_no_rendered_command_carries_a_bare_placeholder_redirect() -> None:
    entry = {"name": "foo.whl", "reproducibility": "byte-identical", "build_command": "make wheel"}
    c = cut(
        method="git-archive",
        repro_source="on",
        repro_binaries="byte-identical",
        convenience=[entry],
        build_command="make bin",
    )
    assert bare_placeholders(render.step2(c)["section_2_build_command"]) == []
    out = render.step2b(c)
    assert (
        bare_placeholders(
            out["rebuild_tree_commands"] + out["source_check_commands"] + out["binary_check_commands"]
        )
        == []
    )
    assert bare_placeholders(render.step3(c, asf_id="rm")["staging_commands"]) == []


def test_step2c_refuses_without_a_release_workflow() -> None:
    with pytest.raises(render.RenderError, match="ci_release_workflow is unset"):
        render.step2c(cut(signing_mode="ci-automated"))


def test_step2c_run_id_placeholder_is_quoted_not_a_redirect() -> None:
    out = render.step2c(
        cut(signing_mode="ci-automated", config={"ci_release_workflow": ".github/workflows/release.yml"})
    )
    watch = next(line for line in out["text"].splitlines() if line.startswith("gh run watch"))
    assert watch.endswith('"<run-id>"')


@pytest.mark.parametrize("kind", ["source", "convenience"])
@pytest.mark.parametrize(
    "command",
    [
        "printf 'rebuilt\\n' > result.txt # archive build",
        "cat > result.txt <<'EOF'\nrebuilt\nEOF",
    ],
)
def test_rebuild_preserves_shell_comments_and_heredocs(tmp_path: Path, kind: str, command: str) -> None:
    entry = {"name": "result.txt", "reproducibility": "byte-identical", "build_command": command}
    c = cut(
        method="custom",
        repro_source="on" if kind == "source" else "off",
        build_command=command,
        convenience=[entry] if kind == "convenience" else [],
    )
    result = render.step2b(c, epoch="1")
    commands = result["source_check_commands" if kind == "source" else "binary_check_commands"]
    build = next(cmd for cmd in commands if cmd.startswith("(\n"))
    checkout = tmp_path / "rebuild/src"
    checkout.mkdir(parents=True)
    completed = subprocess.run(["sh", "-c", build], cwd=tmp_path, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert (checkout / "result.txt").read_text() == "rebuilt\n"
    assert not (tmp_path / "result.txt").exists()


def test_rebuild_stops_before_any_command_when_checkout_is_absent(tmp_path: Path) -> None:
    c = cut(
        method="custom",
        repro_source="on",
        build_command="printf wrong > first.txt\nprintf wrong > second.txt",
    )
    commands = render.step2b(c, epoch="1")["source_check_commands"]
    build = next(cmd for cmd in commands if cmd.startswith("(\n"))
    completed = subprocess.run(["sh", "-c", build], cwd=tmp_path, text=True, capture_output=True)
    assert completed.returncode != 0
    assert not (tmp_path / "first.txt").exists()
    assert not (tmp_path / "second.txt").exists()


@pytest.mark.parametrize("method", ["custom", "git-archive"])
def test_top_level_build_command_resolves_release_placeholders(method: str) -> None:
    command = "printf '%s' <version>-<rcN>"
    c = cut(method=method, build_command=command, repro_source="on")
    assert command not in render.step2(c)["section_2_build_command"]
    assert "printf '%s' 2.12.0-rc1" in render.step2(c)["section_2_build_command"]
    if method == "custom":
        assert "printf '%s' 2.12.0-rc1" in "\n".join(render.step2b(c)["source_check_commands"])


@pytest.mark.parametrize("status", ["differs", "DIFFERS", "verdict content-identical"])
def test_failed_self_check_cannot_propose_rc_staging(status: str) -> None:
    with pytest.raises(render.RenderError, match="failed reproducibility"):
        render.step4(cut(method="git-archive"), self_check=status)


def test_failed_convenience_check_cannot_propose_rc_staging() -> None:
    with pytest.raises(render.RenderError, match=r"foo\.whl failed reproducibility"):
        render.step4(cut(), self_check="identical", convenience_outcomes={"foo.whl": "DIFFERS"})


def test_content_identical_custom_archive_remains_a_warning_under_rm_key() -> None:
    c = cut(method="custom")
    assert render.step4(c, self_check="content-identical")["proposed_label"] == "rc-staging"
    c.meta["signing_mode"] = "ci-automated"
    with pytest.raises(render.RenderError, match="failed reproducibility"):
        render.step4(c, self_check="content-identical")


def test_binary_modes_reflect_entry_overrides_and_skipped_checks() -> None:
    entries = [
        {"name": "a.whl", "reproducibility": "byte-identical", "build_command": "make a"},
        {"name": "b.whl", "reproducibility": "documented-divergence", "build_command": "make b"},
    ]
    c = cut(repro_binaries="off", convenience=entries[:1])
    assert render.step2b(c)["binary_check_mode"] == "byte-identical"
    c = cut(repro_binaries="off", convenience=entries)
    result = render.step2b(c)
    assert result["binary_check_mode"] == "mixed"
    assert result["binary_check_modes"] == {"a.whl": "byte-identical", "b.whl": "documented-divergence"}
    skipped = render.step2b(c, skip=True)
    assert skipped["binary_check_mode"] == "off"
    assert skipped["binary_check_modes"] == {"a.whl": "off", "b.whl": "off"}


def test_documented_divergence_accepts_content_identical_but_byte_identity_does_not() -> None:
    entry = {"name": "foo.whl", "reproducibility": "documented-divergence"}
    c = cut(method="git-archive", convenience=[entry])
    result = render.step4(c, convenience_outcomes={"foo.whl": "content-identical"})
    assert result["proposed_label"] == "rc-staging"
    c.meta["convenience_artefacts"] = [entry | {"reproducibility": "byte-identical"}]
    with pytest.raises(render.RenderError, match="failed reproducibility"):
        render.step4(c, convenience_outcomes={"foo.whl": "content-identical"})
