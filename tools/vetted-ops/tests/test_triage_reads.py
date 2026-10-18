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
"""The pr-management-triage reads, and `--save`."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vetted_ops import cli, config, ops

POLICY = """
workspace = '{workspace}'

[repos]
upstream = "acme/product"

[values]
upstream_labels = ["ready for maintainer review", "area:scheduler"]

[callers]
"pr-management-triage" = [
    "gql-pr-triage-open", "gql-pr-triage-label", "gql-pr-triage-author",
    "gql-pr-triage-review-requested", "gql-pr-triage-one", "gql-main-recent-failures",
    "runs-action-required", "runs-at-head", "check-runs", "gql-pr-triage-preflight", "compare-behind", "team-members",
    "pr-ready",
]
"""


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A workspace whose saved/ directory is marked for --save."""
    ws = tmp_path / "scratch"
    ws.mkdir()
    ws.chmod(0o700)
    (ws / "saved").mkdir(mode=0o700)
    (ws / "saved" / ops.SAVE_MARKER).write_text("")
    return ws


@pytest.fixture()
def policy_path(tmp_path: Path, workspace: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(POLICY.format(workspace=workspace))
    return path


@pytest.fixture()
def policy(policy_path: Path) -> config.Config:
    return config.load(policy_path)


def _argv(policy: config.Config, name: str, *values: str) -> list[str]:
    op = ops.resolve(name)
    params, _ = cli._validate_params(op, list(values), policy)
    built = cli.build_argv(op, params, policy)
    assert isinstance(built, list)
    return built


def _search(argv: list[str]) -> str:
    (value,) = [a for a in argv if a.startswith("searchQuery=")]
    return value.removeprefix("searchQuery=")


# --- the search is pinned to the upstream repo -------------------------------


def test_open_sweep_searches_the_policy_repo_on_every_page(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-triage-open")
    assert argv[:3] == ["gh", "api", "graphql"]
    assert "--paginate" in argv and "--slurp" in argv
    assert _search(argv) == "repo:acme/product is:pr is:open sort:updated-asc"
    assert argv[-1].endswith("pr-triage-search.graphql")


def test_label_sweep_quotes_a_policy_label(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-triage-label", "ready for maintainer review")
    assert _search(argv).endswith(' label:"ready for maintainer review"')
    assert _search(argv).startswith("repo:acme/product ")


def test_label_sweep_refuses_a_label_the_policy_does_not_declare(policy: config.Config) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "gql-pr-triage-label", 'x" repo:evil/repo "')


@pytest.mark.parametrize(
    ("name", "qualifier"),
    [("gql-pr-triage-author", "author"), ("gql-pr-triage-review-requested", "review-requested")],
)
def test_login_sweeps_take_a_validated_login(policy: config.Config, name: str, qualifier: str) -> None:
    assert _search(_argv(policy, name, "alice")).endswith(f" {qualifier}:alice")
    with pytest.raises(ops.ParamError):
        _argv(policy, name, "alice repo:evil/repo")


def test_one_pr_uses_the_policy_owner_and_name(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-triage-one", "42")
    assert "owner=acme" in argv and "repo=product" in argv and "number=42" in argv


def test_rest_reads_stay_under_the_upstream_repo(policy: config.Config) -> None:
    assert _argv(policy, "runs-action-required")[2] == (
        "repos/acme/product/actions/runs?status=action_required&per_page=100"
    )
    assert (
        _argv(policy, "check-runs", "abc1234")[2]
        == "repos/acme/product/commits/abc1234/check-runs?per_page=100"
    )
    assert (
        _argv(policy, "compare-behind", "main", "abc1234")[2] == "repos/acme/product/compare/main...abc1234"
    )
    assert _argv(policy, "team-members", "committers")[2] == "orgs/acme/teams/committers/members?per_page=100"


def test_preflight_reads_every_label_page(policy: config.Config) -> None:
    argv = _argv(policy, "gql-pr-triage-preflight")
    assert argv[:5] == ["gh", "api", "graphql", "--paginate", "--slurp"]
    assert "owner=acme" in argv and "repo=product" in argv


def test_compare_behind_refuses_traversal(policy: config.Config) -> None:
    with pytest.raises(ops.ParamError):
        _argv(policy, "compare-behind", "main", "../../other")


def test_the_triage_reads_are_all_reads() -> None:
    names = [
        "gql-pr-triage-open",
        "gql-pr-triage-label",
        "gql-pr-triage-author",
        "gql-pr-triage-review-requested",
        "gql-pr-triage-one",
        "gql-main-recent-failures",
        "runs-action-required",
        "runs-at-head",
        "check-runs",
        "compare-behind",
        "team-members",
    ]
    assert all(not ops.OPS[n].writes for n in names)


# --- the query documents ------------------------------------------------------


def _fragment(name: str) -> str:
    text = (ops.QUERIES_DIR / f"{name}.graphql").read_text()
    match = re.search(r"^fragment TriagePR on PullRequest \{.*", text, flags=re.MULTILINE | re.DOTALL)
    assert match
    return match.group(0)


def test_the_search_and_single_pr_shapes_are_one_fragment() -> None:
    assert _fragment("pr-triage-search") == _fragment("pr-triage-one")


def test_the_search_document_has_exactly_one_page_info() -> None:
    """`gh --paginate` follows the first hasNextPage/endCursor in the response."""
    text = (ops.QUERIES_DIR / "pr-triage-search.graphql").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("pageInfo") == 1
    assert "$endCursor" in code


# --- --save -----------------------------------------------------------------


class _Captured:
    def __init__(self, stdout: bytes, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def _fake_run(output: bytes, seen: list[dict[str, Any]]) -> Any:
    def run(argv: list[str], **kwargs: Any) -> _Captured:
        seen.append({"argv": argv, **kwargs})
        return _Captured(output)

    return run


def test_save_writes_the_output_and_prints_one_line(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(cli.subprocess, "run", _fake_run(b'[{"data": 1}]', seen))
    rc = cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            "--save",
            "pages.json",
            "gql-pr-triage-open",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_OK
    saved = workspace.resolve() / "saved" / "pages.json"
    assert saved.read_bytes() == b'[{"data": 1}]'
    assert oct(saved.stat().st_mode & 0o777) == "0o600"
    assert json.loads(capsys.readouterr().out) == {"saved": str(saved), "bytes": 13}
    assert seen[0]["stdout"] is subprocess.PIPE


def test_save_overwrites_a_previous_save(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for payload in (b"first, and longer", b"second"):
        monkeypatch.setattr(cli.subprocess, "run", _fake_run(payload, []))
        assert (
            cli.main(
                [
                    "--caller",
                    "pr-management-triage",
                    "--config",
                    str(policy_path),
                    "--save",
                    "x.json",
                    "runs-action-required",
                ],
                read_only=True,
            )
            == cli.EXIT_OK
        )
    assert (workspace / "saved" / "x.json").read_bytes() == b"second"


@pytest.mark.parametrize("name", ["../escape.json", "sub/dir.json", ".hidden", "", "a" * 101])
def test_save_refuses_a_name_that_is_not_one_component(
    policy_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setattr(cli.subprocess, "run", _fake_run(b"x", []))
    rc = cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            f"--save={name}",
            "runs-action-required",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_POLICY


def _save_rc(policy_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes = b"x") -> int:
    monkeypatch.setattr(cli.subprocess, "run", _fake_run(payload, []))
    return cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            "--save",
            "x.json",
            "runs-action-required",
        ],
        read_only=True,
    )


def test_save_never_creates_the_saved_directory(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A policy can name any directory you own; --save must not write into one nobody marked."""
    for child in (workspace / "saved").iterdir():
        child.unlink()
    (workspace / "saved").rmdir()
    assert _save_rc(policy_path, monkeypatch) == cli.EXIT_POLICY
    assert not (workspace / "saved").exists()


def test_save_refuses_an_unmarked_saved_directory(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace / "saved" / ops.SAVE_MARKER).unlink()
    assert _save_rc(policy_path, monkeypatch) == cli.EXIT_POLICY
    assert not (workspace / "saved" / "x.json").exists()


def test_save_refuses_a_symlinked_marker(
    policy_path: Path, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace / "saved" / ops.SAVE_MARKER).unlink()
    elsewhere = tmp_path / "marker"
    elsewhere.write_text("")
    (workspace / "saved" / ops.SAVE_MARKER).symlink_to(elsewhere)
    assert _save_rc(policy_path, monkeypatch) == cli.EXIT_POLICY


def test_save_refuses_a_symlinked_saved_directory(
    policy_path: Path, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ops.SAVE_MARKER).write_text("")
    for child in (workspace / "saved").iterdir():
        child.unlink()
    (workspace / "saved").rmdir()
    (workspace / "saved").symlink_to(elsewhere)
    assert _save_rc(policy_path, monkeypatch) == cli.EXIT_POLICY
    assert sorted(p.name for p in elsewhere.iterdir()) == [ops.SAVE_MARKER]


def test_save_replaces_a_symlink_instead_of_writing_through_it(
    policy_path: Path, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim = tmp_path / "victim"
    victim.write_text("untouched")
    os.symlink(victim, workspace / "saved" / "x.json")
    assert _save_rc(policy_path, monkeypatch, b"saved") == cli.EXIT_OK
    assert victim.read_text() == "untouched"
    assert not (workspace / "saved" / "x.json").is_symlink()
    assert (workspace / "saved" / "x.json").read_bytes() == b"saved"


def test_save_replaces_a_hard_link_instead_of_writing_through_it(
    policy_path: Path, workspace: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim = tmp_path / "victim"
    victim.write_text("untouched")
    os.link(victim, workspace / "saved" / "x.json")
    assert _save_rc(policy_path, monkeypatch, b"saved") == cli.EXIT_OK
    assert victim.read_text() == "untouched"
    assert (workspace / "saved" / "x.json").read_bytes() == b"saved"


def test_save_leaves_no_temporary_file(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _save_rc(policy_path, monkeypatch) == cli.EXIT_OK
    assert sorted(p.name for p in (workspace / "saved").iterdir()) == [ops.SAVE_MARKER, "x.json"]


def test_save_refuses_an_open_workspace(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace.chmod(0o777)
    monkeypatch.setattr(cli.subprocess, "run", _fake_run(b"x", []))
    rc = cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            "--save",
            "x.json",
            "runs-action-required",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_POLICY


def test_save_refuses_a_write_operation(policy_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []
    monkeypatch.setattr(cli.subprocess, "run", _fake_run(b"x", seen))
    rc = cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            "--save",
            "x.json",
            "pr-ready",
            "7",
        ],
    )
    assert rc == cli.EXIT_POLICY
    assert seen == []


def test_a_failed_read_saves_nothing(
    policy_path: Path, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli.subprocess, "run", lambda argv, **kw: _Captured(b"partial", returncode=1))
    rc = cli.main(
        [
            "--caller",
            "pr-management-triage",
            "--config",
            str(policy_path),
            "--save",
            "x.json",
            "runs-action-required",
        ],
        read_only=True,
    )
    assert rc == cli.EXIT_COMMAND
    assert not (workspace / "saved" / "x.json").exists()
