# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Jira REST v2 operations for the security tracker, over the shared `JiraRest` client.

Every request goes through `jira_bridge.rest.JiraRest.send`, so the security tracker
inherits its rules unchanged: https only, the token bound to a host the user confirmed
(`JIRA_API_HOST` or the token file), `Authorization` only to that host, redirects
refused, and writes refused outright when the token was withheld.  Tests replace the
network with a `Transport`; production never takes that path.
"""

from __future__ import annotations

import json
import secrets
import urllib.parse
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, NamedTuple

from jira_bridge.rest import JiraRest, JiraRestError

EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_REFUSED = 4
EXIT_BACKEND = 5


class TrackerError(Exception):
    """An error carrying the contract exit code."""

    exit_code = EXIT_BACKEND


class UsageError(TrackerError):
    exit_code = EXIT_USAGE


class NotFoundError(TrackerError):
    exit_code = EXIT_NOT_FOUND


class RefusedError(TrackerError):
    exit_code = EXIT_REFUSED


class BackendError(TrackerError):
    """An HTTP or network failure; ``status`` is the HTTP status when there was one."""

    exit_code = EXIT_BACKEND

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class Response(NamedTuple):
    status: int
    body: bytes


# (method, url, headers, body) -> Response.  Tests only; production uses JiraRest.send.
Transport = Callable[[str, str, Mapping[str, str], bytes | None], Response]


def _error_text(body: bytes) -> str:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    parts = [str(m) for m in data.get("errorMessages") or []]
    errors = data.get("errors") or {}
    if isinstance(errors, dict):
        parts.extend(f"{k}: {v}" for k, v in errors.items())
    return "; ".join(parts)


@dataclass
class JiraClient:
    """Jira REST v2 access for one project."""

    base_url: str
    project: str
    cloud: bool = False
    #: The shared client every production request goes through.
    rest: JiraRest | None = None
    #: Tests only: a fake network in place of `rest`.
    transport: Transport | None = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.rest is None and self.transport is None:
            raise ValueError("JiraClient needs a JiraRest (or, in tests, a transport)")

    # -- plumbing ------------------------------------------------------

    def _send(
        self,
        method: str,
        path: str,
        params: Mapping[str, str | int] | None,
        body: bytes | None,
        headers: Mapping[str, str] | None,
    ) -> Response:
        if self.transport is not None:
            url = self.base_url + path
            if params:
                url += "?" + urllib.parse.urlencode(
                    {k: str(v) for k, v in params.items()}
                )
            return self.transport(
                method, url, {"Accept": "application/json", **(headers or {})}, body
            )
        assert self.rest is not None
        try:
            status, data = self.rest.send(
                method,
                path,
                params={k: str(v) for k, v in params.items()} if params else None,
                body=body,
                headers=dict(headers or {}),
            )
        except JiraRestError as exc:
            message = str(exc)
            if (
                message.startswith("refusing ")
                and "writes need a Jira token" in message
            ):
                raise RefusedError(message) from exc
            raise BackendError(message) from exc
        return Response(status, data)

    def raw(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        resp = self._send(method, path, params, body, headers)
        if resp.status == 404:
            raise NotFoundError(f"not found: {method} {path}")
        if resp.status >= 400:
            detail = _error_text(resp.body)
            suffix = f": {detail}" if detail else ""
            raise BackendError(
                f"Jira returned HTTP {resp.status} for {method} {path}{suffix}",
                resp.status,
            )
        if not resp.body.strip():
            return None
        try:
            return json.loads(resp.body)
        except ValueError as exc:
            raise BackendError(
                f"Jira returned a non-JSON response for {method} {path}"
            ) from exc

    def call(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int] | None = None,
        payload: Any = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if body is not None else None
        return self.raw(method, path, params=params, body=body, headers=headers)

    # -- urls ----------------------------------------------------------

    def browse_url(self, key: str) -> str:
        return f"{self.base_url}/browse/{key}"

    def comment_url(self, key: str, comment_id: str) -> str:
        return (
            f"{self.browse_url(key)}?focusedCommentId={comment_id}#comment-{comment_id}"
        )

    # -- operations ----------------------------------------------------

    def issue(self, key: str, fields: str) -> dict[str, Any]:
        data = self.call("GET", f"/rest/api/2/issue/{key}", params={"fields": fields})
        if not isinstance(data, dict):
            raise BackendError(f"unexpected response for issue {key}")
        return data

    def search(self, jql: str, fields: str, limit: int) -> Iterator[dict[str, Any]]:
        """Yield up to ``limit`` issues matching ``jql``, paginating.

        Server / Data Center paginate ``/search`` by ``startAt``; Cloud has
        retired that endpoint in favour of ``/search/jql`` with a token.
        """
        page = min(limit, 100)
        returned = 0
        start_at = 0
        token: str | None = None
        while returned < limit:
            params: dict[str, str | int] = {
                "jql": jql,
                "fields": fields,
                "maxResults": page,
            }
            if self.cloud:
                if token:
                    params["nextPageToken"] = token
                data = self.call("GET", "/rest/api/2/search/jql", params=params)
            else:
                params["startAt"] = start_at
                data = self.call("GET", "/rest/api/2/search", params=params)
            issues = (data or {}).get("issues") or []
            for issue in issues:
                if returned >= limit:
                    return
                returned += 1
                yield issue
            if not issues:
                return
            if self.cloud:
                token = data.get("nextPageToken")
                if not token or data.get("isLast"):
                    return
            else:
                start_at += len(issues)
                total = data.get("total")
                if isinstance(total, int) and start_at >= total:
                    return

    def comments(self, key: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        start_at = 0
        while True:
            data = self.call(
                "GET",
                f"/rest/api/2/issue/{key}/comment",
                params={"startAt": start_at, "maxResults": 100},
            )
            batch = (data or {}).get("comments") or []
            result.extend(batch)
            start_at += len(batch)
            total = (data or {}).get("total")
            if not batch or not isinstance(total, int) or start_at >= total:
                return result

    def myself(self) -> dict[str, Any]:
        data = self.call("GET", "/rest/api/2/myself")
        return data if isinstance(data, dict) else {}

    def attach(self, key: str, name: str, content: bytes) -> Any:
        boundary = "magpie-" + secrets.token_hex(16)
        safe_name = name.replace('"', "_").replace("\r", "_").replace("\n", "_")
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
            + content
            + f"\r\n--{boundary}--\r\n".encode()
        )
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Atlassian-Token": "no-check",
        }
        return self.raw(
            "POST", f"/rest/api/2/issue/{key}/attachments", body=body, headers=headers
        )
