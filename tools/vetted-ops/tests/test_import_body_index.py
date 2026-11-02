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

"""Authorization boundaries for the security-import body index."""

from pathlib import Path

import pytest

from vetted_ops import cli, ops, tracker_backends


def test_body_index_is_a_separate_read_only_operation() -> None:
    body_index = ops.resolve("issue-list-with-bodies")
    ordinary_list = ops.resolve("issue-list")

    assert not body_index.writes
    assert body_index.params == ()
    body_argv = body_index.build({"tracker_repo": "acme/private-tracker"})
    ordinary_argv = ordinary_list.build({"tracker_repo": "acme/private-tracker"}, "all")

    assert isinstance(body_argv, list)
    assert isinstance(ordinary_argv, list)
    assert "body" in body_argv[body_argv.index("--json") + 1].split(",")
    assert "body" not in ordinary_argv[ordinary_argv.index("--json") + 1].split(",")


def test_unsupported_backends_refuse_body_index() -> None:
    assert "issue-list-with-bodies" in tracker_backends.NOT_ON_BACKEND


def test_policy_without_body_index_grant_refuses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)

    policy = tmp_path / "policy.toml"
    policy.write_text(
        f'''workspace = "{workspace}"

[tracker]
platform = "github"
repo = "acme/private-tracker"

[repos]
upstream = "acme/product"

[values]
issue_states = ["open", "closed", "all"]

[callers]
"security-issue-import" = ["issue-list"]
''',
        encoding="utf-8",
    )

    code = cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-list-with-bodies",
        ],
        read_only=True,
    )

    assert code != 0
    assert "not permitted" in capsys.readouterr().err


def test_explicit_grant_allows_body_index_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    workspace = tmp_path / "scratch"
    workspace.mkdir()
    workspace.chmod(0o700)

    policy = tmp_path / "policy.toml"
    policy.write_text(
        f'''workspace = "{workspace}"

[repos]
upstream = "acme/product"
tracker = "acme/private-tracker"

[values]
issue_states = ["open", "closed", "all"]

[callers]
"security-issue-import" = ["issue-list-with-bodies"]
''',
        encoding="utf-8",
    )

    code = cli.main(
        [
            "--config",
            str(policy),
            "--caller",
            "security-issue-import",
            "--dry-run",
            "issue-list-with-bodies",
        ],
        read_only=True,
    )

    output = capsys.readouterr()

    assert code == 0
    assert "--repo acme/private-tracker" in output.out
    assert "number,title,state,url,body" in output.out
