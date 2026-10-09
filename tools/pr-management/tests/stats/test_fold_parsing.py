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

"""The fold block lives in the PR body, which the PR author controls.

A hand-written or malformed ``pr-triage-fold`` marker must degrade to "no
fold event" -- never crash the dashboard run (ValueError on an unparsable
``triaged=`` value, TypeError downstream on a timezone-naive one).
"""

from __future__ import annotations

from pr_management.stats import reference

from .helpers import make_ctx


def _body_with(triaged):
    return {"body": f"<!-- pr-triage-fold: triaged={triaged} head=abc1234 action=draft -->"}


def test_garbage_triaged_value_returns_none():
    assert reference.fold_triaged_at(_body_with("soon")) is None


def test_impossible_date_returns_none():
    assert reference.fold_triaged_at(_body_with("2026-13-99T99:99:99Z")) is None


def test_timezone_naive_triaged_value_returns_none():
    assert reference.fold_triaged_at(_body_with("2026-06-11T14:22:00")) is None


def test_missing_body_returns_none():
    assert reference.fold_triaged_at({"body": ""}) is None
    assert reference.fold_triaged_at({}) is None


def test_valid_fold_still_parses():
    at = reference.fold_triaged_at(_body_with("2026-06-11T14:22:00Z"))
    assert at is not None
    assert at.tzinfo is not None


def test_malformed_marker_does_not_hide_a_later_valid_fold():
    pr = {"body": "<!-- pr-triage-fold: triaged=oops -->\n" + _body_with("2026-06-11T14:22:00Z")["body"]}
    at = reference.fold_triaged_at(pr)
    assert at is not None
    assert at.isoformat() == "2026-06-11T14:22:00+00:00"


def test_marker_events_survive_malformed_fold():
    """The dashboard entry point must not raise on author-controlled bodies."""
    events = reference.triage_marker_events(_body_with("oops"), make_ctx())
    assert events == []
