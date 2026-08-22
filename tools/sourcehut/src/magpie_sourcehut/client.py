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

"""SourceHut GraphQL API client."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class SourceHutError(Exception):
    """General exception for SourceHut client errors."""


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
        raise SourceHutError(f"SourceHut request redirected to {newurl}; refusing to forward credentials")


def _require_https(url: str) -> None:
    """Require HTTPS for SourceHut API URLs."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise SourceHutError("SourceHut API URLs must use HTTPS")


def query_graphql(service: str, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a GraphQL query/mutation against a specific SourceHut service.

    Args:
        service: Subdomain of sr.ht (e.g., 'todo', 'lists', 'builds', 'git', 'hg').
        query: The GraphQL query or mutation string.
        variables: Optional variables for the query.

    Returns:
        The 'data' object from the GraphQL response.
    """
    token = os.environ.get("SRHT_TOKEN")
    if not token:
        raise SourceHutError("SRHT_TOKEN environment variable is not set")

    url = f"https://{service}.sr.ht/query"
    _require_https(url)
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    # Writes never follow redirects: repeating a mutation at a redirected
    # location is less safe than failing and requiring the caller to retry.
    opener = urllib.request.build_opener(NoAuthRedirectHandler)

    try:
        with opener.open(req) as resp:
            body = resp.read().decode("utf-8")
            res_json = json.loads(body)
            errors = res_json.get("errors")
            if errors:
                err_msgs = [e.get("message", "Unknown error") for e in errors]
                raise SourceHutError(f"GraphQL error from {service}.sr.ht: {'; '.join(err_msgs)}")
            return res_json.get("data", {})
    except SourceHutError:
        raise
    except urllib.error.HTTPError as exc:
        err_msg = None
        try:
            err_body = exc.read().decode("utf-8")
            err_json = json.loads(err_body)
            err_errors = err_json.get("errors")
            if err_errors:
                err_msgs = [e.get("message", "Unknown error") for e in err_errors]
                err_msg = f"HTTP {exc.code}: {'; '.join(err_msgs)}"
        except (ValueError, AttributeError, TypeError, OSError):
            # Ignore errors parsing the HTTP error response body as JSON. This is
            # a best-effort attempt to extract a nicer message from an untrusted
            # body, so failing to parse it must never be worse than not trying:
            # control falls through to the `status`-only SourceHutError below.
            # `ValueError` covers both json.JSONDecodeError and the
            # UnicodeDecodeError that a non-UTF-8 body raises; `AttributeError`
            # covers a body that is valid JSON but not an object (`null`, an
            # array, a bare string) or an `errors` entry that is not a dict;
            # `OSError` covers a failed `exc.read()`. Programming errors
            # (NameError, RuntimeError, ...) are deliberately left to propagate.
            pass

        if err_msg:
            raise SourceHutError(err_msg) from exc
        raise SourceHutError(f"HTTP request to {url} failed with status {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise SourceHutError(f"Failed to connect to {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SourceHutError(f"Failed to parse JSON response from {url}") from exc
