# SPDX-License-Identifier: Apache-2.0
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

"""Fetch a PMC's cases from the dashboard's read API.

The dashboard authenticates with the ASF OAuth session cookie only.  The
cookie is a credential: it lives under the user's home directory, never in
the project tree, and is sent to the dashboard's own origin and nowhere else.
Only GET is ever sent, and redirects are not followed, since the one the
dashboard issues to an API caller is to the login page.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "https://dash.security.apache.org"
DEFAULT_SESSION_FILE = "~/.config/apache-magpie/asf-security-dash/session.json"
SESSION_ENV = "ASF_SECURITY_DASH_SESSION"
TIMEOUT_SECONDS = 30
_PMC = re.compile(r"[a-z0-9]+")


class DashError(Exception):
    """Raised when the bridge cannot complete a request."""


class SessionExpired(DashError):
    """The session cookie is missing, rejected, or has expired."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> urllib.request.Request | None:
        return None


def check_pmc(pmc: str) -> str:
    """The PMC id as the dashboard spells it, or `DashError`."""
    if not _PMC.fullmatch(pmc):
        raise DashError(f"not a PMC id: {pmc!r} (lower-case letters and digits)")
    return pmc


def project_url(pmc: str) -> str:
    """The project page, where a PMC member triages a case."""
    return f"{BASE_URL}/project/{check_pmc(pmc)}"


def session_file() -> Path:
    return Path(os.environ.get(SESSION_ENV) or DEFAULT_SESSION_FILE).expanduser()


def load_cookie(path: Path | None = None) -> str:
    """The `Cookie` header value stored in the session file."""
    path = path or session_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SessionExpired(
            f"no dashboard session at {path}: sign in at {BASE_URL} and save the session cookie there"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise DashError(f"cannot read the dashboard session at {path}: {exc}") from exc
    cookie = data.get("cookie") if isinstance(data, dict) else None
    if not isinstance(cookie, str) or not cookie.strip() or "\n" in cookie or "\r" in cookie:
        raise DashError(f'{path} must hold {{"cookie": "<name>=<value>"}}')
    return cookie.strip()


def _open(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout)


def fetch_reports(pmc: str, cookie: str) -> list[dict[str, Any]]:
    """The raw case list of `GET /api/project/<pmc>/reports`."""
    url = f"{BASE_URL}/api/project/{check_pmc(pmc)}/reports"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "Cookie": cookie}, method="GET"
    )
    try:
        with _open(request, TIMEOUT_SECONDS) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (301, 302, 303, 307, 308, 401):
            raise SessionExpired(f"the dashboard session was refused: sign in again at {BASE_URL}") from exc
        if exc.code == 403:
            raise DashError(
                f"not authorized for {pmc}: the dashboard shows a PMC to its members only"
            ) from exc
        raise DashError(f"GET {url} returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DashError(f"cannot reach {BASE_URL}: {exc.reason}") from exc
    return parse_reports(body)


def parse_reports(body: bytes | str) -> list[dict[str, Any]]:
    """The case list, validated as the JSON array the reports API returns."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SessionExpired(
            f"the dashboard answered with something other than JSON, usually its login page: sign in again at {BASE_URL}"
        ) from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise DashError("the reports API did not return a list of cases")
    return data
