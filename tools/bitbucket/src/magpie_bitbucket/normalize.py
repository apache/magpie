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


def pull_request_discussion(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize pull request discussion/comments from Bitbucket."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    comments: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        if kind == "cloud":
            comments.append(_cloud_comment(item))
        else:
            comments.extend(_datacenter_comment_activity(item))

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "comments": comments,
        "participants": _participants(comments),
        "unresolved_count": None,
        "raw": raw,
    }


def pull_request_status(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize pull request build/status checks from Bitbucket."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    check_details = [
        _cloud_status_check(item) if kind == "cloud" else _datacenter_status_check(item)
        for item in values
        if isinstance(item, dict)
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "commit": _string(raw.get("commit")),
        "state": _pull_request_state(kind, raw.get("pull_request")),
        "checks": _aggregate_checks(check_details),
        "mergeable": "unknown",
        "check_details": check_details,
        "raw": raw,
    }


def _cloud_status_check(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": _string(raw.get("key")),
        "name": _string(raw.get("name") or raw.get("key")),
        "state": _normalize_check_state(raw.get("state")),
        "url": _string(raw.get("url")),
        "description": _string(raw.get("description")),
        "created": _cloud_timestamp(raw.get("created_on")),
        "updated": _cloud_timestamp(raw.get("updated_on")),
        "raw": raw,
    }


def _datacenter_status_check(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": _string(raw.get("key")),
        "name": _string(raw.get("name") or raw.get("key")),
        "state": _normalize_check_state(raw.get("state")),
        "url": _string(raw.get("url")),
        "description": _string(raw.get("description")),
        "created": _epoch_millis_to_iso(raw.get("dateAdded")),
        "updated": _epoch_millis_to_iso(raw.get("dateUpdated")),
        "raw": raw,
    }


def _aggregate_checks(check_details: list[dict[str, Any]]) -> str:
    states = {check.get("state") for check in check_details}
    if not states:
        return "none"
    if "failure" in states:
        return "failing"
    if "pending" in states:
        return "pending"
    if states == {"success"}:
        return "passing"
    return "pending"


def _pull_request_state(kind: str, raw: object) -> str:
    if not isinstance(raw, dict):
        return "unknown"
    if kind == "cloud":
        return _normalize_state(raw.get("state"))
    return _normalize_state(raw.get("state"))


def _normalize_check_state(value: object) -> str:
    raw_state = _string(value)
    state = raw_state.upper() if raw_state is not None else ""
    if state in {"SUCCESS", "SUCCESSFUL", "PASSED"}:
        return "success"
    if state in {"FAILED", "FAILURE", "ERROR"}:
        return "failure"
    if state in {"INPROGRESS", "IN_PROGRESS", "PENDING"}:
        return "pending"
    if state in {"STOPPED", "CANCELLED", "CANCELED"}:
        return "cancelled"
    return "unknown"


def _cloud_comment(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Bitbucket Cloud pull request comment."""
    body = _content_text(raw.get("content"))
    author = _cloud_user(raw.get("user"))
    created = _cloud_timestamp(raw.get("created_on"))
    updated = _cloud_timestamp(raw.get("updated_on"))

    return {
        "id": _string(raw.get("id")),
        "author": author,
        "date": created,
        "created": created,
        "updated": updated,
        "body": body,
        "kind": "comment",
        "deleted": _bool_or_none(raw.get("deleted")),
        "inline": _cloud_inline(raw.get("inline")),
        "raw": raw,
    }


def _datacenter_comment_activity(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize comment-bearing Bitbucket Data Center activity, including replies."""
    action = str(raw.get("action") or raw.get("type") or "").upper()
    if action and action != "COMMENTED":
        return []

    comment = raw.get("comment")
    if not isinstance(comment, dict):
        return []

    return _datacenter_comment_tree(comment, raw)


def _datacenter_comment_tree(
    raw: dict[str, Any],
    activity: dict[str, Any],
    parent_id: str | None = None,
) -> list[dict[str, Any]]:
    normalized = _datacenter_comment(raw, activity, parent_id)

    replies: list[dict[str, Any]] = []
    for reply in raw.get("comments") or []:
        if isinstance(reply, dict):
            replies.extend(_datacenter_comment_tree(reply, activity, normalized["id"]))

    return [normalized, *replies]


def _datacenter_comment(
    raw: dict[str, Any],
    activity: dict[str, Any],
    parent_id: str | None,
) -> dict[str, Any]:
    created = _epoch_millis_to_iso(raw.get("createdDate") or activity.get("createdDate"))
    updated = _epoch_millis_to_iso(raw.get("updatedDate") or activity.get("updatedDate"))

    return {
        "id": _string(raw.get("id") or activity.get("id")),
        "parent_id": parent_id,
        "author": _datacenter_user(raw.get("author") or activity.get("user")),
        "date": created,
        "created": created,
        "updated": updated,
        "body": _string(raw.get("text")),
        "kind": "comment",
        "deleted": _bool_or_none(raw.get("deleted")),
        "inline": _datacenter_inline(raw.get("anchor")),
        "raw": raw,
    }


def _participants(comments: list[dict[str, Any]]) -> list[str]:
    """Return sorted unique discussion participants derived from comments."""
    names: set[str] = set()
    for comment in comments:
        author = comment.get("author")
        if isinstance(author, str):
            names.add(author)
    return sorted(names)


def _content_text(raw: object) -> str | None:
    """Extract Bitbucket Cloud raw comment text without truthiness fallback."""
    if not isinstance(raw, dict):
        return None
    for key in ("raw", "markup", "html"):
        if key in raw:
            return _string(raw.get(key))
    return None


def _bool_or_none(value: object) -> bool | None:
    """Normalize optional booleans."""
    return value if isinstance(value, bool) else None


def _cloud_inline(raw: object) -> dict[str, Any] | None:
    """Normalize Bitbucket Cloud inline comment location."""
    if not isinstance(raw, dict):
        return None

    inline: dict[str, Any] = {}
    if isinstance(raw.get("path"), str):
        inline["path"] = raw["path"]
    if isinstance(raw.get("from"), int):
        inline["from_line"] = raw["from"]
    if isinstance(raw.get("to"), int):
        inline["to_line"] = raw["to"]

    return inline or None


def _datacenter_inline(raw: object) -> dict[str, Any] | None:
    """Normalize Bitbucket Data Center inline comment location."""
    if not isinstance(raw, dict):
        return None

    inline: dict[str, Any] = {}
    if isinstance(raw.get("path"), str):
        inline["path"] = raw["path"]
    if isinstance(raw.get("from"), int):
        inline["from_line"] = raw["from"]
    if isinstance(raw.get("to"), int):
        inline["to_line"] = raw["to"]
    if "to_line" not in inline and isinstance(raw.get("line"), int):
        inline["to_line"] = raw["line"]

    return inline or None


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
