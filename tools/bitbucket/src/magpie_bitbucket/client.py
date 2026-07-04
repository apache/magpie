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


class BitbucketError(Exception):
    """Raised when the Bitbucket bridge cannot complete a request."""


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
        username=os.environ.get("BITBUCKET_USERNAME"),
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

    if scheme.lower() == "basic":
        username = require(config.username, "BITBUCKET_USERNAME")
        raw = f"{username}:{token}".encode()
        return f"Basic {base64.b64encode(raw).decode('ascii')}"

    return f"{scheme} {token}"


def get_json(url: str, config: BitbucketConfig) -> dict[str, Any]:
    """GET a Bitbucket API URL and parse the JSON response."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": make_auth_header(config),
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise BitbucketError(f"Expected JSON object from {url}")
            return parsed
    except urllib.error.HTTPError as exc:
        message = _read_http_error(exc)
        raise BitbucketError(f"Bitbucket request failed with HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise BitbucketError(f"Failed to connect to Bitbucket: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise BitbucketError(f"Failed to parse JSON response from {url}") from exc


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
