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
"""Tracker operations translated to the local-files and Jira security trackers."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vetted_ops import cli, config, ops, tracker_backends

REPO_TOOLS = Path(__file__).resolve().parents[2]

ALL_TRACKER_OPS = sorted(tracker_backends.TRANSLATIONS) + sorted(tracker_backends.NOT_ON_BACKEND)

BASE = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[values]
labels = ["needs triage", "cve allocated"]
milestones = ["1.2.3"]
assignees = ["alice"]
issue_states = ["open", "closed", "all"]
close_reasons = ["completed", "not planned"]

[values.board_columns]
"Assessed" = "opt_assessed"

[callers]
"security-issue-sync" = {ops}
"""

LOCAL = """
[tracker]
platform = "local-files"
project = "{project}"
root = "{root}"
"""

JIRA = """
[tracker]
platform = "jira"
project = "{project}"
jira_url = "https://issues.example.org/jira"
jira_project = "FOOSEC"
jira_security_level = "Security Team"
"""


def _write_policy(tmp_path: Path, tracker: str, **fmt: str) -> Path:
    workspace = tmp_path / "scratch"
    workspace.mkdir(exist_ok=True)
    workspace.chmod(0o700)
    path = tmp_path / "config.toml"
    path.write_text(BASE.format(workspace=workspace, ops=json.dumps(ALL_TRACKER_OPS)) + tracker.format(**fmt))
    return path


@pytest.fixture()
def local_policy(tmp_path: Path) -> Path:
    return _write_policy(
        tmp_path, LOCAL, project=str(REPO_TOOLS / "local-tracker"), root=str(tmp_path / "reports")
    )


@pytest.fixture()
def jira_policy(tmp_path: Path) -> Path:
    return _write_policy(tmp_path, JIRA, project=str(REPO_TOOLS / "jira"))


def _body(policy: Path, text: str = "hello\n") -> str:
    path = policy.parent / "scratch" / "body.md"
    path.write_text(text)
    return str(path)


SAMPLE = {
    "number": "7",
    "state": "open",
    "label": "needs triage",
    "milestone": "1.2.3",
    "login": "alice",
    "reason": "not planned",
    "title": "Path traversal in upload",
    "query": "upload traversal",
    "action": "Sync",
    "field": "Affected versions",
    "comment_id": "12",
    "item_id": "PVTI_abc",
    "content_id": "I_abc",
    "column": "Assessed",
}


def _args(op: ops.Op, policy: Path) -> list[str]:
    return [(_body(policy) if p in op.body_files else SAMPLE[p]) for p in op.params]


# --- the mapping is complete -------------------------------------------------


def test_every_operation_that_addresses_the_tracker_is_mapped(tmp_path: Path) -> None:
    """Determined by construction, not by the hand-kept tables: an operation that
    refuses for want of a tracker repo addresses the tracker, so on a non-GitHub
    tracker it must either translate or refuse by name — never run its gh builder."""
    workspace = tmp_path / "w"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "c.toml"
    cfg_path.write_text(BASE.format(workspace=workspace, ops="[]"))
    trackerless = config.load(cfg_path).as_mapping()
    (workspace / "b.md").write_text("x")
    addressing = set()
    for name, op in ops.OPS.items():
        params = {
            p: (str(workspace / "b.md") if p in op.body_files else SAMPLE.get(p, "1")) for p in op.params
        }
        try:
            op.build(trackerless, **params)
        except KeyError:
            continue  # needs config values this policy omits (board ids); not a repo address
        except ops.ParamError as exc:
            if "does not configure" in str(exc):
                addressing.add(name)
    assert addressing, "expected tracker operations in the catalogue"
    unmapped = addressing - set(tracker_backends.TRANSLATIONS) - set(tracker_backends.NOT_ON_BACKEND)
    assert not unmapped, f"tracker operations with no backend mapping: {sorted(unmapped)}"
    # And nothing is mapped that is not a catalogue operation.
    assert set(tracker_backends.TRANSLATIONS) <= set(ops.OPS)
    assert set(tracker_backends.NOT_ON_BACKEND) <= set(ops.OPS)


# --- policy validation -------------------------------------------------------


@pytest.mark.parametrize(
    ("tracker", "fmt", "message"),
    [
        ('[tracker]\nplatform = "svn"\n', {}, "platform must be one of"),
        (LOCAL, {"project": "tools/local-tracker", "root": "/r"}, "must be absolute"),
        (LOCAL, {"project": "/usr/bin", "root": "/r"}, "tools/local-tracker directory"),
        (LOCAL, {"project": "/x/local-tracker", "root": "reports"}, "must be absolute"),
        (JIRA.replace("https://", "http://"), {"project": "/x/jira"}, "https://"),
        (JIRA.replace('"FOOSEC"', '"foo sec"'), {"project": "/x/jira"}, "project key"),
        (JIRA.replace('"Security Team"', '"-x"'), {"project": "/x/jira"}, "one line"),
    ],
)
def test_bad_tracker_policy_is_refused(
    tmp_path: Path, tracker: str, fmt: dict[str, str], message: str
) -> None:
    path = _write_policy(tmp_path, tracker, **fmt)
    with pytest.raises(config.ConfigError, match=message):
        config.load(path)


def test_github_platform_keeps_the_gh_builders(tmp_path: Path) -> None:
    path = _write_policy(tmp_path, '[tracker]\nplatform = "github"\n')
    assert config.load(path).tracker_backend is None


# --- translation -------------------------------------------------------------


def _dry_run(policy: Path, op_name: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    op = ops.OPS[op_name]
    code = cli.main(
        ["--config", str(policy), "--caller", "security-issue-sync", "--dry-run", op_name, *_args(op, policy)]
    )
    captured = capsys.readouterr()
    return code, captured.out, captured.err


EXPECTED_LOCAL = {
    "issue-view": ["view", "7"],
    "issue-list": ["list", "--state", "open", "--limit", "1000"],
    "issue-list-label": ["list", "--state", "open", "--label", "needs triage", "--limit", "1000"],
    "issue-comments": ["view", "7", "--comments"],
    "issue-search": ["list", "--state", "all", "--search=upload traversal", "--limit", "100"],
    "label-list": ["labels"],
    "issue-create": ["create", "--title=Path traversal in upload", "--body-file", "-"],
    "issue-add-label": ["edit", "7", "--add-label", "needs triage"],
    "issue-remove-label": ["edit", "7", "--remove-label", "needs triage"],
    "issue-set-milestone": ["edit", "7", "--milestone", "1.2.3"],
    "issue-add-assignee": ["edit", "7", "--add-assignee", "alice"],
    "issue-remove-assignee": ["edit", "7", "--remove-assignee", "alice"],
    "issue-comment": ["comment", "7", "--body-file", "-"],
    "issue-edit-body": ["edit", "7", "--body-file", "-"],
    "issue-edit-title": ["edit", "7", "--title=Path traversal in upload"],
    "issue-close": ["close", "7", "--reason", "not-planned"],
    "issue-reopen": ["reopen", "7"],
    "rollup-append": ["rollup-append", "7", "--action", "Sync", "--entry-body-file", "-"],
    "rollup-amend-latest": ["rollup-amend-latest", "7", "--action", "Sync", "--entry-body-file", "-"],
    "body-field-get": ["field-get", "7", "Affected versions"],
    "body-field-set": ["field-set", "7", "Affected versions", "--value-file", "-"],
    "tracker-pending": ["pending"],
    "tracker-publish": ["publish", "--message-file", "-", "--push"],
}


def test_expected_table_covers_every_translation() -> None:
    assert set(EXPECTED_LOCAL) == set(tracker_backends.TRANSLATIONS)


@pytest.mark.parametrize("op_name", sorted(EXPECTED_LOCAL))
def test_local_translation(local_policy: Path, op_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = _dry_run(local_policy, op_name, capsys)
    assert code == cli.EXIT_OK
    argv = out.splitlines()[0].split(" ")
    prefix = ["uv", "run", "--quiet", "--project", str(REPO_TOOLS / "local-tracker"), "magpie-local-tracker"]
    assert argv[: len(prefix)] == prefix
    assert argv[len(prefix) : len(prefix) + 2] == ["--root", str(local_policy.parent / "reports")]
    # Titles and queries hold spaces; compare the joined tail.
    assert " ".join(argv[len(prefix) + 2 :]) == " ".join(EXPECTED_LOCAL[op_name])
    if ops.OPS[op_name].body_files:
        assert "(stdin: 6 bytes)" in out


@pytest.mark.parametrize("op_name", sorted(set(EXPECTED_LOCAL) - {"tracker-pending", "tracker-publish"}))
def test_jira_translation_pins_the_target(
    jira_policy: Path, op_name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = _dry_run(jira_policy, op_name, capsys)
    assert code == cli.EXIT_OK
    line = out.splitlines()[0]
    assert (
        "magpie-jira-tracker --url https://issues.example.org/jira --project FOOSEC --security-level Security Team"
        in line
    )
    assert line.endswith(" ".join(EXPECTED_LOCAL[op_name]))


@pytest.mark.parametrize("op_name", ["tracker-pending", "tracker-publish"])
def test_publish_is_local_files_only(
    jira_policy: Path, op_name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, err = _dry_run(jira_policy, op_name, capsys)
    assert code == cli.EXIT_POLICY
    assert "writes are immediate" in err


@pytest.mark.parametrize("op_name", sorted(tracker_backends.NOT_ON_BACKEND))
def test_unmapped_operations_refuse_by_name(
    local_policy: Path, op_name: str, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = _dry_run(local_policy, op_name, capsys)
    assert code == cli.EXIT_POLICY and out == ""
    assert "is not available on the local-files tracker" in err


def test_a_caller_cannot_retarget_the_tracker(local_policy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The folder comes from policy; a parameter that looks like a flag is refused first."""
    try:
        code = cli.main(
            [
                "--config",
                str(local_policy),
                "--caller",
                "security-issue-sync",
                "issue-view",
                "--root=/elsewhere",
            ]
        )
    except SystemExit as exc:  # argparse rejects the unknown option outright
        code = int(exc.code or 0)
    assert code != cli.EXIT_OK


def test_query_refuses_qualifiers() -> None:
    with pytest.raises(ops.ParamError, match="qualifiers"):
        ops.query("repo:apache/public xss")
    with pytest.raises(ops.ParamError):
        ops.query("a\nb")
    assert ops.query("  xss in login ") == "xss in login"
    # A leading dash exposed by stripping is still refused.
    with pytest.raises(ops.ParamError, match="may not start with"):
        ops.query(" --repo=other/repo")


def test_github_search_ends_options_before_the_query(tmp_path: Path) -> None:
    workspace = tmp_path / "w"
    workspace.mkdir()
    workspace.chmod(0o700)
    cfg_path = tmp_path / "c.toml"
    text = BASE.format(workspace=workspace, ops="[]").replace(
        'upstream = "acme/product"', 'tracker = "acme/tracker"\nupstream = "acme/product"'
    )
    cfg_path.write_text(text)
    argv = ops.OPS["issue-search"].build(config.load(cfg_path).as_mapping(), query="xss")
    assert isinstance(argv, list)
    assert argv[-2:] == ["--", "xss"]


def test_a_dash_leading_title_stays_a_value(local_policy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = _body(local_policy)
    argv = [
        "--config",
        str(local_policy),
        "--caller",
        "security-issue-sync",
        "--dry-run",
        "issue-create",
        " -x",
        body,
    ]
    assert cli.main(argv) == cli.EXIT_OK
    assert "--title=-x" in capsys.readouterr().out


# --- entry points keep their meaning ----------------------------------------


def test_read_entry_point_still_refuses_writes(local_policy: Path) -> None:
    for name in ("issue-add-label", "tracker-publish", "rollup-append"):
        op = ops.OPS[name]
        code = cli.main_read(
            ["--config", str(local_policy), "--caller", "security-issue-sync", name, *_args(op, local_policy)]
        )
        assert code == cli.EXIT_POLICY, name


def test_tracker_entry_point_admits_procedures_and_publish_only(
    local_policy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def run(name: str) -> int:
        op = ops.OPS[name]
        return cli.main_tracker(
            [
                "--config",
                str(local_policy),
                "--caller",
                "security-issue-sync",
                "--dry-run",
                name,
                *_args(op, local_policy),
            ]
        )

    assert run("rollup-append") == cli.EXIT_OK
    assert run("tracker-publish") == cli.EXIT_OK
    assert run("issue-add-label") == cli.EXIT_POLICY


# --- execution ---------------------------------------------------------------


def test_body_travels_on_stdin_and_backend_refusal_maps_to_policy(
    local_policy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def fake_run(argv: list[str], check: bool, input: bytes) -> subprocess.CompletedProcess[bytes]:
        seen["argv"], seen["input"] = argv, input
        return subprocess.CompletedProcess(argv, seen.get("rc", 0))

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    body = _body(local_policy, "secret report text")
    args = ["--config", str(local_policy), "--caller", "security-issue-sync", "issue-comment", "7", body]
    assert cli.main(args) == cli.EXIT_OK
    assert seen["input"] == b"secret report text"
    assert body not in seen["argv"]
    seen["rc"] = 4
    assert cli.main(args) == cli.EXIT_POLICY
    seen["rc"] = 5
    assert cli.main(args) == cli.EXIT_COMMAND


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv not installed")
def test_end_to_end_against_the_local_tracker(local_policy: Path, capfd: pytest.CaptureFixture[str]) -> None:
    """The translated argv is accepted by the real magpie-local-tracker."""
    root = local_policy.parent / "reports"
    subprocess.run(
        ["uv", "run", "--quiet", "--project", str(REPO_TOOLS / "local-tracker"), "magpie-local-tracker",
         "--root", str(root), "init", "--access-restricted"],
        check=True, capture_output=True,
    )  # fmt: skip

    def vop(*argv: str) -> int:
        return cli.main(["--config", str(local_policy), "--caller", "security-issue-sync", *argv])

    assert (
        vop("issue-create", "Path traversal in upload", _body(local_policy, "### Affected versions\n\n1.0\n"))
        == 0
    )
    assert vop("issue-add-label", "1", "needs triage") == 0
    assert vop("body-field-set", "1", "Affected versions", _body(local_policy, "1.0 to 1.2")) == 0
    assert vop("rollup-append", "1", "Sync", _body(local_policy, "synced")) == 0
    assert vop("issue-close", "1", "not planned") == 0
    capfd.readouterr()
    assert vop("issue-view", "1") == 0
    view = json.loads(capfd.readouterr().out)
    assert view["title"] == "Path traversal in upload"
    assert view["labels"] == ["needs triage"] and view["state"] == "closed"
    assert "1.0 to 1.2" in view["body"]
    assert (root / "SEC-0001" / "status-rollup.md").read_text().count("· Sync</summary>") == 1
