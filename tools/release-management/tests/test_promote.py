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
    declared: list[dict[str, Any]] | None = None,
    digest_set: list[str] | None = None,
) -> dict[str, Any]:
    staging = staging_url or template.replace("<bucket>", "dev").replace("<version>", f"{version}-{rc}")
    target = target_url or template.replace("<bucket>", "release").replace("<version>", version)
    return {
        # `release-config load` prints the parsed release-build.md under `build`.
        "build": {"digest_set": digest_set or []},
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
            "convenience_artefacts": declared or [],
            "convenience": {"publish": publish or [], "held": held or []},
        },
    }


def promote(upstream: str = "apache/airflow", project: str = "airflow", **kw: Any) -> render.Promote:
    product = kw.pop("product", "Apache Airflow")
    return render.Promote.from_load(loaded(**kw), upstream=upstream, project=project, product_name=product)


AIRFLOW: dict[str, Any] = {"upstream": "apache/airflow", "project": "airflow"}


def matches(pattern: str, text: str, flags: int = re.I) -> bool:
    return re.search(pattern, text, flags) is not None


# --- step-0-preflight ------------------------------------------------------ #


def test_step0_case_1_clean_pass() -> None:
    out = render.verdict(preflight(), vote_passed=True, target="empty")
    assert {k: out[k] for k in out if k not in ("read", "scope")} == {
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
    out = render.verdict(preflight(), vote_passed=False, target="empty")
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["planning issue does not carry vote-passed label"]
    assert out["rm_is_pmc"] is True


def test_step0_case_3_non_pmc_rm() -> None:
    out = render.verdict(preflight(rm_is_pmc=False), vote_passed=True, target="empty")
    assert out["verdict"] == "handoff-non-pmc"
    assert out["blockers"] == [] and out["rm_is_pmc"] is False
    assert out["read"] == ["outcomes/handoff-non-pmc.md"]


def test_step0_case_4_target_url_exists() -> None:
    out = render.verdict(preflight(), vote_passed=True, target="populated")
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["target URL dist/release/airflow/2.11.0/ already contains content"]
    assert out["read"] == ["blockers/target-exists.md"]


def test_step0_non_pmc_with_a_blocker_is_blocked_not_handoff() -> None:
    out = render.verdict(preflight(rm_is_pmc=False), vote_passed=False, target="empty")
    assert out["verdict"] == "blocked"


def test_step0_tool_blockers_pass_through_and_unknown_rm_is_not_pmc() -> None:
    out = render.verdict(
        preflight(rm_is_pmc=None, blockers=["RM identity unknown for the PMC gate"]),
        vote_passed=True,
        target="empty",
    )
    assert out["verdict"] == "blocked"
    assert out["blockers"] == ["RM identity unknown for the PMC gate"]
    assert out["rm_is_pmc"] is False


def test_step0_non_asf_skips_the_pmc_gate() -> None:
    out = render.verdict(
        preflight(rm_is_pmc=None, non_asf=True, backend="github-releases"),
        vote_passed=True,
        target="empty",
    )
    assert out["verdict"] == "proceed" and out["rm_is_pmc"] is True and out["non_asf"] is True


def test_step0_no_planning_issue_blocks() -> None:
    out = render.verdict(preflight(), vote_passed=True, target="empty", planning_issue_found=False)
    assert out["verdict"] == "blocked" and "no planning issue found" in out["blockers"][0]


def test_step0_trusted_hardware_attestation() -> None:
    url = "https://github.com/apache/airflow/issues/45010"
    blocked = render.verdict(preflight(trusted=True), vote_passed=True, target="empty", planning_issue=url)
    assert blocked["verdict"] == "blocked"
    assert blocked["blockers"][0].startswith(
        "automated release signing requires every artefact to be rebuilt bit-by-bit identical on trusted hardware"
    )
    assert f"release-verify-rc 2.11.0-rc1 --trusted-hardware --post-to {url}" in blocked["blockers"][0]
    assert blocked["read"] == ["blockers/trusted-hardware.md"]
    ok = render.verdict(preflight(trusted=True), vote_passed=True, target="empty", attestation=True)
    assert ok["verdict"] == "proceed"
    # Not required → never mentioned.
    assert render.verdict(preflight(), vote_passed=True, target="empty")["blockers"] == []


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
    out = render.step2(p, draft_tag="1.5.0-rc2")
    block = out["command_block"]
    assert out["staging_url"] == "https://github.com/example-org/example-project/releases/tag/1.5.0-rc2"
    assert out["target_url"] == "https://github.com/example-org/example-project/releases/tag/1.5.0"
    assert out["handoff_note"] is None and out["rm_is_pmc"] is True
    assert_common(out)
    assert matches(r"gh\s+release\s+edit", block)  # has_gh_release_edit_command
    assert matches(r"--draft[ =]false", block)  # has_draft_false_flag
    # rc-cut drafts the release with --prerelease; publishing must clear it.
    assert "  --draft=false \\\n  --prerelease=false \\\n  --tag 1.5.0" in block
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


def test_step2_github_releases_without_draft_tag_is_refused() -> None:
    """The discrepancy check needs the tag the draft carries; without it, it would pass vacuously."""
    p = render.Promote.from_load(
        loaded(version="1.5.0", rc="rc2", backend="github-releases"), upstream="o/r", product_name="X"
    )
    with pytest.raises(render.RenderError, match="--draft-tag was not passed"):
        render.step2(p)
    with pytest.raises(render.RenderError, match="--draft-tag was not passed"):
        render.step2(p, draft_tag="", draft_tag_confirmed=True)


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
        ("https://s3.eu-west-1.amazonaws.com/bkt/<version>/", "bkt"),
        ("https://s3-eu-west-1.amazonaws.com/bkt/<version>/", "bkt"),
        # Virtual-hosted buckets whose own name starts with `s3` are not path-style.
        ("https://s3data.s3.us-east-1.amazonaws.com/rel/<version>/", "s3data"),
        ("https://s3-logs.s3.amazonaws.com/<version>/", "s3-logs"),
        # The bucket is everything before the LAST `.s3.` / `.s3-`.
        ("https://my.s3x.s3.amazonaws.com/<version>/", "my.s3x"),
        ("https://my.s3.data.s3-us-west-2.amazonaws.com/<version>/", "my.s3.data"),
        ("https://bkt.s3.dualstack.us-east-1.amazonaws.com/<version>/", "bkt"),
    ],
)
def test_s3_bucket_from_template(template: str, bucket: str) -> None:
    assert render.s3_bucket(template) == bucket


@pytest.mark.parametrize(
    "template",
    [
        "https://downloads.example.org/<version>/",
        "https://amazonaws.com/bkt/<version>/",
        "https://s3.amazonaws.com/",
        "https://bkt.s3.amazonaws.com.example.org/<version>/",
    ],
)
def test_s3_bucket_unreadable_is_refused(template: str) -> None:
    with pytest.raises(render.RenderError, match="S3 bucket"):
        render.s3_bucket(template)


@pytest.mark.parametrize(
    ("template", "staging", "target"),
    [
        ("s3://bkt/releases/<version>/", "s3://bkt/releases/3.2.0-rc1/", "s3://bkt/releases/3.2.0/"),
        ("https://s3.amazonaws.com/bkt/rel/<version>/", "s3://bkt/rel/3.2.0-rc1/", "s3://bkt/rel/3.2.0/"),
        (
            "https://bkt.s3.eu-west-1.amazonaws.com/a/b/<version>/",
            "s3://bkt/a/b/3.2.0-rc1/",
            "s3://bkt/a/b/3.2.0/",
        ),
        ("s3://bkt/<bucket>/<version>", "s3://bkt/dev/3.2.0-rc1/", "s3://bkt/release/3.2.0/"),
    ],
)
def test_step2_s3_keeps_the_template_key_prefix(template: str, staging: str, target: str) -> None:
    """Both `aws s3` URIs come from the rendered staging / target URLs, so a key prefix survives."""
    p = render.Promote.from_load(
        loaded(version="3.2.0", rc="rc1", backend="s3", template=template), upstream="o/r", product_name="X"
    )
    block = render.step2(p)["command_block"]
    assert f"aws s3 mv \\\n  {staging} \\\n  {target} \\\n  --recursive" in block
    assert f"aws s3 ls {target}" in block.splitlines()


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
            declared=[
                {"name": "apache-foo-<version>-bin.tar.gz", "publish_channel": "dist-release"},
                {"name": "apache_foo-<version>-py3-none-any.whl", "publish_channel": "pypi"},
                {"name": "registry.example.org/apache/foo:<version>", "publish_channel": "docker"},
            ],
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


# --- held artefacts staged with the source are left out of the promotion ---- #

HELD_BIN = "apache-foo-4.1.0-bin.tar.gz"
DECLARED_BIN = [{"name": "apache-foo-<version>-bin.tar.gz", "publish_channel": "dist-release"}]


def held_promote(backend: str, template: str, **kw: Any) -> render.Promote:
    return render.Promote.from_load(
        loaded(
            version="4.1.0",
            rc="rc2",
            backend=backend,
            template=template,
            held=[{"name": HELD_BIN, "reason": "differs"}],
            declared=kw.pop("declared", DECLARED_BIN),
            **kw,
        ),
        upstream="apache/foo",
        project="foo",
        product_name="Apache Foo",
    )


def test_step2_svnpubsub_removes_held_staged_artefacts_before_the_move() -> None:
    p = held_promote("svnpubsub", "https://dist.apache.org/repos/dist/<bucket>/foo/<version>/")
    out = render.step2(p, apache_id="jdoe", result_vote_url="u", rc_commit_sha=SHA)
    block = out["command_block"]
    dev = "https://dist.apache.org/repos/dist/dev/foo/4.1.0-rc2/"
    removal = (
        "svn rm \\\n"
        f"  {dev}{HELD_BIN} \\\n"
        f"  {dev}{HELD_BIN}.asc \\\n"
        f"  {dev}{HELD_BIN}.sha512 \\\n"
        "  --username jdoe \\\n"
        '  -m "Withholding unreproduced convenience artefacts from Apache Foo 4.1.0 (rc2)" &&\n'
    )
    assert removal in block
    # The removal runs first, and the && means a failed removal stops the svn mv.
    assert block.index("\nsvn rm \\") < block.index("\nsvn mv \\") < block.index("\nsvn list ")
    # Nothing, not even a comment, sits between the && and the svn mv it guards.
    assert '(rc2)" &&\nsvn mv \\\n' in block
    assert (
        "# Step 2 of 4 — move RC to release (release_dist_backend=svnpubsub), chained after Step 1" in block
    )
    assert "# Step 4 of 4 — cut and push the FINAL release tag" in block
    assert out["convenience_held"] == [f"{HELD_BIN}: differs"]
    assert "The svn rm above removes it, with its .asc and .sha512, from the RC directory" in block
    assert not re.search(r"\\[ \t]+#", block)


def test_step2_s3_excludes_held_staged_artefacts_from_the_move() -> None:
    block = render.step2(held_promote("s3", "s3://bkt/<version>/"))["command_block"]
    excludes = "".join(f"  --exclude {HELD_BIN}{s} \\\n" for s in ("", ".asc", ".sha512"))
    assert f"aws s3 mv \\\n  s3://bkt/4.1.0-rc2/ \\\n  s3://bkt/4.1.0/ \\\n{excludes}  --recursive" in block
    assert "The --exclude flags above leave it, with its .asc and .sha512, out of the aws s3 mv." in block


def test_step2_github_releases_deletes_held_assets_before_publishing() -> None:
    p = held_promote("github-releases", "https://github.com/apache/foo/releases/tag/<version>")
    block = render.step2(p, draft_tag="4.1.0-rc2")["command_block"]
    # The signature and checksum assets go with it, each chained to the publish.
    delete = "".join(
        f"gh release delete-asset 4.1.0-rc2 {HELD_BIN}{s} --repo apache/foo --yes &&\n"
        for s in ("", ".asc", ".sha512")
    )
    assert f"{delete}gh release edit 4.1.0-rc2 \\" in block
    assert block.index("delete-asset") < block.index("--draft=false")
    assert (
        "The delete-asset above removes it, with its .asc and .sha512, from the draft release before it is published."
        in block
    )


@pytest.mark.parametrize(
    ("digest_set", "suffixes", "text"),
    [
        (["sha512", "sha256"], ("", ".asc", ".sha512", ".sha256"), ".asc, .sha512 and .sha256"),
        (["sha256"], ("", ".asc", ".sha256"), ".asc and .sha256"),
        ([" SHA256 ", "sha512"], ("", ".asc", ".sha256", ".sha512"), ".asc, .sha256 and .sha512"),
        (None, ("", ".asc", ".sha512"), ".asc and .sha512"),
    ],
)
def test_step2_held_sidecars_follow_the_digest_set(
    digest_set: list[str] | None, suffixes: tuple[str, ...], text: str
) -> None:
    """rc-cut stages one `.<digest>` file per digest_set entry; every one is withheld with the artefact."""
    names = [f"{HELD_BIN}{s}" for s in suffixes]
    dev = "https://dist.apache.org/repos/dist/dev/foo/4.1.0-rc2/"

    svn = held_promote(
        "svnpubsub", "https://dist.apache.org/repos/dist/<bucket>/foo/<version>/", digest_set=digest_set
    )
    block = render.step2(svn, apache_id="jdoe", result_vote_url="u", rc_commit_sha=SHA)["command_block"]
    assert "svn rm \\\n" + "".join(f"  {dev}{n} \\\n" for n in names) + "  --username jdoe \\\n" in block
    assert f"# remove each, with its {text}, from the RC directory" in block
    assert f"The svn rm above removes it, with its {text}, from the RC directory" in block

    s3 = held_promote("s3", "s3://bkt/<version>/", digest_set=digest_set)
    block = render.step2(s3)["command_block"]
    excludes = "".join(f"  --exclude {n} \\\n" for n in names)
    assert f"  s3://bkt/4.1.0/ \\\n{excludes}  --recursive" in block
    assert f"The --exclude flags above leave it, with its {text}, out of the aws s3 mv." in block

    gh = held_promote(
        "github-releases", "https://github.com/apache/foo/releases/tag/<version>", digest_set=digest_set
    )
    block = render.step2(gh, draft_tag="4.1.0-rc2")["command_block"]
    deletes = "".join(f"gh release delete-asset 4.1.0-rc2 {n} --repo apache/foo --yes &&\n" for n in names)
    assert f"{deletes}gh release edit 4.1.0-rc2 \\" in block
    assert f"The delete-asset above removes it, with its {text}, from the draft release" in block


def test_step2_held_sidecars_refuse_a_digest_rc_cut_never_stages() -> None:
    p = held_promote("s3", "s3://bkt/<version>/", digest_set=["sha512", "md5"])
    with pytest.raises(render.RenderError, match=r"unsupported digest\(s\) 'md5'"):
        render.step2(p)
    # Without a held staged artefact the digest set is not needed, so it does not refuse.
    clean = render.Promote.from_load(
        loaded(backend="s3", template="s3://bkt/<version>/", digest_set=["md5"]),
        upstream="o/r",
        product_name="X",
    )
    assert "--exclude" not in render.step2(clean)["command_block"]


def test_step2_self_hosted_refuses_held_staged_artefacts() -> None:
    """The project template cannot be told to leave a file out, so the render refuses instead of claiming it did."""
    p = held_promote(
        "self-hosted", "https://downloads.example.org/<version>/", command_template="./publish.sh <version>"
    )
    with pytest.raises(
        render.RenderError, match=r"staged with the source \(apache-foo-4\.1\.0-bin\.tar\.gz\)"
    ):
        render.step2(p)


def test_step2_held_artefact_on_its_own_channel_is_not_removed_from_the_source() -> None:
    p = held_promote(
        "svnpubsub",
        "https://dist.apache.org/repos/dist/<bucket>/foo/<version>/",
        declared=[{"name": "apache-foo-<version>-bin.tar.gz", "publish_channel": "pypi"}],
    )
    block = render.step2(p, apache_id="jdoe", result_vote_url="u", rc_commit_sha=SHA)["command_block"]
    assert "svn rm" not in block and "# Step 1 of 3 — move RC to release" in block
    assert "approved. No publish command for it is emitted." in block


def test_step2_held_artefact_with_unknown_channel_is_treated_as_staged() -> None:
    """A held name no declared entry matches is assumed to sit with the source (fail-closed)."""
    p = held_promote("s3", "s3://bkt/<version>/", declared=[])
    assert f"--exclude {HELD_BIN} \\" in render.step2(p)["command_block"]


def test_step2_held_artefact_with_its_own_version_is_matched() -> None:
    p = render.Promote.from_load(
        loaded(
            version="4.1.0",
            rc="rc2",
            backend="s3",
            template="s3://bkt/<version>/",
            held=[{"name": "foo-chart-1.2.0.tgz", "reason": "not checked"}],
            declared=[{"name": "foo-chart-<version>.tgz", "version": "1.2.0", "publish_channel": "helm"}],
        ),
        upstream="apache/foo",
        product_name="Apache Foo",
    )
    assert "--exclude" not in render.step2(p)["command_block"]


@pytest.mark.parametrize("name", ["sub/dir.tar.gz", "apache-foo-*.tar.gz", "two words.tar.gz", ".."])
def test_step2_held_staged_name_that_cannot_be_excluded_safely_is_refused(name: str) -> None:
    p = render.Promote.from_load(
        loaded(backend="s3", template="s3://bkt/<version>/", held=[{"name": name, "reason": "differs"}]),
        upstream="o/r",
        product_name="X",
    )
    with pytest.raises(render.RenderError, match="cannot leave it out safely"):
        render.step2(p)


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


def test_step2_atr_backend_is_refused_explicitly() -> None:
    with pytest.raises(render.RenderError, match="does not support release_dist_backend atr yet") as exc:
        render.step2(promote(backend="atr"))
    assert "ATR's Finish step" in str(exc.value) and "unknown" not in str(exc.value)


# --- the Step 0 verdict gates the render ------------------------------------ #


def test_step0_target_check_not_run_blocks() -> None:
    """A skipped or errored target listing is a blocker, never an empty target (Golden rule 4)."""
    for target in (None, "", "unknown"):
        out = render.verdict(preflight(), vote_passed=True, target=target)
        assert out["verdict"] == "blocked"
        assert out["blockers"] == [
            "target URL check result unknown: list dist/release/airflow/2.11.0/ "
            "(svn list / gh release view / aws s3 ls) and pass --target empty or --target populated"
        ]
        assert out["read"] == []


def test_render_gate_refuses_a_blocked_or_foreign_verdict() -> None:
    p = promote()
    blocked = render.verdict(preflight(), vote_passed=False, target="empty", **AIRFLOW)
    with pytest.raises(render.RenderError, match="verdict is 'blocked'"):
        render.handoff_from_verdict(p, blocked)
    with pytest.raises(render.RenderError, match="verdict is None"):
        render.handoff_from_verdict(p, {})
    other = render.verdict(preflight(rc="rc2"), vote_passed=True, target="empty", **AIRFLOW)
    with pytest.raises(
        render.RenderError, match=r"verdict is for 2\.11\.0-rc2, but the load is for 2\.11\.0-rc1"
    ):
        render.handoff_from_verdict(p, other)


def test_verdict_records_which_release_it_is_for() -> None:
    out = render.verdict(preflight(), vote_passed=True, target="empty", **AIRFLOW)
    assert out["scope"] == {
        "project": "airflow",
        "upstream": "apache/airflow",
        "dist_backend": "svnpubsub",
        "staging_url": "https://dist.apache.org/repos/dist/dev/airflow/2.11.0-rc1/",
        "target_url": "https://dist.apache.org/repos/dist/release/airflow/2.11.0/",
    }


def test_render_gate_refuses_a_verdict_for_another_project_at_the_same_version() -> None:
    """Same version and RC is not enough: project, upstream, backend and URLs must match the load."""
    p = promote()
    foreign = preflight()
    foreign["values"]["staging_url"] = "https://dist.apache.org/repos/dist/dev/otherproj/2.11.0-rc1/"
    foreign["values"]["target_url"] = "https://dist.apache.org/repos/dist/release/otherproj/2.11.0/"
    cross = render.verdict(
        foreign, vote_passed=True, target="empty", upstream="apache/otherproj", project="otherproj"
    )
    with pytest.raises(
        render.RenderError, match=r"verdict is for project 'otherproj', but the load is for 'airflow'"
    ):
        render.handoff_from_verdict(p, cross)
    # Each field on its own is enough to refuse.
    same = render.verdict(preflight(), vote_passed=True, target="empty", **AIRFLOW)
    for key, value in (
        ("upstream", "apache/other"),
        ("dist_backend", "s3"),
        ("staging_url", "https://dist.apache.org/repos/dist/dev/other/2.11.0-rc1/"),
        ("target_url", "https://dist.apache.org/repos/dist/release/other/2.11.0/"),
    ):
        changed = same | {"scope": same["scope"] | {key: value}}
        with pytest.raises(render.RenderError, match=f"verdict is for {key} "):
            render.handoff_from_verdict(p, changed)
    # A verdict that does not record its release at all is refused, not trusted.
    with pytest.raises(render.RenderError, match="does not record which release"):
        render.handoff_from_verdict(p, {k: v for k, v in same.items() if k != "scope"})
    # A verdict made without --upstream / --project does not match a render that names them.
    with pytest.raises(render.RenderError, match="verdict is for project '<project>'"):
        render.handoff_from_verdict(p, render.verdict(preflight(), vote_passed=True, target="empty"))
    assert render.handoff_from_verdict(p, same) is False


def test_render_gate_derives_the_handoff_from_the_verdict() -> None:
    p = promote()
    proceed = render.verdict(preflight(), vote_passed=True, target="empty", **AIRFLOW)
    handoff = render.verdict(preflight(rm_is_pmc=False), vote_passed=True, target="empty", **AIRFLOW)
    assert render.handoff_from_verdict(p, proceed) is False
    assert render.handoff_from_verdict(p, handoff) is True
    assert render.handoff_from_verdict(p, handoff, handoff=True) is True
    with pytest.raises(render.RenderError, match="--handoff disagrees"):
        render.handoff_from_verdict(p, proceed, handoff=True)
    with pytest.raises(render.RenderError, match="--handoff disagrees"):
        render.handoff_from_verdict(p, handoff, handoff=False)


def test_apache_name_is_not_doubled() -> None:
    assert render.apache_name("Apache Airflow") == "Apache Airflow"
    assert render.apache_name("Airflow") == "Apache Airflow"


def test_cli_verdict_render_and_refusal(tmp_path, capsys) -> None:
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight()), encoding="utf-8")
    scope = ["--upstream", "apache/airflow", "--project", "airflow"]
    base = ["promote", "verdict", "--preflight", str(pre), *scope]
    assert main([*base, "--vote-passed", "--target", "empty"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == "proceed" and out["scope"]["project"] == "airflow"
    assert main([*base, "--target", "empty"]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "blocked"
    verdict = tmp_path / "verdict.json"
    verdict.write_text(
        json.dumps(render.verdict(preflight(rm_is_pmc=False), vote_passed=True, target="empty", **AIRFLOW)),
        encoding="utf-8",
    )
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    argv = [
        "promote",
        "render",
        "--load",
        str(load),
        "--verdict",
        str(verdict),
        "--upstream",
        "apache/airflow",
        "--project",
        "airflow",
        "--product-name",
        "Apache Airflow",
    ]
    # The hand-off comes from the verdict: omitting --handoff no longer renders rm_is_pmc true.
    assert main([*argv, "--apache-id", "johndoe", "--rm", "johndoe"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["rm_is_pmc"] is False and out["handoff_note"]
    assert main([*argv, "--apache-id", "johndoe", "--handoff", "--rm", "johndoe"]) == 0
    assert json.loads(capsys.readouterr().out)["rm_is_pmc"] is False
    load.write_text(json.dumps(loaded(backend="self-hosted")), encoding="utf-8")
    assert main(argv) == 2
    # The verdict was reached for svnpubsub; a load for another backend is refused before rendering.
    assert "verdict is for dist_backend 'svnpubsub'" in json.loads(capsys.readouterr().out)["refused"]
    # A render for another project than the verdict's is refused.
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    other = [a if a != "airflow" else "otherproj" for a in argv]
    assert main(other) == 2
    assert "verdict is for project 'airflow'" in json.loads(capsys.readouterr().out)["refused"]
    with pytest.raises(SystemExit):
        main(["promote", "verdict", "--preflight", str(pre), "--vote-passed", "--target", "empty"])


def test_cli_render_refuses_without_a_renderable_verdict(tmp_path, capsys) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    verdict = tmp_path / "verdict.json"
    verdict.write_text(
        json.dumps(render.verdict(preflight(), vote_passed=False, target="empty", **AIRFLOW)),
        encoding="utf-8",
    )
    scope = ["--upstream", "apache/airflow", "--project", "airflow"]
    argv = ["promote", "render", "--load", str(load), "--verdict", str(verdict), *scope]
    assert main(argv) == 2
    assert "verdict is 'blocked'" in json.loads(capsys.readouterr().out)["refused"]
    verdict.write_text(
        json.dumps(render.verdict(preflight(), vote_passed=True, target="empty", **AIRFLOW)), encoding="utf-8"
    )
    assert main([*argv, "--handoff"]) == 2
    assert "--handoff disagrees" in json.loads(capsys.readouterr().out)["refused"]
    with pytest.raises(SystemExit):
        main(["promote", "render", "--load", str(load), *scope])  # --verdict is required
    with pytest.raises(SystemExit):
        main(
            ["promote", "render", "--load", str(load), "--verdict", str(verdict)]
        )  # so are --upstream / --project


def test_cli_verdict_requires_the_target_result(tmp_path) -> None:
    pre = tmp_path / "pre.json"
    pre.write_text(json.dumps(preflight()), encoding="utf-8")
    base = [
        "promote",
        "verdict",
        "--preflight",
        str(pre),
        "--upstream",
        "apache/airflow",
        "--project",
        "airflow",
    ]
    with pytest.raises(SystemExit):
        main([*base, "--vote-passed"])
    with pytest.raises(SystemExit):
        main([*base, "--vote-passed", "--target", "skipped"])


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
