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

"""Guards the field coupling between the fetch scripts.

`fetch_events.py` will not trust a cached events file that is older than the
issue's last update. That guard reads `updatedAt` out of `issues.json`, which
`fetch_issues.py` is responsible for putting there. If the field goes missing
from the `--json` list, nothing raises: the lookup yields `None`, the guard
takes its "no timestamp, trust the cache" branch, and every issue relabelled
after its first fetch keeps stale event history for good. The dashboard then
reports lifecycle bands that silently disagree with the tracker.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

TOOL_DIR = pathlib.Path(__file__).resolve().parents[1]


def _json_fields(script: pathlib.Path) -> set[str]:
    """Return the `gh --json` field names requested by a fetch script."""
    src = script.read_text()
    match = re.search(r'"--json",\s*\n\s*(?:#[^\n]*\n\s*)*"([^"]+)"', src)
    assert match, f"no --json field list found in {script.name}"
    return {field.strip() for field in match.group(1).split(",")}


def test_fetch_events_guard_depends_on_updated_at():
    """The staleness guard is written in terms of the issue's updatedAt."""
    assert "updatedAt" in (TOOL_DIR / "fetch_events.py").read_text()


def test_fetch_issues_requests_updated_at():
    """So fetch_issues.py must actually request it, or the guard never fires."""
    assert "updatedAt" in _json_fields(TOOL_DIR / "fetch_issues.py")


def test_fetch_issues_requests_extra_fields():
    """fetch_bodies.py builds issue_extra.json from these list-call fields."""
    fields = _json_fields(TOOL_DIR / "fetch_issues.py")
    assert {"body", "closedByPullRequestsReferences"} <= fields


def _load_fetch_bodies():
    spec = importlib.util.spec_from_file_location("fetch_bodies", TOOL_DIR / "fetch_bodies.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_extra_takes_fields_from_list_call():
    """Issues carrying the list-call fields need no per-issue fetch, and fresh list data wins over cache."""
    fb = _load_fetch_bodies()
    refs = [{"number": 7, "repository": {"name": "airflow"}}]
    issues = [
        {"number": 1, "body": "new body", "closedByPullRequestsReferences": refs},
        {"number": 2, "body": "", "closedByPullRequestsReferences": []},
    ]
    cache = {"1": {"number": 1, "body": "stale body", "closedByPullRequestsReferences": []}}
    todo = fb.build_extra(issues, cache)
    assert todo == []
    assert cache["1"] == {"number": 1, "body": "new body", "closedByPullRequestsReferences": refs}
    assert cache["2"] == {"number": 2, "body": "", "closedByPullRequestsReferences": []}


def test_build_extra_falls_back_to_cache_then_per_issue_fetch():
    """An issues.json without the fields keeps the old resume-from-cache behaviour."""
    fb = _load_fetch_bodies()
    issues = [{"number": 1}, {"number": 2}]
    cached = {"number": 1, "body": "cached", "closedByPullRequestsReferences": []}
    cache = {"1": dict(cached)}
    todo = fb.build_extra(issues, cache)
    assert todo == [2]
    assert cache == {"1": cached}
