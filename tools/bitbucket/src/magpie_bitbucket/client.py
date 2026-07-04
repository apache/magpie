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

"""Shared Bitbucket client configuration and HTTP helpers."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 30
_ALLOWED_AUTH_SCHEMES = {"basic", "bearer"}


class BitbucketError(Exception):
    """Raised when the Bitbucket bridge cannot complete a request."""


class NoAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so Authorization is not forwarded to another host."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise BitbucketError(f"Bitbucket request redirected to {newurl}; refusing to forward credentials")


@dataclass(frozen=True)
class BitbucketConfig:
    """Environment-derived Bitbucket bridge configuration."""

    kind: str
    token: str | None
    auth_scheme: str
    username: str | None
    workspace: str | None
    repo_slug: str | None
    base_url: str | None
    project_key: str | None


def load_config() -> BitbucketConfig:
    """Load Bitbucket bridge configuration from environment variables."""
    kind = os.environ.get("BITBUCKET_KIND", "cloud").strip().lower()
    if kind not in {"cloud", "datacenter"}:
        raise BitbucketError("BITBUCKET_KIND must be 'cloud' or 'datacenter'")

    default_auth_scheme = "Basic" if kind == "cloud" else "Bearer"

    return BitbucketConfig(
        kind=kind,
        token=os.environ.get("BITBUCKET_TOKEN"),
        auth_scheme=os.environ.get("BITBUCKET_AUTH_SCHEME", default_auth_scheme),
        username=os.environ.get("BITBUCKET_CLOUD_USER"),
        workspace=os.environ.get("BITBUCKET_WORKSPACE"),
        repo_slug=os.environ.get("BITBUCKET_REPO_SLUG"),
        base_url=os.environ.get("BITBUCKET_BASE_URL"),
        project_key=os.environ.get("BITBUCKET_PROJECT_KEY"),
    )


def require(value: str | None, name: str) -> str:
    """Return a required config value or raise a readable bridge error."""
    if not value:
        raise BitbucketError(f"{name} is required")
    return value


def quote_path(value: str) -> str:
    """Quote one URL path segment."""
    return urllib.parse.quote(value, safe="")


def make_auth_header(config: BitbucketConfig) -> str:
    """Build the Authorization header for the selected Bitbucket backend."""
    token = require(config.token, "BITBUCKET_TOKEN")
    scheme = config.auth_scheme.strip()

    if scheme.lower() not in _ALLOWED_AUTH_SCHEMES:
        raise BitbucketError("BITBUCKET_AUTH_SCHEME must be 'Basic' or 'Bearer'")

    if scheme.lower() == "basic":
        username = require(config.username, "BITBUCKET_CLOUD_USER")
        raw = f"{username}:{token}".encode()
        return f"Basic {base64.b64encode(raw).decode('ascii')}"

    return f"Bearer {token}"


def get_json(url: str, config: BitbucketConfig) -> dict[str, Any]:
    """GET a Bitbucket API URL and parse the JSON response."""
    _require_https(url)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": make_auth_header(config),
        },
        method="GET",
    )

    opener = urllib.request.build_opener(NoAuthRedirectHandler)

    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise BitbucketError(f"Expected JSON object from {url}")
            return parsed
    except BitbucketError:
        raise
    except urllib.error.HTTPError as exc:
        message = _read_http_error(exc)
        raise BitbucketError(f"Bitbucket request failed with HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise BitbucketError(f"Failed to connect to Bitbucket: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BitbucketError(
            f"Timed out while connecting to Bitbucket after {DEFAULT_TIMEOUT_SECONDS}s"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BitbucketError(f"Failed to parse JSON response from {url}") from exc


def _require_https(url: str) -> None:
    """Require HTTPS for Bitbucket API URLs."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise BitbucketError("Bitbucket API URLs must use HTTPS")


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    """Read the response body from an HTTPError when available."""
    try:
        body = exc.read().decode("utf-8")
    except Exception:
        return exc.reason

    if not body:
        return exc.reason

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body

    if isinstance(parsed, dict):
        error = parsed.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if parsed.get("message"):
            return str(parsed["message"])
        if parsed.get("errors"):
            return str(parsed["errors"])

    return body
