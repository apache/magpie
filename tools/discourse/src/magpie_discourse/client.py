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

"""Shared Discourse client configuration and HTTP helpers."""

from __future__ import annotations

import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 30

QueryValue = str | int | Sequence[str | int]


class DiscourseError(Exception):
    """Raised when the Discourse bridge cannot complete a request."""


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep read requests within the configured forum's origin and path."""

    def __init__(self, base_url: str) -> None:
        self._origin = origin(parse_url(base_url))
        self._raw_path = urllib.parse.urlsplit(base_url).path.rstrip("/")
        self._path = _checked_path(base_url).rstrip("/")

    def check_request(self, request: urllib.request.Request) -> None:
        """Reject writes and requests outside the configured forum before sending."""
        if request.get_method() != "GET":
            raise DiscourseError("Only GET requests are supported by the read-only Discourse bridge")
        self._check_url(request.full_url)

    def _check_url(self, url: str) -> None:
        destination = parse_url(url)
        raw_path = urllib.parse.urlsplit(url).path
        path = _checked_path(url)
        if (
            origin(destination) != self._origin
            or destination.username is not None
            or not _is_under_path(raw_path, self._raw_path)
            or not _is_under_path(path, self._path)
        ):
            raise DiscourseError(
                "Discourse request is outside the configured forum; refusing to forward credentials"
            )

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        self.check_request(req)
        # Validate the supplied target too; urllib may already have normalised Location.
        _checked_path(newurl)
        try:
            target = urllib.parse.urljoin(req.full_url, newurl)
        except ValueError as exc:
            raise DiscourseError("Invalid Discourse redirect URL; refusing to forward credentials") from exc
        self._check_url(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def origin(parsed: urllib.parse.ParseResult) -> tuple[str, str | None, int | None]:
    """Return the effective origin of a URL for redirect comparisons."""
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else None)
    return (parsed.scheme, parsed.hostname, port)


def parse_url(value: str) -> urllib.parse.ParseResult:
    """Parse a URL and validate its host/port before it can reach urllib."""
    try:
        parsed = urllib.parse.urlparse(value)
        origin(parsed)
    except ValueError as exc:
        raise DiscourseError("Invalid Discourse URL: check its host and port") from exc
    return parsed


def _checked_path(url: str) -> str:
    """Decode a path once, rejecting encoded separators and ambiguous escapes."""
    message = "Invalid Discourse URL path; refusing to forward credentials"
    if any(ord(char) < 32 or ord(char) == 127 for char in url):
        raise DiscourseError(message)
    parse_url(url)
    path = urllib.parse.urlsplit(url).path
    if re.search(r"%(?![0-9a-fA-F]{2})|%(?:2f|5c)", path, re.IGNORECASE):
        raise DiscourseError(message)
    try:
        path = urllib.parse.unquote(path, errors="strict")
    except UnicodeDecodeError as exc:
        raise DiscourseError(message) from exc
    if (
        "%" in path
        or "\\" in path
        or any(ord(char) < 32 or ord(char) == 127 for char in path)
        or any(segment in (".", "..") for segment in path.split("/"))
    ):
        raise DiscourseError(message)
    return path


def _is_under_path(path: str, base_path: str) -> bool:
    """Check a complete path-segment boundary without changing its spelling."""
    return not base_path or path == base_path or path.startswith(f"{base_path}/")


@dataclass(frozen=True)
class DiscourseConfig:
    """Environment-derived Discourse bridge configuration."""

    base_url: str
    api_key: str | None
    api_username: str | None


def load_config() -> DiscourseConfig:
    """Load the bridge configuration from environment variables."""
    raw_url = os.environ.get("DISCOURSE_URL", "").strip()
    if not raw_url:
        raise DiscourseError("DISCOURSE_URL is required (the forum's https:// base URL)")
    parsed = parse_url(raw_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise DiscourseError("DISCOURSE_URL must be an https:// URL")
    if "?" in raw_url or "#" in raw_url or parsed.username is not None:
        raise DiscourseError("DISCOURSE_URL must not carry credentials, a query or a fragment")
    base_url = raw_url.rstrip("/")
    path_error = "DISCOURSE_URL has an invalid or ambiguous path"
    try:
        _checked_path(base_url)
    except DiscourseError as exc:
        raise DiscourseError(path_error) from exc
    base_path = urllib.parse.urlsplit(base_url).path
    if ";" in base_path.rsplit("/", 1)[-1]:
        raise DiscourseError(path_error)
    if not base_path.isascii() or " " in base_path:
        raise DiscourseError(f"{path_error}; use percent-encoded non-ASCII characters and spaces")

    api_key = os.environ.get("DISCOURSE_API_KEY", "").strip() or None
    api_username = os.environ.get("DISCOURSE_API_USERNAME", "").strip() or None
    if api_key and not api_username:
        raise DiscourseError("DISCOURSE_API_USERNAME is required when DISCOURSE_API_KEY is set")
    if any("\r" in value or "\n" in value for value in (api_key or "", api_username or "")):
        raise DiscourseError("Discourse API credentials must not contain newlines")
    if api_username is not None and not api_username.isascii():
        raise DiscourseError("DISCOURSE_API_USERNAME must contain only ASCII characters")
    if api_key is not None:
        try:
            api_key.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise DiscourseError("DISCOURSE_API_KEY must be encodable as a latin-1 HTTP header") from exc

    return DiscourseConfig(base_url=base_url, api_key=api_key, api_username=api_username)


def auth_headers(config: DiscourseConfig) -> dict[str, str]:
    """Return the API key headers, or none for anonymous reads of a public forum."""
    if not config.api_key:
        return {}
    return {"Api-Key": config.api_key, "Api-Username": config.api_username or ""}


def api_url(config: DiscourseConfig, path: str, params: Mapping[str, QueryValue] | None = None) -> str:
    """Build an API URL under the configured forum base URL."""
    url = f"{config.base_url}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params, doseq=True)}"
    return url


def _urlopen(request: urllib.request.Request, timeout: float, *, base_url: str) -> Any:
    """Open a GET with the configured forum boundary (patched in tests)."""
    handler = SameOriginRedirectHandler(base_url)
    handler.check_request(request)
    opener = urllib.request.build_opener(handler)
    return opener.open(request, timeout=timeout)


def get_json(
    config: DiscourseConfig, path: str, params: Mapping[str, QueryValue] | None = None
) -> dict[str, Any]:
    """GET a Discourse API path and parse the JSON object it returns."""
    url = api_url(config, path, params)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", **auth_headers(config)},
        method="GET",
    )
    try:
        with _urlopen(request, DEFAULT_TIMEOUT_SECONDS, base_url=config.base_url) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except DiscourseError:
        raise
    except urllib.error.HTTPError as exc:
        raise DiscourseError(_http_error_message(exc)) from exc
    except urllib.error.URLError as exc:
        raise DiscourseError(f"Failed to connect to Discourse: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DiscourseError(f"Timed out talking to Discourse after {DEFAULT_TIMEOUT_SECONDS}s") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DiscourseError(f"Discourse returned a response that is not JSON: {url}") from exc
    except (OSError, http.client.HTTPException) as exc:
        raise DiscourseError(f"Failed to read the Discourse response: {exc}") from exc
    if not isinstance(parsed, dict):
        raise DiscourseError(f"Expected a JSON object from {url}")
    return parsed


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    """Describe an HTTP error, keeping Discourse's own error text when it sends one."""
    message = f"Discourse request failed with HTTP {exc.code}"
    if exc.code == 429:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        hint = f"{retry_after} seconds" if retry_after and retry_after.isdecimal() else retry_after
        return f"{message} (rate limited; retry after {hint or 'a while'})"
    try:
        body = json.loads(exc.read().decode("utf-8"))
    except (OSError, http.client.HTTPException, UnicodeDecodeError, json.JSONDecodeError):
        return message
    errors = body.get("errors") if isinstance(body, dict) else None
    if isinstance(errors, list) and errors:
        return f"{message}: {'; '.join(str(error) for error in errors)}"
    return message
