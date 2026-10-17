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

"""End-to-end JSON-sidecar parity between reference.py and dashboard.py.

PR #348 review asked for a golden-file guard on the "preserved bit-for-bit"
claim. This runs BOTH scripts' main() over the same in-memory fixture (gh
calls stubbed) and asserts dashboard's sidecar is a superset of reference's
with identical values on every shared key. `fetched_at` is excluded — it is a
wall-clock stamp, not a computed quantity.
"""

from __future__ import annotations

import json

import pytest

from pr_management.stats import dashboard, reference

from .helpers import comment, make_pr

QC = reference.DEFAULT_TRIAGE_MARKER
READY = reference.DEFAULT_READY_LABEL

# Shared key whose value is a timestamp, not a computed quantity.
_VOLATILE = {"fetched_at"}


def _open_fixture():
    return [
        make_pr(1, author="alice", assoc="NONE", created_days_ago=40),
        make_pr(2, author="bob", assoc="NONE", labels=[READY]),
        make_pr(3, author="maint", assoc="MEMBER"),
        make_pr(4, author="carol", assoc="NONE", is_draft=True),
        make_pr(
            5,
            author="dave",
            assoc="NONE",
            comments=[comment(f"{QC}", author="maint", assoc="MEMBER")],
        ),
    ]


def _closed_fixture():
    return [
        make_pr(
            20, assoc="NONE", created_days_ago=20, closed_days_ago=3, merged=True, include_engagement=False
        ),
        make_pr(
            21, assoc="NONE", created_days_ago=18, closed_days_ago=2, merged=False, include_engagement=False
        ),
    ]


def _install_stubs(monkeypatch, module):
    """Stub a module's fetch primitives to serve the in-memory fixture."""

    def fake_paginated_search(query, search_q, *args, status=None, **kwargs):
        if status is not None:
            status.setdefault("partial", False)
        if "is:open" in search_q:
            return [dict(pr) for pr in _open_fixture()]
        return [dict(pr) for pr in _closed_fixture()]

    monkeypatch.setattr(module, "paginated_search", fake_paginated_search)
    monkeypatch.setattr(module, "fetch_codeowners", lambda repo: "")
    monkeypatch.setattr(module, "fetch_ready_pr_files", lambda repo, nums: {})
    if module is dashboard:
        # dashboard.main() ends by publishing to a secret gist through `gh`.
        # A unit test must never reach GitHub, so fail loudly if it gets there.
        def refuse_publish(*args, **kwargs):
            pytest.fail("unit test reached the dashboard gist publish step")

        # Guard each entry point independently of main()'s current call order.
        monkeypatch.setattr(module, "gist_scope_available", refuse_publish)
        monkeypatch.setattr(module, "publish_gist", refuse_publish)
        monkeypatch.setattr(module, "read_stats_gist_id", refuse_publish)
        monkeypatch.setattr(module, "store_stats_gist_id", refuse_publish)


def _run(monkeypatch, module, out_path):
    _install_stubs(monkeypatch, module)
    argv = [
        "prog",
        "--repo",
        "apache/airflow",
        "--viewer",
        "tester",
        "--since",
        "2026-04-01",
        "--out",
        str(out_path),
    ]
    if module is dashboard:
        argv.append("--no-publish")  # reference.py has no publish step and no such flag
    monkeypatch.setattr(module.sys, "argv", argv)
    module.main()
    return json.loads(out_path.with_suffix(".json").read_text())


def test_dashboard_sidecar_is_superset_of_reference(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        ref = _run(m, reference, tmp_path / "ref.html")
    with monkeypatch.context() as m:
        dash = _run(m, dashboard, tmp_path / "dash.html")

    shared = set(ref) - _VOLATILE
    # Superset: every reference key survives in the dashboard sidecar.
    missing = shared - set(dash)
    assert not missing, f"dashboard dropped reference keys: {missing}"

    # Identical values on every shared, non-volatile key.
    for key in sorted(shared):
        assert dash[key] == ref[key], f"value drift on {key!r}: {dash[key]!r} != {ref[key]!r}"

    # And the dashboard genuinely extends the contract.
    assert set(dash) - set(ref), "dashboard should add keys beyond reference"
    assert "partial" in dash


def test_known_counts_for_fixture(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        dash = _run(m, dashboard, tmp_path / "dash.html")

    assert dash["open_count"] == 5
    assert dash["closed_count"] == 2
    assert dash["ready_count"] == 1
    assert dash["untriaged_count"] == 1
    assert dash["partial"] is False
