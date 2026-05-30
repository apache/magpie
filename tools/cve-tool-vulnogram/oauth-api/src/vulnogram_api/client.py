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
"""HTTP client for the Vulnogram session-cookie API.

The two operations the CLIs need:

- :func:`get_record` — read the JSON for a CVE record (no CSRF token
  required; the ``/cve5/json/<id>`` endpoint is the read view).
- :func:`update_record` — write the JSON for a CVE record. Requires
  scraping the per-page CSRF token from the rendered ``/cve5/<id>``
  page, then POSTing the JSON to the same URL with a ``CSRF-Token``
  header. Mirrors what Vulnogram's own browser client does (see
  ``Vulnogram/Vulnogram@src/js/edit/actions.js`` —
  ``fetch(postUrl, { method: 'POST', headers: { 'CSRF-Token': … } })``).

Both raise :class:`SessionExpired` when the response is a 302 to the
ASF-OAuth login page (the common cause: the session cookie has aged
out and the operator needs to re-run ``vulnogram-api-setup``).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from vulnogram_api.credentials import Session

# `var csrfToken = "…"` is rendered into every editable Vulnogram page
# via the inline JS block in `views/edit.pug`. We scrape it rather than
# parsing a meta tag because that is the form Vulnogram itself emits.
# Token characters: csurf base64url-encodes, so a generous character class
# without quote characters is enough.
_CSRF_RE = re.compile(r'var\s+csrfToken\s*=\s*"([^"]+)"')

DEFAULT_TIMEOUT_S = 30


class VulnogramAPIError(Exception):
    """Base class for Vulnogram API errors."""


class SessionExpired(VulnogramAPIError):
    """The session cookie has aged out; re-run ``vulnogram-api-setup``."""


class CSRFNotFound(VulnogramAPIError):
    """The CSRF token could not be scraped from the record page."""


class RecordSaveFailed(VulnogramAPIError):
    """Vulnogram returned an error envelope from the upsert endpoint."""


def _record_page_url(session: Session, cve_id: str, *, section: str) -> str:
    return f"https://{session.host}/{section}/{urllib.parse.quote(cve_id, safe='')}"


def _record_json_url(session: Session, cve_id: str, *, section: str) -> str:
    return f"https://{session.host}/{section}/json/{urllib.parse.quote(cve_id, safe='')}"


def _request(
    url: str,
    *,
    session: Session,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> tuple[int, dict[str, str], bytes]:
    """Issue a single HTTP request with the session cookie attached.

    Returns ``(status, headers, body_bytes)``. Raises
    :class:`SessionExpired` if the server redirects to the ASF-OAuth
    login flow (signal that the cookie has aged out).
    """
    full_headers: dict[str, str] = {"Cookie": session.cookie_header()}
    if headers:
        full_headers.update(headers)

    req = urllib.request.Request(url, data=body, method=method, headers=full_headers)
    # Don't follow redirects — we want to see the 302 to oauth.apache.org
    # so we can map it to SessionExpired.
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        # csurf rejects with 403 + EBADCSRFTOKEN; surface as-is so the
        # caller can decide whether to re-scrape and retry.
        return e.code, dict(e.headers or {}), e.read()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        # Returning None tells urllib to NOT follow the redirect; the
        # 3xx surfaces to our caller. We only redirect-stop on the
        # specific oauth.apache.org login bounce — let any other 3xx
        # propagate naturally (urllib raises HTTPError on unhandled
        # redirects when the handler returns None).
        return None


def _is_login_redirect(status: int, headers: dict[str, str]) -> bool:
    if status not in (301, 302, 303, 307, 308):
        return False
    location = headers.get("Location") or headers.get("location") or ""
    parsed = urllib.parse.urlparse(location)
    host = (parsed.hostname or "").lower()
    is_oauth_host = host == "oauth.apache.org" or host.endswith(".oauth.apache.org")
    is_login_path = (parsed.path or "").startswith("/users/login")
    return is_oauth_host or is_login_path


def get_record(
    session: Session,
    cve_id: str,
    *,
    section: str = "cve5",
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """Fetch a CVE record's stored JSON from ``/<section>/json/<id>``.

    The JSON endpoint returns a list (Vulnogram supports comma-
    separated IDs); we always pass a single ID and unwrap. An empty
    list means the record does not exist yet.
    """
    url = _record_json_url(session, cve_id, section=section)
    status, headers, body = _request(url, session=session, timeout=timeout)
    if _is_login_redirect(status, headers):
        raise SessionExpired(
            "Vulnogram redirected to ASF OAuth login — session cookie expired. Re-run `vulnogram-api-setup`."
        )
    if status != 200:
        raise VulnogramAPIError(f"GET {url} returned HTTP {status}: {body[:200].decode(errors='replace')}")
    docs = json.loads(body.decode("utf-8"))
    if not isinstance(docs, list):
        raise VulnogramAPIError(f"GET {url} did not return a list: {docs!r}")
    if not docs:
        raise VulnogramAPIError(f"Record {cve_id} not found at {url}.")
    first = docs[0]
    if not isinstance(first, dict):
        raise VulnogramAPIError(f"GET {url} returned non-dict element: {first!r}")
    return first


def fetch_csrf_token(
    session: Session,
    cve_id: str,
    *,
    section: str = "cve5",
    timeout: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Scrape the CSRF token from the rendered editor page."""
    url = _record_page_url(session, cve_id, section=section)
    status, headers, body = _request(url, session=session, timeout=timeout)
    if _is_login_redirect(status, headers):
        raise SessionExpired(
            "Vulnogram redirected to ASF OAuth login — session cookie expired. Re-run `vulnogram-api-setup`."
        )
    if status != 200:
        raise VulnogramAPIError(f"GET {url} returned HTTP {status}: {body[:200].decode(errors='replace')}")
    text = body.decode("utf-8", errors="replace")
    m = _CSRF_RE.search(text)
    if not m:
        raise CSRFNotFound(
            f"Could not find a `var csrfToken = ...` line on {url}. "
            "The Vulnogram page shape may have changed; check upstream "
            "Vulnogram/Vulnogram@views/edit.pug."
        )
    return m.group(1)


def update_record(
    session: Session,
    cve_id: str,
    document: dict[str, Any],
    *,
    section: str = "cve5",
    timeout: int = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    """POST a CVE document to ``/<section>/<id>``.

    Returns the parsed JSON envelope Vulnogram replies with — typically
    ``{"type": "saved"}`` on success, or ``{"type": "err", "msg": ...}``
    on validation failure. Raises :class:`RecordSaveFailed` for the
    ``err`` envelope so callers can surface the message verbatim.
    """
    csrf = fetch_csrf_token(session, cve_id, section=section, timeout=timeout)
    url = _record_page_url(session, cve_id, section=section)
    status, headers, body = _request(
        url,
        session=session,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "CSRF-Token": csrf,
        },
        body=json.dumps(document).encode("utf-8"),
        timeout=timeout,
    )
    if _is_login_redirect(status, headers):
        raise SessionExpired(
            "Vulnogram redirected to ASF OAuth login during POST — "
            "session cookie expired. Re-run `vulnogram-api-setup`."
        )
    if status >= 400:
        raise VulnogramAPIError(f"POST {url} returned HTTP {status}: {body[:300].decode(errors='replace')}")
    try:
        envelope = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise VulnogramAPIError(
            f"POST {url} returned non-JSON body: {body[:200].decode(errors='replace')}"
        ) from e
    if not isinstance(envelope, dict):
        raise VulnogramAPIError(f"POST {url} returned non-dict envelope: {envelope!r}")
    etype = envelope.get("type")
    if etype == "saved":
        return envelope
    if etype == "go":
        # Vulnogram returns `{type: 'go', to: <new id>}` when the
        # primary ID changes mid-save (renaming). We treat that as
        # success but pass the envelope through so callers can spot it.
        return envelope
    raise RecordSaveFailed(
        f"POST {url} envelope was not `saved`: {envelope}. "
        "Most common cause: validation error in the JSON body."
    )


def probe(session: Session, *, section: str = "cve5", timeout: int = DEFAULT_TIMEOUT_S) -> str:
    """Hit a low-cost protected endpoint and report ``valid`` / ``expired`` / ``error: …``.

    Used by :mod:`vulnogram_api.check`. Picks ``/<section>/new`` because
    it requires authentication but does no DB writes.

    A non-login redirect (e.g. Vulnogram now 302-redirects ``/cve5/new`` to
    ``/allocatecve``) means the session was successfully validated by the
    app — only the post-auth destination changed. Treat any non-login 3xx
    as ``valid``; pinning the probe URL would otherwise need a sync release
    every time the Vulnogram app reshuffles its routing.
    """
    url = f"https://{session.host}/{section}/new"
    try:
        status, headers, _ = _request(url, session=session, timeout=timeout)
    except urllib.error.URLError as e:
        return f"error: {e}"
    if _is_login_redirect(status, headers):
        return "expired"
    if status == 200 or status in (301, 302, 303, 307, 308):
        return "valid"
    return f"error: HTTP {status}"
