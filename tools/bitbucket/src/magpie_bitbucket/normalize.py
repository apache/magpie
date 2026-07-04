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

"""Normalize Bitbucket Cloud and Data Center responses."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

READ_ONLY_LABELS = ["bitbucket", "read-only", "partial-change-request"]


def repository(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize repository metadata from Bitbucket Cloud or Data Center."""
    if kind == "cloud":
        return {
            "backend": "bitbucket-cloud",
            "id": _string(raw.get("uuid") or raw.get("full_name") or raw.get("slug")),
            "name": raw.get("name"),
            "slug": raw.get("slug"),
            "description": raw.get("description"),
            "is_private": raw.get("is_private"),
            "main_branch": _cloud_main_branch(raw),
            "links": _cloud_links(raw),
            "capabilities": {
                "repository_metadata": "read",
                "pull_requests": "read",
                "issues": "not_implemented",
                "writes": "not_implemented",
            },
            "raw": raw,
        }

    return {
        "backend": "bitbucket-datacenter",
        "id": _string(raw.get("id") or raw.get("slug") or raw.get("name")),
        "name": raw.get("name"),
        "slug": raw.get("slug"),
        "description": raw.get("description"),
        "is_private": _datacenter_private(raw),
        "main_branch": _datacenter_main_branch(raw),
        "links": _datacenter_links(raw),
        "capabilities": {
            "repository_metadata": "read",
            "pull_requests": "read",
            "issues": "not_implemented",
            "writes": "not_implemented",
        },
        "raw": raw,
    }


def pull_request_summary(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one pull request as a read-only change-request summary."""
    if kind == "cloud":
        return {
            "backend": "bitbucket-cloud",
            "id": _string(raw.get("id")),
            "title": raw.get("title"),
            "author": _cloud_user(raw.get("author")),
            "state": _normalize_state(raw.get("state")),
            "created": _cloud_timestamp(raw.get("created_on")),
            "updated": _cloud_timestamp(raw.get("updated_on")),
            "source": _cloud_branch(raw.get("source")),
            "target": _cloud_branch(raw.get("destination")),
            "permalink": _cloud_link(raw, "html"),
            "labels": READ_ONLY_LABELS,
        }

    return {
        "backend": "bitbucket-datacenter",
        "id": _string(raw.get("id")),
        "title": raw.get("title"),
        "author": _datacenter_user(raw.get("author")),
        "state": _normalize_state(raw.get("state")),
        "created": _epoch_millis_to_iso(raw.get("createdDate")),
        "updated": _epoch_millis_to_iso(raw.get("updatedDate")),
        "source": _datacenter_branch(raw.get("fromRef")),
        "target": _datacenter_branch(raw.get("toRef")),
        "permalink": _datacenter_link(raw),
        "labels": READ_ONLY_LABELS,
    }


def pull_request(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one pull request as a read-only change-request proposal."""
    summary = pull_request_summary(kind, raw)
    summary["description"] = raw.get("description")
    summary["mergeable"] = "unknown"
    summary["checks"] = "none"
    summary["diff"] = None
    summary["commits"] = None
    summary["raw"] = raw
    return summary


def pull_request_list(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Bitbucket pull-request list response."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "read-only-partial-change-request",
        "pull_requests": [pull_request_summary(kind, item) for item in values if isinstance(item, dict)],
        "raw": raw,
    }


def _string(value: object) -> str | None:
    """Convert a value to string while preserving missing values as None."""
    if value is None:
        return None
    return str(value)


def _normalize_state(value: object) -> str:
    """Normalize backend-specific PR states to change-request lifecycle words."""
    state = str(value or "").lower()
    if state in {"open", "opened"}:
        return "open"
    if state in {"merged", "fulfilled"}:
        return "merged"
    if state in {"declined", "superseded"}:
        return "declined"
    return state or "unknown"


def _cloud_timestamp(value: object) -> str | None:
    """Return a Cloud timestamp string when present."""
    return _string(value)


def _epoch_millis_to_iso(value: object) -> str | None:
    """Convert Bitbucket Data Center epoch milliseconds to UTC ISO-8601."""
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat().replace("+00:00", "Z")
    return _string(value)


def _cloud_main_branch(raw: dict[str, Any]) -> str | None:
    mainbranch = raw.get("mainbranch")
    if isinstance(mainbranch, dict):
        value = mainbranch.get("name")
        return _string(value)
    return _string(mainbranch)


def _cloud_links(raw: dict[str, Any]) -> dict[str, str]:
    links = raw.get("links")
    if not isinstance(links, dict):
        return {}
    normalized: dict[str, str] = {}
    for name, value in links.items():
        if isinstance(value, dict) and isinstance(value.get("href"), str):
            normalized[name] = value["href"]
    return normalized


def _cloud_link(raw: dict[str, Any], name: str) -> str | None:
    links = _cloud_links(raw)
    return links.get(name)


def _cloud_user(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    return _string(raw.get("display_name") or raw.get("nickname") or raw.get("username") or raw.get("uuid"))


def _cloud_branch(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    branch = raw.get("branch")
    if isinstance(branch, dict):
        return _string(branch.get("name"))
    return None


def _datacenter_private(raw: dict[str, Any]) -> bool | None:
    public = raw.get("public")
    if isinstance(public, bool):
        return not public
    return None


def _datacenter_main_branch(raw: dict[str, Any]) -> str | None:
    branch = raw.get("defaultBranch")
    if isinstance(branch, dict):
        return _string(branch.get("displayId") or branch.get("id"))
    return _string(branch)


def _datacenter_links(raw: dict[str, Any]) -> dict[str, str]:
    links = raw.get("links")
    if not isinstance(links, dict):
        return {}

    normalized: dict[str, str] = {}
    for name, value in links.items():
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict) and isinstance(first.get("href"), str):
                normalized[name] = first["href"]
    return normalized


def _datacenter_link(raw: dict[str, Any]) -> str | None:
    return _datacenter_links(raw).get("self")


def _datacenter_user(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    user = raw.get("user")
    if isinstance(user, dict):
        return _string(user.get("displayName") or user.get("name") or user.get("emailAddress"))
    return _string(raw.get("displayName") or raw.get("name") or raw.get("emailAddress"))


def _datacenter_branch(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    return _string(raw.get("displayId") or raw.get("id"))
