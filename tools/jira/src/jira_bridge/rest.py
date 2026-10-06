# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Read-only Jira REST v2 client, stdlib only — the Python counterpart of bridge.groovy's reads.

It keeps the bridge's conventions: Jira Data Center REST API v2, a token in
`JIRA_API_TOKEN` sent as `Authorization: <JIRA_AUTH_SCHEME> <token>` (`Basic` by default,
`Bearer` for ASF personal access tokens), and anonymous reads when there is no token.
A token may also live in `~/.config/apache-magpie/jira-token` — under `$HOME`, never in the
project tree.  It only ever sends GET requests.

Consumers: the `jira` backend of tools/contributor-metrics (contributor-activity reads of
`contract:tracker`).
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

URL_RE = re.compile(r"^https?://[^\s\"'<>]+$")
PAGE_SIZE = 100
MAX_TRIES = 6
RETRYABLE_STATUS = {429, 502, 503, 504}
TOKEN_FILE = Path.home() / ".config" / "apache-magpie" / "jira-token"

Opener = Callable[[urllib.request.Request], Any]


class JiraRestError(RuntimeError):
    """A request failed: an HTTP error, or an unreachable host after retries."""


class JiraRestConfigError(ValueError):
    """The base URL or the auth scheme is not usable."""


def default_token() -> str:
    """`JIRA_API_TOKEN`, else the token file under `$HOME`, else "" (anonymous)."""
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not token and TOKEN_FILE.is_file():
        token = TOKEN_FILE.read_text().strip()
    return token


def _urlopen(req: urllib.request.Request) -> Any:
    return urllib.request.urlopen(req, timeout=60)


class JiraRest:
    """GET-only access to one Jira instance."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        auth_scheme: str | None = None,
        opener: Opener | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        if not URL_RE.match(self.url):
            raise JiraRestConfigError(f"Jira URL must be http(s)://…, got {self.url!r}")
        self.token = default_token() if token is None else token
        self.auth_scheme = auth_scheme or os.environ.get("JIRA_AUTH_SCHEME", "Basic")
        if self.auth_scheme not in ("Basic", "Bearer"):
            raise JiraRestConfigError(
                f"JIRA_AUTH_SCHEME must be Basic or Bearer, got {self.auth_scheme!r}"
            )
        self.opener: Opener = opener or _urlopen
        self.sleep: Callable[[float], None] = sleep or time.sleep

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        """One GET, retrying rate limits and transient failures with exponential backoff."""
        req = urllib.request.Request(
            f"{self.url}{path}?{urllib.parse.urlencode(params)}",
            headers={"Accept": "application/json"},
        )
        if self.token:
            req.add_header("Authorization", f"{self.auth_scheme} {self.token}")
        delay = 2.0
        for attempt in range(MAX_TRIES):
            last = attempt == MAX_TRIES - 1
            try:
                with self.opener(req) as resp:
                    data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                    return data
            except urllib.error.HTTPError as exc:
                if exc.code not in RETRYABLE_STATUS or last:
                    raise JiraRestError(
                        f"HTTP {exc.code} from {path}: {exc.reason}"
                    ) from exc
            except urllib.error.URLError as exc:
                if last:
                    raise JiraRestError(
                        f"cannot reach {self.url}: {exc.reason}"
                    ) from exc
            self.sleep(delay)
            delay = min(delay * 2, 120.0)
        raise JiraRestError("Jira failed after retries")  # pragma: no cover

    def search(
        self, jql: str, *, fields: str, pages: int, expand: str = ""
    ) -> tuple[list[dict[str, Any]], int]:
        """Up to `pages` pages of 100 issues for `jql`, and the total Jira reports."""
        issues: list[dict[str, Any]] = []
        total = 0
        for page in range(pages):
            params: dict[str, str | int] = {
                "jql": jql,
                "startAt": page * PAGE_SIZE,
                "maxResults": PAGE_SIZE,
                "fields": fields,
            }
            if expand:
                params["expand"] = expand
            data = self.get("/rest/api/2/search", params)
            total = int(data.get("total", 0))
            batch = data.get("issues") or []
            issues += batch
            if not batch or len(issues) >= total:
                break
        return issues, total
