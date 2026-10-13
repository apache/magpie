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
"""release-promote: the Step 0 verdict and the Step 2 command set.

The scripted cases of the retired model-graded suites `step-0-preflight`
(cases 1 to 3) and `step-2-emit-commands` (cases 1, 2, 3 and 5) live here, named
after each former case, with the same scenario and the same assertions.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from release_management.cli import main
from release_management.promote import render

FP = "ABCD1234EF5678901234ABCD1234EF5678901234"
SHA = "9988776655443322110000ffeeddccbbaa998877"


def preflight(
    *,
    rm_is_pmc: bool | None = True,
    non_asf: bool = False,
    backend: str = "svnpubsub",
    trusted: bool = False,
    blockers: list[str] | None = None,
    version: str = "2.11.0",
    rc: str = "rc1",
) -> dict[str, Any]:
    return {
        "ok": not blockers,
        "skill": "promote",
        "blockers": blockers or [],
        "warnings": [],
        "values": {
            "roster_path": ".apache-magpie-overrides/pmc-roster.md",
            "rm_identity": "johndoe",
            "version": version,
            "rc": rc,
            "non_asf": non_asf,
            "rm_is_pmc": rm_is_pmc,
            "dist_backend": backend,
            "staging_url": f"https://dist.apache.org/repos/dist/dev/airflow/{version}-{rc}/",
            "target_url": f"https://dist.apache.org/repos/dist/release/airflow/{version}/",
            "trusted_hardware_attestation_required": trusted,
            "handoff_non_pmc": rm_is_pmc is False and not non_asf,
        },
    }


def loaded(
    *,
    version: str = "2.11.0",
    rc: str = "rc1",
    backend: str = "svnpubsub",
    template: str = "https://dist.apache.org/repos/dist/<bucket>/airflow/<version>/",
    staging_url: str | None = None,
    target_url: str | None = None,
    command_template: str | None = None,
    fingerprint: str | None = FP,
    remote: str | None = "origin",
    publish: list[dict[str, Any]] | None = None,
    held: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    staging = staging_url or template.replace("<bucket>", "dev").replace("<version>", f"{version}-{rc}")
    target = target_url or template.replace("<bucket>", "release").replace("<version>", version)
    return {
        "metadata": {
            "version": version,
            "rc": rc,
            "dist_backend": backend,
            "dist_url_template": template,
            "staging_url": staging,
            "target_url": target,
            "promote_command_template": command_template,
            "rm_gpg_fingerprint": fingerprint,
            "git_upstream_remote": remote,
            "convenience_artefacts": [],
            "convenience": {"publish": publish or [], "held": held or []},
        }
    }


def promote(upstream: str = "apache/airflow", project: str = "airflow", **kw: Any) -> render.Promote:
    product = kw.pop("product", "Apache Airflow")
    return render.Promote.from_load(loaded(**kw), upstream=upstream, project=project, product_name=product)


def matches(pattern: str, text: str, flags: int = re.I) -> bool:
    return re.search(pattern, text, flags) is not None


# --- step-0-preflight ------------------------------------------------------ #


def test_step0_case_1_clean_pass() -> None:
    out = render.verdict(preflight(), vote_passed=True, target_populated=False)
    assert {k: out[k] for k in out if k != "read"} == {
        "verdict": "proceed",
        "blockers": [],
        "rm_is_pmc": True,
        "non_asf": False,
        "version": "2.11.0",
        "rc": "rc1",
        "dist_backend": "svnpubsub",
    }
    assert out["read"] == []


def test_step0_case_2_not_vote_passed() -> None:
    out = render.verdict(preflight(), vote_passed=False, target_populated=False)
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["planning issue does not carry vote-passed label"]
    assert out["rm_is_pmc"] is True


def test_step0_case_3_non_pmc_rm() -> None:
    out = render.verdict(preflight(rm_is_pmc=False), vote_passed=True, target_populated=False)
    assert out["verdict"] == "handoff-non-pmc"
    assert out["blockers"] == [] and out["rm_is_pmc"] is False
    assert out["read"] == ["outcomes/handoff-non-pmc.md"]


def test_step0_case_4_target_url_exists() -> None:
    out = render.verdict(preflight(), vote_passed=True, target_populated=True)
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["target URL dist/release/airflow/2.11.0/ already contains content"]
    assert out["read"] == ["blockers/target-exists.md"]


def test_step0_non_pmc_with_a_blocker_is_blocked_not_handoff() -> None:
    out = render.verdict(preflight(rm_is_pmc=False), vote_passed=False, target_populated=False)
    assert out["verdict"] == "blocked"


def test_step0_tool_blockers_pass_through_and_unknown_rm_is_not_pmc() -> None:
    out = render.verdict(
        preflight(rm_is_pmc=None, blockers=["RM identity unknown for the PMC gate"]),
        vote_passed=True,
        target_populated=False,
    )
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["RM identity unknown for the PMC gate"]
    assert out["rm_is_pmc"] is False


def test_step0_non_asf_skips_the_pmc_gate() -> None:
    out = render.verdict(
        preflight(rm_is_pmc=None, non_asf=True, backend="github-releases"),
        vote_passed=True,
        target_populated=False,
    )
    assert out["verdict"] == "proceed" and out["rm_is_pmc"] is True and out["non_asf"] is True


def test_step0_no_planning_issue_blocks() -> None:
    out = render.verdict(preflight(), vote_passed=True, target_populated=False, planning_issue_found=False)
    assert out["verdict"] == "blocked" and "no planning issue found" in out["blockers"][0]


def test_step0_trusted_hardware_attestation() -> None:
    url = "https://github.com/apache/airflow/issues/45010"
    blocked = render.verdict(
        preflight(trusted=True), vote_passed=True, target_populated=False, planning_issue=url
    )
    assert blocked["verdict"] == "blocked"
    assert blocked["blockers"][0].startswith(
        "automated release signing requires every artefact to be rebuilt bit-by-bit identical on trusted hardware"
    )
    assert f"release-verify-rc 2.11.0-rc1 --trusted-hardware --post-to {url}" in blocked["blockers"][0]
    assert blocked["read"] == ["blockers/trusted-hardware.md"]
    ok = render.verdict(preflight(trusted=True), vote_passed=True, target_populated=False, attestation=True)
    assert ok["verdict"] == "proceed"
    # Not required → never mentioned.
    assert render.verdict(preflight(), vote_passed=True, target_populated=False)["blockers"] == []


# --- step-2-emit-commands -------------------------------------------------- #


def assert_common(out: dict[str, Any]) -> None:
    assert out["proposed_label"] == "promoted"
    assert out["mirror_note_present"] is True
    assert render.MIRROR_NOTE in out["command_block"]
    assert "at least 1 hour after the promote commit" in out["command_block"]


def test_step2_case_1_svnpubsub() -> None:
    out = render.step2(
        promote(),
        apache_id="johndoe",
        result_vote_url="https://lists.apache.org/thread/result-vote-thread-abc123",
        rc_commit_sha=SHA,
    )
    block = out["command_block"]
    assert out["staging_url"] == "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/"
    assert out["target_url"] == "https://dist.apache.org/repos/dist/release/airflow/2.11.0/"
    assert out["dist_backend"] == "svnpubsub" and out["rm_is_pmc"] is True and out["handoff_note"] is None
    assert_common(out)
    assert matches(r"svn\s+mv", block)  # has_svn_mv_command
    assert matches(r"dist/dev/airflow/2\.11\.0-rc1", block)  # has_correct_source_url
    assert matches(r"dist/release/airflow/2\.11\.0/", block)  # has_correct_target_url
    assert matches(r"-m[\s\S]{0,300}result-vote-thread-abc123", block)  # has_result_vote_url_in_commit_msg
    # has_no_direct_dist_release_write: svn mv from dev to release; no import / cp / put into release.
    assert not matches(r"svn\s+(import|cp|copy|put)", block)
    assert '-m "Promoting Apache Airflow 2.11.0 (from rc1). [RESULT]: ' in block
    assert f"git -c gpg.format=openpgp tag -s -u {FP} \\\n  2.11.0 {SHA} \\" in block
    assert "git push origin refs/tags/2.11.0" in block
    assert "--username johndoe" in block
    assert out["warnings"] == []
    # Paste-ready: no comment after a line-continuation backslash.
    assert not re.search(r"\\[ \t]+#", block)


def test_step2_case_2_github_releases() -> None:
    p = render.Promote.from_load(
        loaded(
            version="1.5.0",
            rc="rc2",
            backend="github-releases",
            template="https://github.com/example-org/example-project/releases/tag/<version>",
        ),
        upstream="example-org/example-project",
        project="example-project",
        product_name="Example Project",
    )
    out = render.step2(p)
    block = out["command_block"]
    assert out["staging_url"] == "https://github.com/example-org/example-project/releases/tag/1.5.0-rc2"
    assert out["target_url"] == "https://github.com/example-org/example-project/releases/tag/1.5.0"
    assert out["handoff_note"] is None and out["rm_is_pmc"] is True
    assert_common(out)
    assert matches(r"gh\s+release\s+edit", block)  # has_gh_release_edit_command
    assert matches(r"--draft[ =]false", block)  # has_draft_false_flag
    assert not matches(r"svn\s+mv", block)  # has_no_svn_mv_command
    assert "gh release edit 1.5.0-rc2 \\\n  --repo example-org/example-project" in block
    assert "--tag 1.5.0" in block and "gh release view 1.5.0 --repo example-org/example-project" in block


def test_step2_github_releases_tag_discrepancy_needs_confirmation() -> None:
    p = render.Promote.from_load(
        loaded(version="1.5.0", rc="rc2", backend="github-releases"), upstream="o/r", product_name="X"
    )
    with pytest.raises(render.RenderError, match=r"tagged v1\.5\.0-rc2, not 1\.5\.0-rc2"):
        render.step2(p, draft_tag="v1.5.0-rc2")
    out = render.step2(p, draft_tag="v1.5.0-rc2", draft_tag_confirmed=True)
    assert "gh release edit v1.5.0-rc2 \\" in out["command_block"]


def test_step2_case_3_s3() -> None:
    p = render.Promote.from_load(
        loaded(version="3.2.0", rc="rc1", backend="s3", template="s3://releases-example-org/<version>/"),
        upstream="example-org/example",
        product_name="Example",
    )
    out = render.step2(p)
    block = out["command_block"]
    assert out["staging_url"] == "s3://releases-example-org/3.2.0-rc1/"
    assert out["target_url"] == "s3://releases-example-org/3.2.0/"
    assert out["handoff_note"] is None
    assert_common(out)
    assert matches(r"aws\s+s3\s+mv", block)  # has_aws_s3_mv_command
    assert matches(r"--recursive", block)  # has_recursive_flag
    assert matches(r"s3://releases-example-org/3\.2\.0-rc1", block)  # has_correct_source_prefix
    assert matches(r"s3://releases-example-org/3\.2\.0/", block)  # has_correct_target_prefix


@pytest.mark.parametrize(
    ("template", "bucket"),
    [
        ("s3://bkt/<version>/", "bkt"),
        ("https://bkt.s3.eu-west-1.amazonaws.com/<version>/", "bkt"),
        ("https://s3.amazonaws.com/bkt/rel/<version>/", "bkt"),
    ],
)
def test_s3_bucket_from_template(template: str, bucket: str) -> None:
    assert render.s3_bucket(template) == bucket


def test_s3_bucket_unreadable_is_refused() -> None:
    with pytest.raises(render.RenderError, match="S3 bucket"):
        render.s3_bucket("https://downloads.example.org/<version>/")


def test_step2_case_5_convenience_artefacts() -> None:
    p = render.Promote.from_load(
        loaded(
            version="4.1.0",
            rc="rc2",
            template="https://dist.apache.org/repos/dist/<bucket>/foo/<version>/",
            remote="apache",
            publish=[
                {
                    "name": "apache-foo-4.1.0-bin.tar.gz",
                    "publish_channel": "dist-release",
                    "publish_command": None,
                },
                {
                    "name": "apache_foo-4.1.0-py3-none-any.whl",
                    "publish_channel": "pypi",
                    "publish_command": "twine upload dist/apache_foo-4.1.0-py3-none-any.whl",
                },
            ],
            held=[{"name": "registry.example.org/apache/foo:4.1.0", "reason": "differs"}],
        ),
        upstream="apache/foo",
        project="foo",
        product_name="Apache Foo",
    )
    out = render.step2(
        p,
        apache_id="jdoe",
        result_vote_url="https://lists.apache.org/thread/result-vote-foo-410",
        rc_commit_sha=SHA,
    )
    block = out["command_block"]
    assert out["staging_url"] == "https://dist.apache.org/repos/dist/dev/foo/4.1.0-rc2/"
    assert out["target_url"] == "https://dist.apache.org/repos/dist/release/foo/4.1.0/"
    assert out["handoff_note"] is None
    assert_common(out)
    assert matches(r"svn\s+mv", block) and not matches(r"svn\s+(import|cp|put)", block)
    publish = "\n".join(out["convenience_publish_commands"])
    assert re.search(
        r"twine upload dist/apache_foo-4\.1\.0-py3-none-any\.whl", publish
    )  # has_wheel_publish_command
    assert re.search(
        r"registry\.example\.org/apache/foo:4\.1\.0", "\n".join(out["convenience_held"])
    )  # has_image_held
    assert "docker push" not in publish and "docker push" not in block  # has_no_publish_for_held_artefact
    assert out["convenience_publish_commands"] == [
        "apache-foo-4.1.0-bin.tar.gz: promoted with the source",
        "apache_foo-4.1.0-py3-none-any.whl: twine upload dist/apache_foo-4.1.0-py3-none-any.whl",
    ]
    assert out["convenience_held"] == ["registry.example.org/apache/foo:4.1.0: differs"]
    assert "HOLD: registry.example.org/apache/foo:4.1.0 — not published." in block
    assert "git push apache refs/tags/4.1.0" in block
    # The convenience section comes after the source promotion and the final tag, before the mirror note.
    assert block.index("tag -v 4.1.0") < block.index("twine upload") < block.index("Mirror propagation")


def test_step2_source_only_has_no_convenience_section() -> None:
    out = render.step2(promote(), apache_id="a", result_vote_url="u", rc_commit_sha=SHA)
    assert out["convenience_publish_commands"] == [] and out["convenience_held"] == []
    assert "Convenience artefacts" not in out["command_block"]


def test_step2_handoff_non_pmc() -> None:
    out = render.step2(
        promote(),
        handoff=True,
        rm="johndoe",
        roster_path=".apache-magpie-overrides/pmc-roster.md",
        apache_id="johndoe",
        result_vote_url="u",
        rc_commit_sha=SHA,
    )
    assert out["rm_is_pmc"] is False
    assert out["handoff_note"].startswith("HAND-OFF: The distribution tree at dist/release/")
    assert (
        "johndoe does not appear on the PMC roster in\n.apache-magpie-overrides/pmc-roster.md."
        in out["handoff_note"]
    )
    assert "request PMC access from VP of airflow" in out["handoff_note"]
    block = out["command_block"]
    # The command block is still populated: a PMC member copies and runs it.
    assert block.startswith(out["handoff_note"]) and "svn mv \\" in block
    assert_common(out)


def test_step2_missing_facts_are_placeholders_with_warnings() -> None:
    out = render.step2(promote(fingerprint=None))
    block = out["command_block"]
    for placeholder in ("<apache_id>", "<result_vote_url>", "<rc-commit-sha>", "<rm_gpg_fingerprint>"):
        assert placeholder in block
    assert len(out["warnings"]) == 4


def test_step2_self_hosted() -> None:
    out = render.step2(
        promote(backend="self-hosted", command_template="./publish.sh --from <version>-<rcN> --to <version>")
    )
    assert "./publish.sh --from 2.11.0-rc1 --to 2.11.0" in out["command_block"]
    assert_common(out)


def test_step2_self_hosted_without_template_and_unknown_backend_are_refused() -> None:
    with pytest.raises(render.RenderError, match="release_publish_command_template is unset"):
        render.step2(promote(backend="self-hosted"))
    with pytest.raises(render.RenderError, match="unknown release_dist_backend"):
        render.step2(promote(backend="ftp"))


def test_apache_name_is_not_doubled() -> None:
    assert render.apache_name("Apache Airflow") == "Apache Airflow"
    assert render.apache_name("Airflow") == "Apache Airflow"


def test_cli_verdict_render_and_refusal(tmp_path, capsys) -> None:
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight()), encoding="utf-8")
    assert main(["promote", "verdict", "--preflight", str(pre), "--vote-passed"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "proceed"
    assert main(["promote", "verdict", "--preflight", str(pre)]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "blocked"
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    argv = [
        "promote",
        "render",
        "--load",
        str(load),
        "--project",
        "airflow",
        "--product-name",
        "Apache Airflow",
    ]
    assert main([*argv, "--apache-id", "johndoe", "--handoff", "--rm", "johndoe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["rm_is_pmc"] is False and out["handoff_note"]
    load.write_text(json.dumps(loaded(backend="self-hosted")), encoding="utf-8")
    assert main(argv) == 2
    assert "release_publish_command_template" in json.loads(capsys.readouterr().out)["refused"]


def test_planning_issue_values_cannot_expand_in_the_pasted_block() -> None:
    """The vote-result URL and the RC commit SHA come from the planning issue
    (external content): each is one inert shell word in the command block."""
    out = render.step2(
        promote(),
        apache_id="johndoe",
        result_vote_url='https://lists.apache.org/thread/x" ; touch pwned ; echo "',
        rc_commit_sha="$(touch pwned)",
    )
    block = out["command_block"]
    assert '\\" ; touch pwned ; echo \\"' in block
    assert "'$(touch pwned)'" in block
