# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""jira_bridge.rest: the read-only REST client, against recorded responses. No network."""

from __future__ import annotations

import io
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from jira_bridge import rest as rest_mod
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
    monkeypatch.setenv("JIRA_API_HOST", "issues.example.org")
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


@pytest.fixture(autouse=True)
def no_ambient_credentials(monkeypatch, tmp_path):
    for var in ("JIRA_API_TOKEN", "JIRA_API_HOST", "JIRA_AUTH_SCHEME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(rest_mod, "TOKEN_FILE", tmp_path / "jira-token")


def test_plain_http_is_refused_except_on_loopback():
    for url in (
        "http://issues.example.org/jira",
        "http://10.0.0.5/jira",
        "http://localhost.evil.org",
    ):
        with pytest.raises(JiraRestConfigError):
            JiraRest(url, token="")
    for url in (
        "http://localhost:8080/jira",
        "http://127.0.0.1:9",
        "http://[::1]:8080",
    ):
        assert JiraRest(url, token="").host in rest_mod.LOOPBACK_HOSTS


def test_token_is_withheld_without_a_confirmed_host():
    opener, seen = recorder([{"total": 0, "issues": []}])
    rest = JiraRest(BASE, token="pat", opener=opener)
    rest.search("x", fields="created", pages=1)
    assert seen[0].get_header("Authorization") is None
    assert not rest.authenticated and "no confirmed host" in rest.auth_note
    assert "pat" not in rest.auth_note and "pat" not in repr(rest)


def test_token_is_withheld_when_committed_config_points_elsewhere(
    tmp_path, monkeypatch
):
    (tmp_path / "jira-token").write_text("token=pat\nhost=issues.example.org\n")
    opener, seen = recorder([{"total": 0, "issues": []}])
    rest = JiraRest("https://jira.attacker.example/jira", opener=opener)
    rest.search("x", fields="created", pages=1)
    assert seen[0].get_header("Authorization") is None
    assert "confirmed for 'issues.example.org'" in rest.auth_note
    # The same file authorises the host it names.
    opener2, seen2 = recorder([{"total": 0, "issues": []}])
    JiraRest(BASE, opener=opener2).search("x", fields="created", pages=1)
    assert seen2[0].get_header("Authorization") == "Basic pat"


def test_token_is_never_attached_to_another_host():
    sent = []

    def opener(req):
        sent.append(req.get_header("Authorization"))
        return io.BytesIO(b"{}")

    rest = JiraRest(BASE, token="pat", token_host="issues.example.org", opener=opener)
    rest.url = "https://jira.attacker.example"  # a request built for any other host
    rest.get("/x", {})
    assert sent == [None]


def test_errors_never_carry_the_token():
    def denied(req):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", Message(), None)

    rest = JiraRest(
        BASE, token="sekrit-pat", token_host="issues.example.org", opener=denied
    )
    with pytest.raises(JiraRestError) as info:
        rest.get("/x", {})
    assert "sekrit-pat" not in str(info.value)


def test_a_redirect_never_forwards_the_token():
    seen: dict[str, list] = {"origin": [], "target": []}

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["target"].append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):
            pass

    target = HTTPServer(("127.0.0.1", 0), Target)

    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["origin"].append(self.headers.get("Authorization"))
            self.send_response(302)
            self.send_header(
                "Location", f"http://127.0.0.1:{target.server_port}/stolen"
            )
            self.end_headers()

        def log_message(self, *a):
            pass

    origin = HTTPServer(("127.0.0.1", 0), Origin)
    for srv in (origin, target):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        rest = JiraRest(
            f"http://127.0.0.1:{origin.server_port}",
            token="pat",
            token_host="127.0.0.1",
            sleep=lambda s: None,
        )
        with pytest.raises(JiraRestError) as info:
            rest.get("/rest/api/2/search", {})
        assert "redirect" in str(info.value) and "pat" not in str(info.value)
        assert seen["origin"] == ["Basic pat"]
        assert seen["target"] == []
    finally:
        origin.shutdown()
        target.shutdown()


# -- send(): the write path the security tracker uses ----------------------------


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture():
    seen: list[urllib.request.Request] = []

    def opener(req):
        seen.append(req)
        return _Resp(b'{"key": "FOOSEC-1"}')

    return opener, seen


def test_send_writes_with_a_token_confirmed_for_the_host():
    opener, seen = _capture()
    rest = JiraRest(
        BASE,
        token="pat",
        token_host="issues.example.org",
        auth_scheme="Bearer",
        opener=opener,
    )
    status, body = rest.send(
        "POST",
        "/rest/api/2/issue",
        body=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert (status, json.loads(body)) == (200, {"key": "FOOSEC-1"})
    assert seen[0].get_method() == "POST"
    assert seen[0].get_header("Authorization") == "Bearer pat"


@pytest.mark.parametrize("host", ["", "evil.example.org"])
def test_send_refuses_a_write_when_the_token_was_withheld(host):
    opener, seen = _capture()
    rest = JiraRest(BASE, token="pat", token_host=host, opener=opener)
    with pytest.raises(JiraRestError, match="writes need a Jira token confirmed"):
        rest.send("PUT", "/rest/api/2/issue/FOOSEC-1", body=b"{}")
    assert seen == []
    # Reads still go out, anonymously.
    rest.send("GET", "/rest/api/2/issue/FOOSEC-1")
    assert seen[0].get_header("Authorization") is None


def test_send_returns_http_errors_and_sends_a_write_once():
    calls = {"n": 0}

    def failing(req):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            BASE, 503, "unavailable", Message(), io.BytesIO(b'{"errorMessages": ["x"]}')
        )

    rest = JiraRest(
        BASE,
        token="pat",
        token_host="issues.example.org",
        opener=failing,
        sleep=lambda s: None,
    )
    status, body = rest.send("POST", "/rest/api/2/issue", body=b"{}")
    assert status == 503 and calls["n"] == 1
    assert b"errorMessages" in body


def test_basic_with_user_encodes_a_raw_token():
    opener, seen = _capture()
    rest = JiraRest(
        BASE, token="raw", token_host="issues.example.org", user="bob", opener=opener
    )
    rest.send("GET", "/rest/api/2/myself")
    import base64

    assert (
        seen[0].get_header("Authorization")
        == "Basic " + base64.b64encode(b"bob:raw").decode()
    )
