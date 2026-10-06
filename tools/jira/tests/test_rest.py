# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""jira_bridge.rest: the read-only REST client, against recorded responses. No network."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message

import pytest

from jira_bridge.rest import JiraRest, JiraRestConfigError, JiraRestError

BASE = "https://issues.example.org/jira"


def recorder(pages):
    seen: list[urllib.request.Request] = []

    def opener(req):
        seen.append(req)
        start = int(
            urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)["startAt"][
                0
            ]
        )
        return io.BytesIO(json.dumps(pages[start // 100]).encode())

    return opener, seen


def test_search_pages_until_the_total_and_sends_only_gets():
    pages = [
        {"total": 150, "issues": [{"key": f"FOO-{n}"} for n in range(100)]},
        {"total": 150, "issues": [{"key": f"FOO-{n}"} for n in range(100, 150)]},
    ]
    opener, seen = recorder(pages)
    rest = JiraRest(BASE, token="", opener=opener, sleep=lambda s: None)
    issues, total = rest.search('project = "FOO"', fields="created", pages=5)
    assert (len(issues), total, len(seen)) == (150, 150, 2)
    assert {r.get_method() for r in seen} == {"GET"}
    assert all(r.get_header("Authorization") is None for r in seen)


def test_search_stops_at_the_page_budget():
    pages = [{"total": 1000, "issues": [{"key": "FOO-1"}] * 100}] * 3
    opener, seen = recorder(pages)
    issues, total = JiraRest(BASE, token="", opener=opener).search(
        "x", fields="created", pages=2
    )
    assert (len(issues), total, len(seen)) == (200, 1000, 2)


def test_token_and_scheme_follow_the_bridge_conventions(monkeypatch):
    monkeypatch.setenv("JIRA_API_TOKEN", "pat")
    monkeypatch.setenv("JIRA_AUTH_SCHEME", "Bearer")
    opener, seen = recorder([{"total": 0, "issues": []}])
    JiraRest(BASE, opener=opener).search("x", fields="created", pages=1)
    assert seen[0].get_header("Authorization") == "Bearer pat"


def test_transient_errors_are_retried_and_others_raise():
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError(BASE, 503, "unavailable", Message(), None)
        return io.BytesIO(b'{"ok": true}')

    assert JiraRest(BASE, token="", opener=flaky, sleep=sleeps.append).get(
        "/x", {}
    ) == {"ok": True}
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]

    def denied(req):
        raise urllib.error.HTTPError(BASE, 401, "Unauthorized", Message(), None)

    with pytest.raises(JiraRestError):
        JiraRest(BASE, token="", opener=denied, sleep=sleeps.append).get("/x", {})


def test_bad_configuration_is_rejected():
    with pytest.raises(JiraRestConfigError):
        JiraRest("ftp://nope", token="")
    with pytest.raises(JiraRestConfigError):
        JiraRest(BASE, token="", auth_scheme="Digest")
