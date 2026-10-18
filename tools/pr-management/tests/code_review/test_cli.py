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
"""`pr-management code-review …` end to end, over saved reads."""

from __future__ import annotations

import base64
import json
import shlex
from pathlib import Path
from typing import Any

import pytest

from pr_management import cli

from .builders import NOW, node, review

DIFF = """diff --git a/scheduler/job.py b/scheduler/job.py
--- a/scheduler/job.py
+++ b/scheduler/job.py
@@ -1,2 +1,3 @@
 a = 1
+b = 2
 c = 3
"""


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> dict[str, Any]:
    assert cli.main(list(argv)) == 0
    return json.loads(capsys.readouterr().out)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "project.md").write_text(
        "| Key | Value |\n|---|---|\n| `upstream_repo` | `acme/product` |\n"
        "| `project_name` | `Apache Product` |\n"
        "| `upstream_contributing_docs_url` | `https://example.org/contrib` |\n"
    )
    (cfg / "pr-management-config.md").write_text(
        "| Key | Default | Notes |\n|---|---|---|\n| `real_ci_patterns` | `Tests` | x |\n"
    )
    return cfg


@pytest.fixture()
def saved(tmp_path: Path) -> Path:
    path = tmp_path / "saved"
    path.mkdir()
    page = {
        "data": {
            "repository": {
                "pullRequests": {
                    "nodes": [
                        node(7, requested=["alice"], files=["scheduler/job.py"]),
                        node(8, files=["docs/x.md"]),
                    ]
                }
            }
        }
    }
    (path / "cr-open.json").write_text(json.dumps([page]))
    owners = base64.b64encode(b"/scheduler/ @acme/core\n").decode()
    (path / "cr-codeowners-github.json").write_text(json.dumps(owners))
    (path / "team-core.txt").write_text("alice\nbob\n")
    (path / "viewer-commits.json").write_text(json.dumps([[]]))
    full = node(7, requested=["alice"], files=["scheduler/job.py"], reviews=[review("bob", "COMMENTED")])
    (path / "cr-pr-7.json").write_text(
        json.dumps(
            {
                "data": {
                    "viewer": {"login": "alice"},
                    "repository": {"viewerPermission": "WRITE", "pullRequest": full},
                }
            }
        )
    )
    (path / "diff-7.patch").write_text(DIFF)
    (path / "cr-pr-template.json").write_text(json.dumps(base64.b64encode(b"## Summary\n").decode()))
    (path / "stack-7.json").write_text(json.dumps({"data": {"repository": {"pullRequest": {"stack": None}}}}))
    return path


def test_queue_unions_the_signals_and_asks_for_nothing_more(
    capsys: pytest.CaptureFixture[str], project: Path, saved: Path
) -> None:
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "queue",
        "--saved-dir",
        str(saved),
        "--viewer",
        "alice",
        "--now",
        NOW.isoformat(),
    )
    assert out["needs"] == []
    (row,) = out["queue"]
    assert row["number"] == 7 and row["chips"][:2] == ["review-requested", "codeowner: scheduler/job.py"]


def test_queue_asks_for_missing_reads(capsys: pytest.CaptureFixture[str], project: Path, saved: Path) -> None:
    (saved / "team-core.txt").unlink()
    (saved / "viewer-commits.json").unlink()
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "queue",
        "--saved-dir",
        str(saved),
        "--viewer",
        "alice",
        "--now",
        NOW.isoformat(),
    )
    ops = {n["op"] for n in out["needs"]}
    assert ops == {"team-members", "cr-viewer-commits"}


def test_context_then_disposition_then_render(
    capsys: pytest.CaptureFixture[str], project: Path, saved: Path, tmp_path: Path
) -> None:
    ctx = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "context",
        "--saved-dir",
        str(saved),
        "--pr",
        "7",
        "--repo-root",
        str(tmp_path),
    )
    assert ctx["needs"] == [] and ctx["slop"]["outcome"] == "silent" and "PR #7" in ctx["headline"]
    findings = tmp_path / "findings.json"
    findings.write_text(
        json.dumps(
            [
                {
                    "file": "scheduler/job.py",
                    "line": 2,
                    "severity": "minor",
                    "rule_id": "naming",
                    "explanation": "Name b better; ask @carol.",
                    "comment": "Name b better.",
                }
            ]
        )
    )
    dis = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "disposition",
        "--saved-dir",
        str(saved),
        "--pr",
        "7",
        "--viewer",
        "alice",
        "--findings",
        str(findings),
    )
    assert dis["disposition"] == "COMMENT" and dis["footer"] == "comment-maintainer"
    summary = tmp_path / "summary.txt"
    summary.write_text("One naming nit inline.")
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "render",
        "--saved-dir",
        str(saved),
        "--pr",
        "7",
        "--findings",
        str(findings),
        "--summary",
        str(summary),
        "--disposition",
        "COMMENT",
        "--out-dir",
        str(tmp_path / "out"),
        "--permission",
        "write",
    )
    assert out["footer_verified"] and out["live_mentions"] == [] and out["inline_threads"] == 1
    assert shlex.split(out["post_command"]) == ["gh", "api", "graphql", "--input", out["payload_file"]]
    body = Path(out["body_file"]).read_text()
    assert "Apache Product maintainer" in body and "https://example.org/contrib" in body


def test_guard_needs_the_liveness_read_then_checks_the_head(
    capsys: pytest.CaptureFixture[str], project: Path, saved: Path
) -> None:
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "guard",
        "--saved-dir",
        str(saved),
        "--pr",
        "7",
        "--head",
        "abc1234def",
        "--viewer",
        "carol",
    )
    assert not out["proceed"] and out["needs"][0]["op"] == "gql-pr-liveness"
    (saved / "liveness-7.json").write_text(
        json.dumps(
            {"data": {"repository": {"pullRequest": {"headRefOid": "fffffff", "mergeable": "MERGEABLE"}}}}
        )
    )
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "guard",
        "--saved-dir",
        str(saved),
        "--pr",
        "7",
        "--head",
        "abc1234def",
        "--viewer",
        "carol",
    )
    assert not out["proceed"] and "new commits" in out["reason"]


def test_session_summary(capsys: pytest.CaptureFixture[str], project: Path, tmp_path: Path) -> None:
    ses = tmp_path / "session.json"
    for pr, outcome in ((1, "APPROVE"), (2, "COMMENT"), (3, "skipped")):
        _run(
            capsys,
            "--config-dir",
            str(project),
            "code-review",
            "session",
            "record",
            "--session",
            str(ses),
            "--pr",
            str(pr),
            "--outcome",
            outcome,
            "--now",
            NOW.isoformat(),
        )
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "session",
        "summary",
        "--session",
        str(ses),
        "--now",
        NOW.isoformat(),
    )
    assert out["counts"] == {"APPROVE": 1, "COMMENT": 1, "skipped": 1} and "Reviewed: 2" in out["text"]


def test_slop_comment_builds_quoted_commands(
    capsys: pytest.CaptureFixture[str], project: Path, tmp_path: Path
) -> None:
    issues = tmp_path / "issues.txt"
    issues.write_text("The `team_project/` directory looks like a class project.\n")
    out = _run(
        capsys,
        "--config-dir",
        str(project),
        "code-review",
        "slop-comment",
        "--pr",
        "9",
        "--issues",
        str(issues),
        "--out-dir",
        str(tmp_path / "o"),
    )
    assert shlex.split(out["comment_command"])[:4] == ["gh", "pr", "comment", "9"]
    assert "Apache Product" in Path(out["body_file"]).read_text()
