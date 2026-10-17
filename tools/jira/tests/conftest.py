# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""A fake Jira transport that records requests and replays canned responses."""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest
from jira_bridge.security_tracker import main
from jira_bridge.tracker_client import Response

BASE = "https://jira.example.org"


@dataclass
class Call:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes | None

    @property
    def path(self) -> str:
        return urllib.parse.urlsplit(self.url).path

    @property
    def query(self) -> dict[str, str]:
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.url).query))

    def json(self) -> Any:
        assert self.body is not None
        return json.loads(self.body)


Handler = Callable[[Call], tuple[int, Any]]


@dataclass
class FakeJira:
    routes: dict[tuple[str, str], list[Any]] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    def on(self, method: str, path: str, *responses: Any) -> FakeJira:
        """Queue responses: (status, json) tuples or handler callables; the last one repeats."""
        self.routes.setdefault((method, path), []).extend(responses)
        return self

    def __call__(
        self, method: str, url: str, headers: Mapping[str, str], body: bytes | None
    ) -> Response:
        call = Call(method, url, dict(headers), body)
        self.calls.append(call)
        queue = self.routes.get((method, call.path))
        if not queue:
            return Response(404, b'{"errorMessages": ["no route"]}')
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        status, payload = item(call) if callable(item) else item
        data = b"" if payload is None else json.dumps(payload).encode()
        return Response(status, data)

    def writes(self) -> list[Call]:
        return [c for c in self.calls if c.method != "GET"]


ENV = {
    "ISSUE_TRACKER_URL": BASE,
    "SECURITY_TRACKER_PROJECT": "FOOSEC",
    "JIRA_API_TOKEN": "secret-token",
    "JIRA_AUTH_SCHEME": "Bearer",
    "SECURITY_TRACKER_SECURITY_LEVEL": "Security Team",
}


def issue(
    key: str = "FOOSEC-12", *, secure: bool = True, **fields: Any
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "Path traversal",
        "status": {"name": "Open", "statusCategory": {"key": "new"}},
        "resolution": None,
        "labels": ["needs-triage"],
        "assignee": None,
        "fixVersions": [],
        "reporter": {"name": "alice", "displayName": "Alice"},
        "created": "2026-10-01T10:00:00.000+0000",
        "updated": "2026-10-02T10:00:00.000+0000",
        "description": "",
        "security": {"id": "10001", "name": "Security Team"} if secure else None,
    }
    base.update(fields)
    return {"key": key, "fields": base}


@dataclass
class Result:
    code: int
    out: str
    err: str

    def json(self) -> Any:
        return json.loads(self.out)


@pytest.fixture
def fake() -> FakeJira:
    return FakeJira()


@pytest.fixture
def run(fake: FakeJira, capsys: pytest.CaptureFixture[str]) -> Callable[..., Result]:
    def _run(*argv: str, env: Mapping[str, str] | None = None) -> Result:
        code = main(list(argv), transport=fake, env=ENV if env is None else env)
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return _run
