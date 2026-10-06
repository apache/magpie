# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Read-only Jira REST v2 client, stdlib only — the Python counterpart of bridge.groovy's reads.

It keeps the bridge's conventions: Jira Data Center REST API v2, a token in
`JIRA_API_TOKEN` sent as `Authorization: <JIRA_AUTH_SCHEME> <token>` (`Basic` by default,
`Bearer` for ASF personal access tokens), and anonymous reads when there is no token.
It only ever sends GET requests.

**The token is the user's personal credential; the URL is not theirs to vouch for.**
The Jira URL comes from project configuration, which can be committed by anyone with
write access, so a changed URL must never silently receive the token.  Four rules:

1. The URL must be `https://`; `http://` is accepted only for loopback hosts
   (`localhost`, `127.0.0.1`, `::1`), for tests and local instances.
2. The token is bound to a host the user confirmed: `JIRA_API_HOST`, or a `host=` line in
   the token file `~/.config/apache-magpie/jira-token` (which then holds `token=` and
   `host=` lines; a file with only the token is read as an unconfirmed token).  When the
   configured URL's host is not the confirmed one, or none is confirmed, the token is
   withheld, reads go out anonymously, and `auth_note` says why.
3. `Authorization` is attached only to a request whose host equals the configured host.
4. Redirects are refused, so the token never follows one; the error names the target.

The token never appears in an error message or an exception.

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
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PAGE_SIZE = 100
MAX_TRIES = 6
RETRYABLE_STATUS = {429, 502, 503, 504}
TOKEN_FILE = Path.home() / ".config" / "apache-magpie" / "jira-token"

Opener = Callable[[urllib.request.Request], Any]


class JiraRestError(RuntimeError):
    """A request failed: an HTTP error, or an unreachable host after retries."""


class JiraRestConfigError(ValueError):
    """The base URL or the auth scheme is not usable."""


def _read_token_file() -> tuple[str, str]:
    """(token, host) from the token file: `token=` / `host=` lines, or a bare token (no host)."""
    if not TOKEN_FILE.is_file():
        return "", ""
    lines = [ln.strip() for ln in TOKEN_FILE.read_text().splitlines() if ln.strip()]
    fields = dict(
        ln.split("=", 1) for ln in lines if ln.startswith(("token=", "host="))
    )
    if fields:
        return fields.get("token", "").strip(), fields.get("host", "").strip().lower()
    return (lines[0] if lines else ""), ""


def default_credentials() -> tuple[str, str]:
    """(token, confirmed host): the environment first, then the token file; "" when unset."""
    file_token, file_host = _read_token_file()
    token = os.environ.get("JIRA_API_TOKEN", "").strip() or file_token
    host = os.environ.get("JIRA_API_HOST", "").strip().lower() or file_host
    return token, host


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise JiraRestError(
            f"refusing HTTP {code} redirect to {newurl}; check the configured Jira URL"
        )


_OPENER = urllib.request.build_opener(_RefuseRedirects())


def _urlopen(req: urllib.request.Request) -> Any:
    return _OPENER.open(req, timeout=60)


class JiraRest:
    """GET-only access to one Jira instance."""

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        token_host: str | None = None,
        auth_scheme: str | None = None,
        opener: Opener | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        if not URL_RE.match(self.url):
            raise JiraRestConfigError(f"Jira URL must be https://…, got {self.url!r}")
        parts = urllib.parse.urlsplit(self.url)
        self.host = (parts.hostname or "").lower()
        self.netloc = parts.netloc.lower()
        if parts.scheme != "https" and self.host not in LOOPBACK_HOSTS:
            raise JiraRestConfigError(
                f"Jira URL must be https:// (http:// only for localhost), got {self.url!r}"
            )
        env_token, env_host = default_credentials()
        token = env_token if token is None else token
        confirmed = (env_host if token_host is None else token_host).strip().lower()
        self.auth_note = ""
        if token and confirmed != self.host:
            self.auth_note = (
                f"the Jira token is confirmed for {confirmed!r}, not {self.host!r}; reading anonymously"
                if confirmed
                else f"the Jira token has no confirmed host (set JIRA_API_HOST or a host= line in "
                f"{TOKEN_FILE}); not sending it to {self.host!r}, reading anonymously"
            )
            token = ""
        self._token = token
        self.auth_scheme = auth_scheme or os.environ.get("JIRA_AUTH_SCHEME", "Basic")
        if self.auth_scheme not in ("Basic", "Bearer"):
            raise JiraRestConfigError(
                f"JIRA_AUTH_SCHEME must be Basic or Bearer, got {self.auth_scheme!r}"
            )
        self.opener: Opener = opener or _urlopen
        self.sleep: Callable[[float], None] = sleep or time.sleep

    def __repr__(self) -> str:
        return f"JiraRest(url={self.url!r}, authenticated={bool(self._token)})"

    @property
    def authenticated(self) -> bool:
        return bool(self._token)

    def get(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        """One GET, retrying rate limits and transient failures with exponential backoff."""
        req = urllib.request.Request(
            f"{self.url}{path}?{urllib.parse.urlencode(params)}",
            headers={"Accept": "application/json"},
        )
        if (
            self._token
            and urllib.parse.urlsplit(req.full_url).netloc.lower() == self.netloc
        ):
            req.add_header("Authorization", f"{self.auth_scheme} {self._token}")
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
