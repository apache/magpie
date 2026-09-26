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

from __future__ import annotations

import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PAGES = 10


class GitLabError(Exception):
    pass


@dataclass
class GitLabConfig:
    token: str | None
    instance_url: str
    token_type: str = field(default="bearer")
    auth_scheme: str = field(default="")


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------


def validate_instance_url(url: str) -> None:
    """Reject non-HTTPS URLs unless they target localhost for local dev."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1"):
        return
    raise GitLabError(f"Insecure instance URL scheme '{parsed.scheme}': HTTPS is required")


# ---------------------------------------------------------------------------
# Safe redirect handler -- prevents token leak on cross-origin or
# HTTPS->HTTP redirects (CWE-200 / CWE-319).
# ---------------------------------------------------------------------------


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Block redirects that would leak credentials to another origin."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        orig = urllib.parse.urlparse(req.full_url)
        resolved_dest = urllib.parse.urljoin(req.full_url, newurl)
        dest = urllib.parse.urlparse(resolved_dest)

        # Deny transport downgrade (HTTPS -> HTTP)
        if orig.scheme == "https" and dest.scheme != "https":
            raise GitLabError("Redirect blocked: HTTPS-to-HTTP downgrade is forbidden")

        # Deny cross-origin redirect (scheme, hostname, port)
        orig_origin = (orig.scheme, orig.hostname, orig.port)
        dest_origin = (dest.scheme, dest.hostname, dest.port)
        if orig_origin != dest_origin:
            raise GitLabError(
                f"Redirect blocked: cross-origin redirect from {orig_origin} to {dest_origin} is forbidden"
            )

        return super().redirect_request(req, fp, code, msg, headers, resolved_dest)


def _build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_SafeRedirectHandler)


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


def load_config() -> GitLabConfig:
    """Build a ``GitLabConfig`` from environment variables.

    Prefers ``GITLAB_TOKEN`` (Personal Access Token, sent as ``PRIVATE-TOKEN:``
    when starting with ``glpat-`` or ``Authorization: Bearer`` otherwise).
    Falls back to ``CI_JOB_TOKEN`` (sent as ``JOB-TOKEN:``).
    Tokens are optional for unauthenticated reads on public projects.
    """
    gitlab_token = os.environ.get("GITLAB_TOKEN")
    ci_job_token = os.environ.get("CI_JOB_TOKEN")
    auth_scheme = os.environ.get("GITLAB_AUTH_SCHEME", "")

    if gitlab_token:
        token = gitlab_token
        token_type = "bearer"
    elif ci_job_token:
        token = ci_job_token
        token_type = "job_token"
    else:
        token = None
        token_type = "bearer"

    instance_url = os.environ.get("GITLAB_INSTANCE_URL", "https://gitlab.com").rstrip("/")
    validate_instance_url(instance_url)
    return GitLabConfig(
        token=token,
        instance_url=instance_url,
        token_type=token_type,
        auth_scheme=auth_scheme,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def require(value: str | None, name: str) -> str:
    if not value:
        raise GitLabError(f"{name} is required")
    return value


def quote_path(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _auth_headers(config: GitLabConfig) -> dict[str, str]:
    """Return the correct authentication header for the token type, or none if unauthenticated."""
    headers: dict[str, str] = {"Accept": "application/json"}
    if not config.token:
        return headers

    if config.auth_scheme:
        scheme = config.auth_scheme.strip().lower()
        if scheme in ("private-token", "privatetoken"):
            headers["PRIVATE-TOKEN"] = config.token
        elif scheme == "bearer":
            headers["Authorization"] = f"Bearer {config.token}"
        elif scheme in ("job-token", "job_token"):
            headers["JOB-TOKEN"] = config.token
        else:
            raise GitLabError(f"Unsupported GITLAB_AUTH_SCHEME: '{config.auth_scheme}'")
    else:
        if config.token_type == "job_token":
            headers["JOB-TOKEN"] = config.token
        elif config.token.startswith("glpat-"):
            headers["PRIVATE-TOKEN"] = config.token
        else:
            headers["Authorization"] = f"Bearer {config.token}"

    return headers


# ---------------------------------------------------------------------------
# Core HTTP helpers
# ---------------------------------------------------------------------------


def get_json(url: str, config: GitLabConfig) -> Any:
    """Fetch a single JSON resource (no pagination)."""
    validate_instance_url(url)
    headers = _auth_headers(config)
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = _build_opener()
    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GitLabError(f"HTTP {exc.code}: {exc.reason}") from exc
    except GitLabError:
        raise
    except Exception as exc:
        raise GitLabError(f"Request failed: {exc}") from exc


def get_paged_json(
    url: str,
    config: GitLabConfig,
    limit: int | None = None,
    max_pages: int | None = DEFAULT_MAX_PAGES,
) -> list[Any]:
    """Fetch a paginated JSON collection, following ``X-Next-Page`` up to ``limit`` or ``max_pages``."""
    validate_instance_url(url)
    headers = _auth_headers(config)
    items: list[Any] = []
    separator = "&" if "?" in url else "?"
    current_url: str | None = f"{url}{separator}per_page=100" if "per_page=" not in url else url
    pages_fetched = 0

    target_pages: int | None = max_pages
    if limit is not None:
        pages_needed = max(1, math.ceil(limit / 100))
        target_pages = min(pages_needed, max_pages) if max_pages is not None else pages_needed

    opener = _build_opener()
    while current_url:
        request = urllib.request.Request(current_url, headers=headers, method="GET")
        try:
            with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, list):
                    items.extend(data)
                else:
                    if not items:
                        return [data]
                    raise GitLabError("Unexpected non-list response during pagination")

                pages_fetched += 1
                next_page = response.headers.get("X-Next-Page") if hasattr(response, "headers") else None
                has_more = isinstance(next_page, str) and bool(next_page.strip())

                if limit is not None and len(items) >= limit:
                    items = items[:limit]
                    if has_more:
                        print(
                            f"[magpie-gitlab] Note: Results capped at {len(items)} items; use --limit to fetch more.",
                            file=sys.stderr,
                        )
                    break

                if target_pages is not None and pages_fetched >= target_pages:
                    if has_more and limit is None:
                        print(
                            f"[magpie-gitlab] Note: Results capped at {len(items)} items ({pages_fetched} pages); use --limit to fetch more.",
                            file=sys.stderr,
                        )
                    break

                if has_more and isinstance(next_page, str):
                    parsed = urllib.parse.urlparse(current_url)
                    query = urllib.parse.parse_qs(parsed.query)
                    query["page"] = [next_page.strip()]
                    new_query = urllib.parse.urlencode(query, doseq=True)
                    current_url = urllib.parse.urlunparse(parsed._replace(query=new_query))
                else:
                    current_url = None
        except urllib.error.HTTPError as exc:
            raise GitLabError(f"HTTP {exc.code}: {exc.reason}") from exc
        except GitLabError:
            raise
        except Exception as exc:
            raise GitLabError(f"Request failed: {exc}") from exc

    return items


# ---------------------------------------------------------------------------
# High-level resource helpers
# ---------------------------------------------------------------------------


def get_project(project: str, config: GitLabConfig) -> Any:
    url = f"{config.instance_url}/api/v4/projects/{quote_path(project)}"
    return get_json(url, config)
