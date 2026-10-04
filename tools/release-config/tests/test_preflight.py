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
"""One pass case and one case per blocker for every skill's Step 0 rules."""

from __future__ import annotations

import pytest

from conftest import BUILD_SOURCE_ONLY


def blocked_on(result, fragment):
    assert not result["ok"], result
    assert any(fragment in b for b in result["blockers"]), result["blockers"]


# --------------------------------------------------------------------------- rc-cut


def test_rc_cut_passes(project, preflight):
    result = preflight(project(), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["archive_reviewed"] is True
    assert result["values"]["signing_mode"] == "rm-key"
    assert result["values"]["staging_url"] == "https://dist.apache.org/repos/dist/dev/foo/1.1.0-rc1/"


@pytest.mark.parametrize(
    ("argv", "fragment"),
    [
        (("1", "rc1"), "version '1' does not match a dotted version"),
        (("1.1.0", "r1"), "RC suffix 'r1' does not match rc<N>"),
        (("1.1.0", "rc0"), "RC suffix 'rc0' does not match rc<N> with N >= 1"),
        (("1.1.0", "rc01"), "RC suffix 'rc01'"),
        (("1.1.0.post1", "rc1"), "version '1.1.0.post1' does not match"),
        (("1.1.0",), "RC suffix missing"),
    ],
)
def test_rc_cut_bad_arguments(project, preflight, argv, fragment):
    blocked_on(preflight(project(), "rc-cut", *argv), fragment)


@pytest.mark.parametrize("version", ["1.1", "1.1.0", "2.11.0.1"])
def test_rc_cut_dotted_versions_accepted(project, preflight, version):
    assert preflight(project(), "rc-cut", version, "rc12")["ok"]


# The same source version / RC rule in every skill that takes an RC identifier.
RC_ID_SKILLS = ("vote-draft", "vote-tally", "promote", "verify-rc")


@pytest.mark.parametrize("skill", RC_ID_SKILLS)
@pytest.mark.parametrize("rc_id", ["1.1.0-rc0", "1.1.0.post1-rc1", "1-rc1", "1.1.0rc1", "1.1.0-rc"])
def test_source_rc_id_rejected_everywhere(project, preflight, skill, rc_id):
    blocked_on(preflight(project(), skill, rc_id, "--force-close", "x", "--rm", "johndoe"), f"RC identifier {rc_id!r} does not match")


@pytest.mark.parametrize("skill", RC_ID_SKILLS)
def test_source_rc_id_two_part_version_accepted(project, preflight, skill):
    result = preflight(project(), skill, "1.1-rc3", "--force-close", "x", "--rm", "johndoe")
    assert not any("RC identifier" in b for b in result["blockers"]), result["blockers"]


@pytest.mark.parametrize(("skill", "argv"), [("announce-draft", ()), ("audit-report", ()), ("prepare", ("prep",))])
def test_source_version_rejects_post_everywhere(project, preflight, skill, argv):
    blocked_on(preflight(project(), skill, *argv, "1.1.0.post1"), "version '1.1.0.post1' does not match")


def test_rc_cut_build_file_missing(project, preflight):
    blocked_on(preflight(project(build=None), "rc-cut", "1.1.0", "rc1"), "release-build.md not found")


def test_rc_cut_required_keys(project, preflight):
    result = preflight(project(drop=("release_dist_backend", "release_dist_url_template")), "rc-cut", "1.1.0", "rc1")
    blocked_on(result, "`release_dist_backend`")
    blocked_on(result, "`release_dist_url_template`")


def test_rc_cut_build_sections_todo(project, preflight):
    build = BUILD_SOURCE_ONLY.replace(
        "- `apache-foo-<version>-source.tar.gz`, canonical source artefact (required, signed, checksummed).", "TODO: list the artefacts."
    )
    build = build.replace("- `sha512`, required.", "TODO: list which digests. ASF baseline is `sha512`; `md5` is no longer accepted.")
    build = build.replace("## Build invocation\n", "## Build stuff\n")
    result = preflight(project(build=build), "rc-cut", "1.1.0", "rc1")
    blocked_on(result, "no build_command")
    blocked_on(result, "no expected_artefacts")
    blocked_on(result, "no digest_set")


@pytest.mark.parametrize(
    ("digests", "fragment"),
    [
        ("- `sha256`, published.", "does not contain sha512"),
        ("- `sha512`, required.\n- `md5`, legacy.", "contains md5"),
        ("- `sha512`, required.\n- `sha1`, legacy.", "contains sha1"),
    ],
)
def test_rc_cut_digest_set(project, preflight, digests, fragment):
    build = BUILD_SOURCE_ONLY.replace("- `sha512`, required.", digests)
    blocked_on(preflight(project(build=build), "rc-cut", "1.1.0", "rc1"), fragment)


def test_rc_cut_digest_set_ignores_template_guidance(project, preflight):
    build = BUILD_SOURCE_ONLY.replace(
        "- `sha512`, required.", "`sha512` only.\n\nTemplate guidance: ASF baseline is `sha512`; `md5` is no longer accepted.\n\n> - `sha256`, published."
    )
    assert preflight(project(build=build), "rc-cut", "1.1.0", "rc1")["ok"]


def test_rc_cut_archive_unreviewed_blocks(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("| `export_ignore_reviewed` | `1.0.0` |", "| `export_ignore_reviewed` | *(unset)* |")
    result = preflight(project(build=build), "rc-cut", "1.0.0", "rc1")
    blocked_on(result, "export_ignore_reviewed is unset")
    assert "release-prepare prep 1.0.0" in result["blockers"][0]
    assert result["values"]["archive_reviewed"] is False


def test_rc_cut_archive_unreviewed_override(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("| `export_ignore_reviewed` | `1.0.0` |", "| `export_ignore_reviewed` | *(unset)* |")
    result = preflight(project(build=build), "rc-cut", "1.0.0", "rc1", "--allow-unreviewed-archive")
    assert result["ok"], result
    assert result["values"]["archive_reviewed"] is False
    assert any("Step 4" in w for w in result["warnings"])


def test_rc_cut_custom_archive_skips_review(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("`git-archive` | default", "`custom` | default").replace(
        "| `export_ignore_reviewed` | `1.0.0` |", "| `export_ignore_reviewed` | *(unset)* |"
    )
    result = preflight(project(build=build), "rc-cut", "1.0.0", "rc1")
    assert result["ok"], result
    assert result["values"]["archive_reviewed"] is True


CONVENIENCE = """## Convenience artefacts

```yaml
convenience_artefacts:
  - name: apache-foo-<version>-bin.tar.gz     # filename as staged
    kind: binary-tarball
    build_command: |
      mvn -DskipTests clean package
    staging: dist-dev
    reproducibility: {mode}
    known_divergences: []
    vote_included: false
    publish_channel: {channel}
    publish_command: {command}
```
"""


def test_rc_cut_automated_signing_consistent(project, preflight):
    build = BUILD_SOURCE_ONLY.replace(
        "## Convenience artefacts\n\nNone — a source-only project.\n", CONVENIENCE.format(mode="byte-identical", channel="dist-release", command="null")
    )
    result = preflight(project({"automated_release_signing": "enabled"}, build=build), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["signing_mode"] == "ci-automated"


def test_rc_cut_automated_signing_needs_byte_identical(project, preflight):
    build = BUILD_SOURCE_ONLY.replace(
        "## Convenience artefacts\n\nNone — a source-only project.\n", CONVENIENCE.format(mode="documented-divergence", channel="dist-release", command="null")
    )
    blocked_on(preflight(project({"automated_release_signing": "enabled"}, build=build), "rc-cut", "1.1.0", "rc1"), "must be `byte-identical`")


def test_rc_cut_automated_signing_needs_reproducibility_source(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("| `reproducibility_source` | `on` |", "| `reproducibility_source` | `off` |")
    blocked_on(preflight(project({"automated_release_signing": "enabled"}, build=build), "rc-cut", "1.1.0", "rc1"), "reproducibility_source")


def test_rc_cut_automated_signing_ignored_where_not_offered(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("| `reproducibility_source` | `on` |", "| `reproducibility_source` | `off` |")
    result = preflight(project({"automated_release_signing": "enabled"}, build=build, org="independent"), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["signing_mode"] == "rm-key"
    assert not any("automated" in w for w in result["warnings"])


def _with_convenience(scheme_line):
    block = CONVENIENCE.format(mode="byte-identical", channel="dist-release", command="null")
    if scheme_line:
        block = block.replace("    kind: binary-tarball\n", f"    kind: binary-tarball\n    {scheme_line}\n")
    return BUILD_SOURCE_ONLY.replace("## Convenience artefacts\n\nNone — a source-only project.\n", block)


def test_convenience_python_scheme_validated(project, preflight):
    result = preflight(project(build=_with_convenience("version_scheme: python")), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["convenience_versions"] == [
        {"name": "apache-foo-<version>-bin.tar.gz", "version": "1.1.0", "version_scheme": "python", "status": "valid"}
    ]
    assert not result["warnings"]


def test_convenience_unknown_scheme_reported_unvalidated(project, preflight):
    result = preflight(project(build=_with_convenience("version_scheme: maven")), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["convenience_versions"][0]["status"] == "unvalidated"
    assert result["values"]["convenience_versions"][0]["version_scheme"] == "maven"
    assert any("'maven', which the tool does not validate" in w for w in result["warnings"])


def test_convenience_no_scheme_warns(project, preflight):
    result = preflight(project(build=_with_convenience(None)), "rc-cut", "1.1.0", "rc1")
    assert result["ok"], result
    assert result["values"]["convenience_versions"][0] == {
        "name": "apache-foo-<version>-bin.tar.gz",
        "version": "1.1.0",
        "version_scheme": None,
        "status": "unvalidated",
    }
    assert any("declares no version_scheme" in w and "python" in w for w in result["warnings"])


@pytest.mark.parametrize("own", ["2.10.5.post1", "<version>.post1"])
def test_convenience_own_post_version_passes_against_plain_source(project, preflight, own):
    """A wheel re-released as 2.10.5.post1 against source release 2.10.5."""
    root = project(build=_with_convenience(f"version_scheme: python\n    version: {own}"))
    for skill, argv in (("rc-cut", ("2.10.5", "rc1")), ("verify-rc", ("2.10.5-rc1",)), ("promote", ("2.10.5-rc1", "--rm", "johndoe"))):
        result = preflight(root, skill, *argv)
        assert result["ok"], (skill, result)
        assert result["values"]["convenience_versions"][0]["version"] == "2.10.5.post1"
        assert result["values"]["convenience_versions"][0]["status"] == "valid"


def test_source_post_version_still_blocks_with_python_artefact(project, preflight):
    root = project(build=_with_convenience("version_scheme: python\n    version: 2.10.5.post1"))
    blocked_on(preflight(root, "rc-cut", "2.10.5.post1", "rc1"), "version '2.10.5.post1' does not match")


@pytest.mark.parametrize("own", ["2.10.5-beta", "2.10.5.post"])
def test_convenience_invalid_python_version_blocks(project, preflight, own):
    root = project(build=_with_convenience(f"version_scheme: python\n    version: {own}"))
    result = preflight(root, "rc-cut", "2.10.5", "rc1")
    blocked_on(result, f"version {own!r} is not a dotted version with an optional `.postN`")
    assert result["values"]["convenience_versions"][0]["status"] == "invalid"


def test_convenience_own_version_unknown_scheme_unvalidated(project, preflight):
    root = project(build=_with_convenience("version_scheme: maven\n    version: 2.10.5-1"))
    result = preflight(root, "rc-cut", "2.10.5", "rc1")
    assert result["ok"], result
    assert result["values"]["convenience_versions"][0] == {
        "name": "apache-foo-<version>-bin.tar.gz",
        "version": "2.10.5-1",
        "version_scheme": "maven",
        "status": "unvalidated",
    }
    assert any("confirms its version '2.10.5-1'" in w for w in result["warnings"])


def test_convenience_versions_also_in_verify_rc_and_promote(project, preflight):
    root = project(build=_with_convenience("version_scheme: python"))
    assert preflight(root, "verify-rc", "1.1.0-rc1")["values"]["convenience_versions"][0]["status"] == "valid"
    assert preflight(root, "promote", "1.1.0-rc1", "--rm", "johndoe")["values"]["convenience_versions"][0]["status"] == "valid"


def test_source_only_reports_no_convenience_versions(project, preflight):
    assert "convenience_versions" not in preflight(project(), "rc-cut", "1.1.0", "rc1")["values"]


# --------------------------------------------------------------------------- vote-draft


def test_vote_draft_passes(project, preflight):
    result = preflight(project(), "vote-draft", "1.1.0-rc1")
    assert result["ok"], result
    assert result["values"]["skip_verify_override"] is False
    assert result["values"]["expedited"] is False


def test_vote_draft_bad_rc(project, preflight):
    blocked_on(preflight(project(), "vote-draft", "1.1.0rc1"), "does not match")


def test_vote_draft_required_keys(project, preflight):
    result = preflight(project(drop=("vote_window_hours", "vote_dev_list")), "vote-draft", "1.1.0-rc1")
    blocked_on(result, "`vote_window_hours`")
    blocked_on(result, "`vote_dev_list`")


def test_vote_draft_short_window_blocks(project, preflight):
    blocked_on(preflight(project({"vote_window_hours": "48"}), "vote-draft", "1.1.0-rc1"), "below the ASF 72-hour floor")


def test_vote_draft_short_window_expedited(project, preflight):
    result = preflight(project({"vote_window_hours": "48"}), "vote-draft", "1.1.0-rc1", "--expedited", "security fix")
    assert result["ok"], result
    assert result["values"]["expedited"] is True


def test_vote_draft_skip_verify_flag_reported(project, preflight):
    assert preflight(project(), "vote-draft", "1.1.0-rc1", "--skip-verify-check", "re-spin")["values"]["skip_verify_override"] is True


# --------------------------------------------------------------------------- vote-tally


def test_vote_tally_passes(project, preflight):
    result = preflight(project(), "vote-tally", "1.1.0-rc1", "--vote-opened", "2026-06-10 10:00 UTC", "--now", "2026-06-14T12:00:00Z")
    assert result["ok"], result
    assert result["values"]["mechanism"] == "dev-list-vote"
    assert result["values"]["roster_path"] == ".apache-magpie-overrides/pmc-roster.md"


def test_vote_tally_window_not_elapsed(project, preflight):
    result = preflight(project(), "vote-tally", "1.1.0-rc1", "--vote-opened", "2026-06-14 08:00 UTC", "--now", "2026-06-14T12:00:00Z")
    blocked_on(result, "4 hours elapsed of 72-hour window")


def test_vote_tally_force_close(project, preflight):
    result = preflight(
        project(), "vote-tally", "1.1.0-rc1", "--vote-opened", "2026-06-14 08:00 UTC", "--now", "2026-06-14T12:00:00Z", "--force-close", "re-vote"
    )
    assert result["ok"], result
    assert result["values"]["force_close"] is True


def test_vote_tally_open_time_needed(project, preflight):
    blocked_on(preflight(project(), "vote-tally", "1.1.0-rc1"), "--vote-opened")


def test_vote_tally_asf_mechanism(project, preflight):
    result = preflight(
        project({"release_approval_mechanism": "github-discussion", "approval_window_hours": "72"}),
        "vote-tally",
        "1.1.0-rc1",
        "--vote-opened",
        "2026-06-10T10:00:00Z",
        "--now",
        "2026-06-14T12:00:00Z",
    )
    blocked_on(result, "an ASF project (project.md → organization: ASF) requires release_approval_mechanism=dev-list-vote; config has github-discussion")
    assert result["values"]["is_asf"] is True


def test_vote_tally_ignores_is_asf_tlp_key(project, preflight):
    """`is_asf_tlp` is gone: `organization: ASF` alone pins the mechanism."""
    root = project({"release_approval_mechanism": "github-discussion", "approval_window_hours": "72", "is_asf_tlp": "false"})
    blocked_on(preflight(root, "vote-tally", "1.1.0-rc1", "--force-close", "x"), "requires release_approval_mechanism=dev-list-vote")


def test_vote_tally_non_asf_other_mechanism(project, preflight):
    root = project({"release_approval_mechanism": "pr-approval", "approval_window_hours": "24"}, org="independent")
    assert preflight(root, "vote-tally", "1.1.0-rc1", "--vote-opened", "2026-06-10T10:00:00Z", "--now", "2026-06-14T12:00:00Z")["ok"]


def test_vote_tally_required_keys(project, preflight):
    result = preflight(
        project(drop=("release_approval_mechanism", "release_approver_roster_path", "result_subject_template")), "vote-tally", "1.1.0-rc1", "--force-close", "x"
    )
    for key in ("release_approval_mechanism", "result_subject_template"):
        blocked_on(result, f"`{key}`")
    assert not any("release_approver_roster_path`" in b for b in result["blockers"])


def test_vote_tally_default_roster_path(project, preflight):
    result = preflight(project(drop=("release_approver_roster_path",)), "vote-tally", "1.1.0-rc1", "--force-close", "x")
    assert result["ok"], result
    assert result["values"]["roster_path"] == ".apache-magpie-overrides/pmc-roster.md"


def test_vote_tally_custom_roster_path(project, preflight, tmp_path):
    (tmp_path / "people").mkdir()
    (tmp_path / "people" / "approvers.md").write_text("| Apache ID |\n|---|\n| `zed` |\n", encoding="utf-8")
    result = preflight(project({"release_approver_roster_path": "people/approvers.md"}, roster=None), "vote-tally", "1.1.0-rc1", "--force-close", "x")
    assert result["ok"], result
    assert result["values"]["roster_path"] == "people/approvers.md"


def test_vote_tally_roster_unreadable(project, preflight):
    blocked_on(preflight(project(roster=None), "vote-tally", "1.1.0-rc1", "--force-close", "x"), "is not readable")


def test_vote_tally_roster_only_placeholders(project, preflight):
    roster = "| Apache ID | Name | Primary email |\n|---|---|---|\n| `<TODO>` | `<TODO Member Name>` | `<TODO>@apache.org` |\n"
    blocked_on(preflight(project(roster=roster), "vote-tally", "1.1.0-rc1", "--force-close", "x"), "has no roster rows")


# --------------------------------------------------------------------------- announce-draft


def test_announce_passes(project, preflight):
    result = preflight(
        project(),
        "announce-draft",
        "1.1.0",
        "--promote-timestamp",
        "2026-06-10 08:00 UTC",
        "--now",
        "2026-06-11T10:00:00Z",
        "--download-page",
        "https://foo/dl",
    )
    assert result["ok"], result
    assert result["values"]["promote_clear_after_utc"] is None


def test_announce_promote_wait_blocks(project, preflight):
    result = preflight(
        project(),
        "announce-draft",
        "1.1.0",
        "--promote-timestamp",
        "2026-06-11 09:45 UTC",
        "--now",
        "2026-06-11T10:15:00Z",
        "--download-page",
        "https://foo/dl",
    )
    blocked_on(result, "clears at 2026-06-11T10:45:00Z (in ~30 minutes)")
    assert result["values"]["promote_clear_after_utc"] == "2026-06-11T10:45:00Z"


def test_announce_promote_wait_override(project, preflight):
    result = preflight(
        project(),
        "announce-draft",
        "1.1.0",
        "--promote-timestamp",
        "2026-06-11T09:45:00Z",
        "--now",
        "2026-06-11T10:15:00Z",
        "--download-page",
        "https://foo/dl",
        "--skip-promote-wait",
        "mirrors synced",
    )
    assert result["ok"], result
    assert result["values"]["skip_promote_wait_override"] is True


def test_announce_clear_after_null_when_other_blockers(project, preflight):
    result = preflight(project(), "announce-draft", "1.1.0", "--promote-timestamp", "2026-06-11 09:45 UTC", "--now", "2026-06-11T10:15:00Z")
    assert len(result["blockers"]) == 2
    assert result["values"]["promote_clear_after_utc"] is None


def test_announce_missing_inputs(project, preflight):
    result = preflight(project(drop=("announce_list", "announce_subject_template")), "announce-draft", "1")
    blocked_on(result, "does not match")
    blocked_on(result, "`announce_list`")
    blocked_on(result, "`announce_subject_template`")
    blocked_on(result, "promote timestamp unavailable")
    blocked_on(result, "Download Page URL unavailable")


def test_announce_download_page_from_config(project, preflight):
    root = project({"download_page_url": "https://foo.apache.org/download"})
    assert preflight(root, "announce-draft", "1.1.0", "--promote-timestamp", "2026-06-10T08:00:00Z", "--now", "2026-06-11T10:00:00Z")["ok"]


ANNOUNCE_OK = ("--promote-timestamp", "2026-06-10T08:00:00Z", "--now", "2026-06-11T10:00:00Z", "--download-page", "u")


def test_announce_non_asf_with_announce_list_blocks(project, preflight):
    result = preflight(project(org="independent"), "announce-draft", "1.1.0", *ANNOUNCE_OK)
    blocked_on(result, "announce-list, which only an ASF project uses; project.md declares organization: independent")
    assert result["values"]["non_asf"] is True


def test_announce_asf_other_backend_blocks(project, preflight):
    result = preflight(project({"release_announce_backend": "site-post"}), "announce-draft", "1.1.0", *ANNOUNCE_OK)
    blocked_on(result, "an ASF project (project.md → organization: ASF) announces on announce-list")
    assert result["values"]["non_asf"] is False


def test_announce_non_asf_other_backend_passes(project, preflight):
    result = preflight(project({"release_announce_backend": "github-release-notes"}, org="independent"), "announce-draft", "1.1.0", *ANNOUNCE_OK)
    assert result["ok"], result


def test_non_asf_flag_removed(project):
    from release_config.cli import run

    with pytest.raises(SystemExit):
        run(["preflight", "--project-root", str(project()), "--skill", "promote", "1.1.0-rc1", "--non-asf"])


# --------------------------------------------------------------------------- promote


def test_promote_passes(project, preflight):
    result = preflight(project(), "promote", "1.1.0-rc1", "--rm", "johndoe")
    assert result["ok"], result
    values = result["values"]
    assert values["rm_is_pmc"] is True
    assert values["target_url"] == "https://dist.apache.org/repos/dist/release/foo/1.1.0/"
    assert values["staging_url"] == "https://dist.apache.org/repos/dist/dev/foo/1.1.0-rc1/"
    assert values["version"] == "1.1.0" and values["rc"] == "rc1"


@pytest.mark.parametrize("identity", ["JohnDoe", "john@example.com", "alice@apache.org", "alice"])
def test_promote_roster_matching(project, preflight, identity):
    assert preflight(project(), "promote", "1.1.0-rc1", "--rm", identity)["values"]["rm_is_pmc"] is True


def test_promote_non_pmc_is_handoff_not_blocker(project, preflight):
    result = preflight(project(), "promote", "1.1.0-rc1", "--rm", "carol")
    assert result["ok"], result
    assert result["values"]["rm_is_pmc"] is False
    assert result["values"]["handoff_non_pmc"] is True


def test_promote_rm_from_user_md(project, preflight):
    root = project(user="# me\n\napache_id: johndoe\n")
    assert preflight(root, "promote", "1.1.0-rc1")["values"]["rm_is_pmc"] is True


def test_promote_rm_unknown(project, preflight):
    blocked_on(preflight(project(), "promote", "1.1.0-rc1"), "RM identity unknown")


def test_promote_non_asf_skips_gate(project, preflight):
    result = preflight(project(org="independent", roster=None), "promote", "1.1.0-rc1")
    assert result["ok"], result
    assert result["values"]["non_asf"] is True
    assert result["values"]["rm_is_pmc"] is True
    assert result["values"]["handoff_non_pmc"] is False


def test_promote_roster_from_roster_path_key(project, preflight, tmp_path):
    (tmp_path / "people").mkdir()
    (tmp_path / "people" / "approvers.md").write_text("| Apache ID |\n|---|\n| `zed` |\n", encoding="utf-8")
    root = project({"release_approver_roster_path": "people/approvers.md"})
    assert preflight(root, "promote", "1.1.0-rc1", "--rm", "zed")["values"]["rm_is_pmc"] is True
    assert preflight(root, "promote", "1.1.0-rc1", "--rm", "johndoe")["values"]["rm_is_pmc"] is False


def test_promote_missing_roster_is_handoff(project, preflight):
    result = preflight(project(roster=None), "promote", "1.1.0-rc1", "--rm", "johndoe")
    assert result["ok"], result
    assert result["values"]["handoff_non_pmc"] is True
    assert any("release_approver_roster_path" in w for w in result["warnings"])


def test_promote_bad_argument_and_keys(project, preflight):
    result = preflight(project(drop=("release_dist_backend", "release_dist_url_template")), "promote", "1.1.0", "--rm", "johndoe")
    blocked_on(result, "does not match")
    blocked_on(result, "`release_dist_backend`")


def test_promote_trusted_hardware_flag(project, preflight):
    assert preflight(project({"automated_release_signing": "enabled"}), "promote", "1.1.0-rc1", "--rm", "johndoe")["values"][
        "trusted_hardware_attestation_required"
    ]
    assert not preflight(project({"automated_release_signing": "requested"}), "promote", "1.1.0-rc1", "--rm", "johndoe")["values"][
        "trusted_hardware_attestation_required"
    ]


# --------------------------------------------------------------------------- verify-rc


def test_verify_rc_passes(project, preflight):
    result = preflight(project(), "verify-rc", "1.1.0-rc1", "--post-to", "https://github.com/apache/foo/issues/1")
    assert result["ok"], result
    assert result["values"] == {
        "rc_tag": "1.1.0-rc1",
        "staging_url": "https://dist.apache.org/repos/dist/dev/foo/1.1.0-rc1/",
        "keyserver": "keys.openpgp.org",
        "post_to": "https://github.com/apache/foo/issues/1",
    }


def test_verify_rc_rc0_rejected(project, preflight):
    blocked_on(preflight(project(), "verify-rc", "1.1.0-rc0"), "does not match")


def test_verify_rc_keyserver_defaults(project, preflight):
    result = preflight(project(drop=("keyserver",)), "verify-rc", "1.1.0-rc1")
    assert result["ok"], result
    assert result["values"]["keyserver"] == "keys.openpgp.org"


def test_verify_rc_missing_template(project, preflight):
    result = preflight(project(drop=("release_dist_url_template",)), "verify-rc", "1.1.0-rc1")
    blocked_on(result, "`release_dist_url_template`")
    assert result["values"]["staging_url"] is None


def test_verify_rc_missing_keys_and_sections(project, preflight):
    build = BUILD_SOURCE_ONLY.replace("## Binary-exclude list", "## Something else").replace("## Apache RAT configuration", "## Licensing")
    result = preflight(project(drop=("keys_file_url", "keyserver", "version_manifest_files"), build=build), "verify-rc", "1.1.0-rc1")
    for fragment in ("`keys_file_url`", "`version_manifest_files`", "§ Binary-exclude list", "§ Apache RAT configuration"):
        blocked_on(result, fragment)
    assert not any("`keyserver`" in b for b in result["blockers"])


def test_verify_rc_malformed_url(project, preflight):
    blocked_on(preflight(project({"release_dist_url_template": "dist/<project>/<version>/"}), "verify-rc", "1.1.0-rc1"), "not well-formed")


# --------------------------------------------------------------------------- archive-sweep


def test_archive_sweep_passes(project, preflight):
    result = preflight(project(), "archive-sweep")
    assert result["ok"], result
    assert result["values"]["non_asf"] is False
    assert len(result["values"]["release_lines"]) == 2


def test_archive_sweep_atr_is_asf(project, preflight):
    result = preflight(project({"release_dist_backend": "atr"}), "archive-sweep")
    assert result["ok"], result
    assert result["values"]["non_asf"] is False


@pytest.mark.parametrize("backend", ["svnpubsub", "atr"])
def test_archive_sweep_asf_backends_default_archive(project, preflight, backend):
    result = preflight(project({"release_dist_backend": backend}, drop=("archive_url_template",)), "archive-sweep")
    assert result["ok"], result
    assert result["values"]["archive_url"] == "https://archive.apache.org/dist/foo/"


def test_archive_sweep_atr_without_project_name_blocks(project, preflight):
    result = preflight(project({"release_dist_backend": "atr"}, drop=("archive_url_template", "project_dist_name")), "archive-sweep")
    blocked_on(result, "archive destination for atr cannot be derived")


def test_archive_sweep_non_asf_from_organization(project, preflight):
    """`non_asf` follows project.md's organization, not the backend."""
    assert preflight(project(org="independent"), "archive-sweep")["values"]["non_asf"] is True
    assert preflight(project({"release_dist_backend": "s3"}), "archive-sweep")["values"]["non_asf"] is False


def test_archive_sweep_blockers(project, preflight):
    result = preflight(
        project({"release_dist_backend": "github-releases"}, drop=("archive_retention_rule", "archive_url_template"), trains=None, org="independent"),
        "archive-sweep",
    )
    blocked_on(result, "`archive_retention_rule`")
    blocked_on(result, "release-trains.md not found")
    blocked_on(result, "github-releases backend is not configured")
    assert result["values"]["non_asf"] is True


def test_archive_sweep_unknown_backend_and_empty_trains(project, preflight):
    result = preflight(project({"release_dist_backend": "ftp"}, trains="# T\n\n## Release branches currently in flight\n\nTODO: list them.\n"), "archive-sweep")
    blocked_on(result, "is not one of")
    blocked_on(result, "lists no release line")


# --------------------------------------------------------------------------- audit-report


def test_audit_report_passes(project, preflight):
    result = preflight(project(), "audit-report", "1.1.0")
    assert result["ok"], result
    assert result["values"]["audit_log_path"] == "audit/releases/"


def test_audit_report_default_roster_path(project, preflight):
    assert preflight(project(drop=("release_approver_roster_path",)), "audit-report", "1.1.0")["ok"]


def test_audit_report_blockers(project, preflight):
    result = preflight(project(drop=("audit_log_path",), roster=None), "audit-report", "v1")
    blocked_on(result, "does not match")
    blocked_on(result, "`audit_log_path`")
    blocked_on(result, "is not readable")
    assert result["values"]["audit_log_path"] is None


# --------------------------------------------------------------------------- keys-sync


def test_keys_sync_from_user_md(project, preflight):
    root = project(user="release_manager:\n  gpg_fingerprint: abcd 1234 abcd 1234 abcd 1234 abcd 1234 abcd 1234\n")
    result = preflight(root, "keys-sync")
    assert result["ok"], result
    assert result["values"]["fingerprint"] == "ABCD1234ABCD1234ABCD1234ABCD1234ABCD1234"
    assert result["values"]["keyserver"] == "keys.openpgp.org"


def test_keys_sync_flags_win(project, preflight):
    result = preflight(project(), "keys-sync", "--fingerprint", "A" * 40, "--keys-url", "https://k", "--keyserver", "hkps://other")
    assert result["values"] == {"fingerprint": "A" * 40, "fingerprint_source": "--fingerprint", "keys_file_url": "https://k", "keyserver": "hkps://other"}


def test_keys_sync_config_fingerprint(project, preflight):
    result = preflight(project({"rm_key_fingerprint": "B" * 40}), "keys-sync")
    assert result["values"]["fingerprint_source"].startswith("release-management-config.md")


def test_keys_sync_blockers(project, preflight):
    result = preflight(project(drop=("keys_file_url", "keyserver")), "keys-sync")
    blocked_on(result, "no RM key fingerprint")
    blocked_on(result, "keys_file_url not resolvable")
    assert result["values"]["keyserver"] == "keys.openpgp.org"


# --------------------------------------------------------------------------- prepare


def test_prepare_plan_passes(project, preflight):
    result = preflight(project(), "prepare", "1.2.0", "--previous-tag", "1.1.0")
    assert result["ok"], result
    assert result["values"]["sub_command"] == "plan"
    assert result["values"]["previous_tag"] == "1.1.0"
    assert result["values"]["release_branch_base"] == "main"


@pytest.mark.parametrize("sub", ["prep", "post"])
def test_prepare_sub_commands(project, preflight, sub):
    result = preflight(project(), "prepare", sub, "1.2.0")
    assert result["ok"], result
    assert result["values"]["sub_command"] == sub
    assert result["values"]["version"] == "1.2.0"


def test_prepare_automated_signing_asf(project, preflight):
    result = preflight(project(), "prepare", "automated-signing")
    assert result["ok"], result
    assert result["values"]["version"] is None


def test_prepare_automated_signing_non_asf(project, preflight):
    result = preflight(project(org="independent"), "prepare", "automated-signing")
    blocked_on(result, "not offered by this project's organization (independent)")
    assert result["values"]["automated_signing_offered"] is False


ORG_OFFERS = "# Acme\n\n```yaml\nrelease_process:\n  release_dist: null\n  automated_signing:\n    policy_url: https://acme.example/signing\n```\n"


def test_prepare_automated_signing_from_adopter_org_manifest(project, preflight):
    """An organization Magpie does not ship offers it through its adopter-local manifest."""
    root = project(org="Acme")
    manifest = root / ".apache-magpie-overrides" / "organizations" / "Acme" / "organization.md"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(ORG_OFFERS, encoding="utf-8")
    result = preflight(root, "prepare", "automated-signing")
    assert result["ok"], result
    assert result["values"]["automated_signing_offered"] is True


def test_project_md_overrides_org_automated_signing(project, preflight):
    """project.md is first in the resolution chain: `automated_signing: null` there withdraws the ASF offer."""
    root = project()
    path = root / ".apache-magpie-overrides" / "project.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n```yaml\nrelease_process:\n  automated_signing: null\n```\n", encoding="utf-8")
    blocked_on(preflight(root, "prepare", "automated-signing"), "release_process.automated_signing is unset or null (project.md)")
    assert preflight(root, "rc-cut", "1.1.0", "rc1", "--allow-unreviewed-archive")["values"]["signing_mode"] == "rm-key"


def test_prepare_blockers(project, preflight):
    result = preflight(project(drop=("release_branch_base", "version_manifest_files"), trains=None), "prepare", "prep", "one")
    blocked_on(result, "does not match")
    blocked_on(result, "`release_branch_base`")
    blocked_on(result, "`version_manifest_files`")
    blocked_on(result, "release-trains.md not found")


def test_prepare_no_arguments(project, preflight):
    blocked_on(preflight(project(), "prepare"), "no sub-command or version")
