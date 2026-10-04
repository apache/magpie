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
"""`load`: file resolution, markdown parsing, defaults and derived values."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import BUILD_SOURCE_ONLY
from release_config import cli, versions
from release_config import mdconfig as md
from release_config.config import load_build, plus_one_hour, render_dist_url

FRAMEWORK = Path(__file__).resolve().parents[3]
TEMPLATES = FRAMEWORK / "plugins" / "magpie-setup" / "templates"


def test_local_layer_wins_whole_file(project, load):
    root = project()
    local = root / ".apache-magpie-local"
    local.mkdir()
    (local / "release-management-config.md").write_text("| Key | Value |\n|---|---|\n| `release_dist_backend` | `atr` |\n", encoding="utf-8")
    loaded = load(root, None)
    assert loaded["sources"]["release-management-config.md"] == ".apache-magpie-local/release-management-config.md"
    assert loaded["config"]["release_dist_backend"] == "atr"
    # per file, not per key: nothing from the overrides copy leaks in
    assert "release_dist_url_template" not in loaded["config"]
    assert loaded["sources"]["release-build.md"] == ".apache-magpie-overrides/release-build.md"


def test_config_dir_reads_one_directory(project, tmp_path):
    root = project()
    out = cli.run(["load", "--project-root", str(tmp_path / "elsewhere"), "--config-dir", str(root / ".apache-magpie-overrides")])
    assert out["config"]["project_dist_name"] == "foo"


def test_defaults_and_derived(project, load):
    loaded = load(project(drop=("release_vote_backend", "keyserver")), None)
    assert loaded["config"]["release_vote_backend"] == "manual"
    assert loaded["config"]["git_upstream_remote"] == "origin"
    assert loaded["config"]["keyserver"] == "keys.openpgp.org"
    derived = loaded["derived"]
    assert derived["signing_mode"] == "rm-key"
    assert derived["is_asf"] is True and derived["non_asf"] is False
    assert "is_asf_tlp" not in derived
    assert derived["automated_signing_offered"] is True
    assert derived["automated_signing_source"].endswith("organizations/ASF/organization.md")
    assert derived["approver_roster_path"] == "<project-config>/pmc-roster.md"
    assert loaded["build"]["reproducibility_binaries"] == "off"


def test_non_asf_derived_from_organization(project, load):
    derived = load(project({"is_asf_tlp": "true"}, org="independent"), None)["derived"]
    assert derived["non_asf"] is True
    assert derived["automated_signing_offered"] is False
    assert derived["automated_signing_source"].endswith("organizations/independent/organization.md")


def test_unknown_org_without_manifest_uses_framework_default(project, load):
    derived = load(project(org="Nobody"), None)["derived"]
    assert derived["automated_signing_offered"] is False
    assert derived["automated_signing_source"] == "framework default"


def test_shipped_org_manifests_automated_signing():
    asf = (FRAMEWORK / "organizations" / "ASF" / "organization.md").read_text(encoding="utf-8")
    independent = (FRAMEWORK / "organizations" / "independent" / "organization.md").read_text(encoding="utf-8")
    assert md.nested_key_declared(asf, "release_process", "automated_signing") is True
    assert md.nested_key_declared(independent, "release_process", "automated_signing") is False
    assert md.nested_key_declared("project_metadata:\n  kind: none\n", "release_process", "automated_signing") is None


@pytest.mark.parametrize(
    ("version", "rc", "ok"),
    [
        ("2.11.0", "rc1", True),
        ("2.11", "rc10", True),
        ("2.11.0.post1", "rc1", False),
        ("2", "rc1", False),
        ("2.11.0", "rc0", False),
    ],
)
def test_source_version_rule(version, rc, ok):
    assert bool(versions.SOURCE_VERSION.match(version) and versions.RC.match(rc)) is ok
    assert bool(versions.SOURCE_RC_ID.match(f"{version}-{rc}")) is ok


@pytest.mark.parametrize(
    ("version", "rc", "status"),
    [
        ("2.11.0", "rc1", "valid"),
        ("2.11.0.post1", "rc1", "valid"),  # rejected for the source version, accepted for a python artefact
        ("2.11.0.post1", "rc0", "invalid"),
        ("2.11.0-beta", "rc1", "invalid"),
    ],
)
def test_python_scheme(version, rc, status):
    assert versions.check_convenience({"name": "w.whl", "version_scheme": "python"}, version, rc)["status"] == status
    assert not versions.SOURCE_VERSION.match("2.11.0.post1")


def test_artefact_version_default_and_render():
    assert versions.artefact_version({}, "2.10.5") == "2.10.5"
    assert versions.artefact_version({"version": "<version>.post1"}, "2.10.5") == "2.10.5.post1"
    assert versions.artefact_version({"version": "2.10.5.post2"}, "2.10.5") == "2.10.5.post2"
    check = versions.check_convenience({"name": "w", "version_scheme": "python", "version": "<version>.post1"}, "2.10.5", "rc1")
    assert check["version"] == "2.10.5.post1" and check["status"] == "valid"


def test_promote_split_uses_artefact_version(project, load):
    build = CONVENIENCE.replace("    kind: wheel\n", "    kind: wheel\n    version: <version>.post1\n")
    meta = load(project(build=build), "promote", "1.1.0-rc1", "--verify-binary", "apache_foo-1.1.0.post1-py3-none-any.whl=identical")["metadata"]
    assert {
        "name": "apache_foo-1.1.0.post1-py3-none-any.whl",
        "publish_channel": "pypi",
        "publish_command": "twine upload dist/apache_foo-1.1.0.post1*",
    } in meta["convenience"]["publish"]


@pytest.mark.parametrize("scheme", [None, "", "maven", "npm"])
def test_other_schemes_unvalidated(scheme):
    check = versions.check_convenience({"name": "x", "version_scheme": scheme}, "anything-goes", "rc0")
    assert check["status"] == "unvalidated" and check["problems"] == []


def test_rc_cut_metadata(project, load):
    meta = load(project(), "rc-cut", "1.1.0", "rc2", "--remote", "apache")["metadata"]
    assert meta["staging_url"] == "https://dist.apache.org/repos/dist/dev/foo/1.1.0-rc2/"
    assert meta["git_upstream_remote"] == "apache"
    assert meta["expected_artefacts"] == ["apache-foo-1.1.0-source.tar.gz"]
    assert meta["source_archive_prefix"] == "apache-foo-1.1.0"
    assert meta["digest_set"] == ["sha512"]
    assert meta["signing_key_fingerprint"] == ""


def test_announce_metadata_promote_clear(project, load):
    meta = load(project(), "announce-draft", "1.1.0", "--promote-timestamp", "2026-06-11 09:45 UTC")["metadata"]
    assert meta["promote_clear_after_utc"] == "2026-06-11T10:45:00Z"
    assert meta["dist_release_url"] == "https://dist.apache.org/repos/dist/release/foo/1.1.0/"
    assert meta["site_pr_files"][-1] == "content/announcements/1.1.0.md"


CONVENIENCE = BUILD_SOURCE_ONLY.replace(
    "## Convenience artefacts\n\nNone — a source-only project.\n",
    """## Convenience artefacts

```yaml
convenience_artefacts:
  - name: apache-foo-<version>-bin.tar.gz
    kind: binary-tarball
    build_command: |
      mvn clean package
    publish_channel: dist-release
  - name: apache_foo-<version>-py3-none-any.whl
    kind: wheel
    version_scheme: python
    reproducibility: documented-divergence
    known_divergences:
      - "RECORD: hash order"
    publish_channel: pypi
    publish_command: twine upload dist/apache_foo-<version>*   # after the vote
  - name: foo-image
    kind: container-image
    publish_channel: container-registry
    publish_command: docker push example/foo:<version>
```
""",
)


def test_promote_convenience_split(project, load):
    meta = load(
        project(build=CONVENIENCE),
        "promote",
        "1.1.0-rc1",
        "--verify-binary",
        "apache-foo-<version>-bin.tar.gz=identical",
        "--verify-binary",
        "apache_foo-1.1.0-py3-none-any.whl=WARN",
    )["metadata"]
    assert meta["target_url"] == "https://dist.apache.org/repos/dist/release/foo/1.1.0/"
    assert meta["convenience"]["publish"] == [
        {"name": "apache-foo-1.1.0-bin.tar.gz", "publish_channel": "dist-release", "publish_command": None},
        {"name": "apache_foo-1.1.0-py3-none-any.whl", "publish_channel": "pypi", "publish_command": "twine upload dist/apache_foo-1.1.0*"},
    ]
    assert meta["convenience"]["held"] == [{"name": "foo-image", "reason": "not checked"}]


def test_promote_differs_is_held(project, load):
    meta = load(project(build=CONVENIENCE), "promote", "1.1.0-rc1", "--verify-binary", "foo-image=differs")["metadata"]
    assert {"name": "foo-image", "reason": "differs"} in meta["convenience"]["held"]


def test_convenience_yaml_parsed(project, load):
    entries = load(project(build=CONVENIENCE), None)["build"]["convenience_artefacts"]
    assert entries[0]["build_command"] == "mvn clean package"
    assert entries[0]["reproducibility"] == "off"  # inherits reproducibility_binaries
    assert entries[1]["known_divergences"] == ["RECORD: hash order"]
    assert entries[1]["version_scheme"] == "python"


@pytest.mark.parametrize(
    ("template", "rc", "bucket", "expected"),
    [
        ("https://dist.apache.org/repos/dist/<bucket>/foo/<version>/", "rc1", "dev", "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc1/"),
        ("https://dist.apache.org/repos/dist/<bucket>/foo/<version>/", None, "release", "https://dist.apache.org/repos/dist/release/foo/1.0.0/"),
        ("https://dist.apache.org/repos/dist/dev/foo/<version>-<rcN>/", "rc3", "dev", "https://dist.apache.org/repos/dist/dev/foo/1.0.0-rc3/"),
        ("https://dist.apache.org/repos/dist/dev/foo/<version>-<rcN>/", None, "release", "https://dist.apache.org/repos/dist/dev/foo/1.0.0/"),
    ],
)
def test_render_dist_url(template, rc, bucket, expected):
    assert render_dist_url(template, "1.0.0", rc, bucket) == expected


def test_plus_one_hour_formats():
    assert plus_one_hour("2026-06-11 09:45 UTC") == "2026-06-11T10:45:00Z"
    assert plus_one_hour("2026-06-11T23:30:00+00:00") == "2026-06-12T00:30:00Z"


def test_parse_value_shapes():
    assert md.parse_value("*(unset)*") is None
    assert md.parse_value("`72`") == "72"
    assert md.parse_value("`a`, `b` *(e.g. x)*") == ["a", "b"]
    assert md.parse_value("`setup.cfg`", "version_manifest_files") == ["setup.cfg"]
    assert md.parse_value("`https://x/<version>/` — the page") == "https://x/<version>/"


def test_framework_templates_parse():
    """The shipped templates load: TODO sections read as unset, examples are ignored."""
    build = load_build((TEMPLATES / "release-build.md").read_text(encoding="utf-8"))
    assert build.digest_set == []  # TODO placeholder
    assert build.expected_artefacts == []
    assert build.convenience_artefacts == [] and build.template_example_skipped
    assert "version_scheme" in (TEMPLATES / "release-build.md").read_text(encoding="utf-8")
    assert build.source_archive_method == "git-archive"
    rmc = md.table_values((TEMPLATES / "release-management-config.md").read_text(encoding="utf-8"))
    assert rmc["release_dist_backend"] == "svnpubsub"
    assert rmc["rm_key_fingerprint"] is None
    assert rmc["version_manifest_files"] == ["setup.cfg", "foo/__init__.py"]
    assert "github-discussion" not in rmc  # the mechanism table is not a key table
    roster = md.parse_roster(TEMPLATES / "pmc-roster.md")
    assert roster is not None and roster.rows == [] and roster.placeholder_rows == 3


def test_main_prints_json(project, capsys):
    root = project()
    assert cli.main(["preflight", "--project-root", str(root), "--user-config", str(root / "none"), "--skill", "release-archive-sweep"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_unknown_skill_is_usage_error(project):
    with pytest.raises(SystemExit):
        cli.run(["preflight", "--project-root", str(project()), "--skill", "nope"])
