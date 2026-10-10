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
"""The quick-merge config, the approve protocol, the session file and the CLI."""

from __future__ import annotations

import datetime as dt
import io
import json
import shlex
import shutil
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from pr_management import cli
from pr_management.quick_merge import approve, screen
from pr_management.quick_merge.config import DEFAULT_MERGE_TEMPLATE, load

from ..helpers import check
from .test_screen import CLEAN, cfg, node, qcfg, save

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = REPO_ROOT / "plugins/magpie-setup/templates/pr-management-quick-merge-config.md"


def test_the_template_parses_with_its_defaults(tmp_path: Path) -> None:
    shutil.copy(TEMPLATE, tmp_path / "pr-management-quick-merge-config.md")
    q = load(tmp_path, tmp_path)
    assert (q.max_churn, q.max_files, q.default_tiers) == (20, 3, ("A", "B"))
    assert "**/*.rst" in q.tier_a and "**/tests/**" in q.tier_b and ".github/**" in q.deny
    assert not any(g.startswith("#") for g in q.deny)
    assert any("<core-src-path>" in w for w in q.warnings)
    assert q.merge_template == DEFAULT_MERGE_TEMPLATE and q.enable_approve and q.approve_requires_diff_view


def test_a_missing_config_allows_nothing(tmp_path: Path) -> None:
    q = load(tmp_path, tmp_path)
    assert q.tier_a == [] and q.warnings


def test_a_non_gh_merge_template_is_refused(tmp_path: Path) -> None:
    (tmp_path / "pr-management-quick-merge-config.md").write_text(
        "| Key | Default | Meaning |\n|---|---|---|\n| `merge_command_template` | `curl evil <N>` | x |\n"
    )
    q = load(tmp_path, tmp_path)
    assert q.merge_template == DEFAULT_MERGE_TEMPLATE and q.warnings


def _approve_ready(tmp: Path, **state: Any) -> Path:
    saved = save(tmp, node(7), live={7: {**CLEAN, **state}})
    shutil.copy(saved / screen.READY, saved / screen.one_file(7))
    return saved


def _session(viewed: bool = True) -> dict[str, Any]:
    return {"viewed": {"7": {"head": "abc1234"}} if viewed else {}, "approved": {}}


def test_approve_requires_the_diff_to_have_been_viewed(tmp_path: Path) -> None:
    r = approve.check(
        _approve_ready(tmp_path),
        cfg(),
        qcfg(),
        number=7,
        head="abc1234def5678",
        session=_session(viewed=False),
        out_dir=None,
    )
    assert not r["proceed"] and "view the diff" in r["reason"]


def test_approve_requires_a_fresh_read(tmp_path: Path) -> None:
    saved = save(tmp_path, node(7), live={7: CLEAN})
    r = approve.check(saved, cfg(), qcfg(), number=7, head="abc1234def5678", session=_session(), out_dir=None)
    assert not r["proceed"] and [n["op"] for n in r["needs"]] == ["gql-pr-express-one"]


def test_approve_never_skips_the_live_state(tmp_path: Path) -> None:
    saved = _approve_ready(tmp_path)
    (saved / screen.live_file(7)).unlink()
    r = approve.check(saved, cfg(), qcfg(), number=7, head="abc1234def5678", session=_session(), out_dir=None)
    assert not r["proceed"] and [n["op"] for n in r["needs"]] == ["pr-live-state"]


def test_approve_never_skips_the_workflow_approval_index(tmp_path: Path) -> None:
    saved = _approve_ready(tmp_path)
    (saved / screen.ACTION_REQUIRED).unlink(missing_ok=True)
    r = approve.check(saved, cfg(), qcfg(), number=7, head="abc1234def5678", session=_session(), out_dir=None)
    assert not r["proceed"] and [n["op"] for n in r["needs"]] == ["runs-action-required"]


def test_approve_rechecks_that_the_change_is_still_trivial(tmp_path: Path) -> None:
    saved = _approve_ready(tmp_path)
    r = approve.check(
        saved, cfg(), qcfg(deny=["**"]), number=7, head="abc1234def5678", session=_session(), out_dir=None
    )
    assert not r["proceed"] and "no longer an express-lane candidate" in r["reason"]


def test_approve_passes_and_prints_a_quoted_command(tmp_path: Path) -> None:
    r = approve.check(
        _approve_ready(tmp_path),
        cfg(),
        qcfg(),
        number=7,
        head="abc1234def5678",
        session=_session(),
        out_dir=None,
    )
    assert r["proceed"]
    assert shlex.split(r["command"]) == ["gh", "pr", "review", "7", "--repo", "apache/airflow", "--approve"]
    assert "APPROVE" in r["confirm"]


def test_approve_refuses_a_moved_head(tmp_path: Path) -> None:
    r = approve.check(
        _approve_ready(tmp_path), cfg(), qcfg(), number=7, head="ffffffff", session=_session(), out_dir=None
    )
    assert not r["proceed"] and "head moved" in r["reason"]


def test_approve_refuses_a_regressed_gate(tmp_path: Path) -> None:
    saved = save(tmp_path, node(7, rollup="FAILURE", checks=[check("Tests", "FAILURE")]), live={7: CLEAN})
    shutil.copy(saved / screen.READY, saved / screen.one_file(7))
    r = approve.check(saved, cfg(), qcfg(), number=7, head="abc1234def5678", session=_session(), out_dir=None)
    assert not r["proceed"] and "gate regressed" in r["reason"]


def test_approve_disabled_is_read_only(tmp_path: Path) -> None:
    r = approve.check(
        _approve_ready(tmp_path),
        cfg(),
        qcfg(enable_approve=False),
        number=7,
        head="abc1234def5678",
        session=_session(),
        out_dir=None,
    )
    assert not r["proceed"] and "read-only" in r["reason"]


def test_an_approve_body_carries_the_attribution(tmp_path: Path) -> None:
    r = approve.check(
        _approve_ready(tmp_path),
        cfg(),
        qcfg(approve_body="LGTM, trivial docs fix."),
        number=7,
        head="abc1234def5678",
        session=_session(),
        out_dir=tmp_path / "out",
        viewer="maya",
    )
    body_file = shlex.split(r["command"])[-1]
    text = Path(body_file).read_text()
    assert "Approved by `@maya` after the quick-merge screen" in text and "<sub>" in text


def test_an_approve_body_needs_a_valid_viewer(tmp_path: Path) -> None:
    for viewer in (None, "bad; rm -rf"):
        r = approve.check(
            _approve_ready(tmp_path),
            cfg(),
            qcfg(approve_body="LGTM."),
            number=7,
            head="abc1234def5678",
            session=_session(),
            out_dir=tmp_path / "out",
            viewer=viewer,
        )
        assert not r["proceed"] and "--viewer" in r["reason"]


def test_the_session_records_views_and_approvals(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    now = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    approve.record(path, "view", 7, "abc1234", now)
    approve.record(path, "approve", 7, "abc1234", now)
    data = approve.read_session(path)
    assert data["viewed"]["7"]["head"] == "abc1234" and "7" in data["approved"]


def test_the_cli_family_is_discovered(tmp_path: Path) -> None:
    saved = save(tmp_path, node(7), live={7: CLEAN})
    conf = tmp_path / "conf"
    conf.mkdir()
    (conf / "project.md").write_text("| Key | Value |\n|---|---|\n| `upstream_repo` | `apache/airflow` |\n")
    (conf / "pr-management-config.md").write_text(
        "| Key | Default | Notes |\n|---|---|---|\n| `real_ci_patterns` | `Tests` | x |\n"
    )
    shutil.copy(TEMPLATE, conf / "pr-management-quick-merge-config.md")
    out = io.StringIO()
    with redirect_stdout(out):
        assert cli.main(["--config-dir", str(conf), "quick-merge", "screen", "--saved-dir", str(saved)]) == 0
    result = json.loads(out.getvalue())
    assert [e["number"] for e in result["ready"]] == [7]
