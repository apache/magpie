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


def repository_restrictions(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize repository branch restrictions from Bitbucket."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    restrictions = [
        _cloud_branch_restriction(item) if kind == "cloud" else _datacenter_branch_restriction(item)
        for item in values
        if isinstance(item, dict)
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "permission_required": _string(raw.get("permission_required")),
        "restrictions": restrictions,
        "raw": raw,
    }


def issue_summary(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Bitbucket issue as read-only tracker context."""
    if kind == "cloud":
        return {
            "backend": "bitbucket-cloud",
            "id": _string(raw.get("id")),
            "title": raw.get("title"),
            "state": _normalize_issue_state(raw.get("state")),
            "kind": _string(raw.get("kind")),
            "priority": _string(raw.get("priority")),
            "assignee": _cloud_user(raw.get("assignee")),
            "reporter": _cloud_user(raw.get("reporter")),
            "created": _cloud_timestamp(raw.get("created_on")),
            "updated": _cloud_timestamp(raw.get("updated_on")),
            "permalink": _cloud_link(raw, "html"),
            "labels": ["bitbucket", "read-only", "partial-tracker"],
        }

    return {
        "backend": "bitbucket-datacenter",
        "id": _string(raw.get("id")),
        "title": raw.get("title"),
        "state": "unsupported",
        "kind": None,
        "priority": None,
        "assignee": None,
        "reporter": None,
        "created": None,
        "updated": None,
        "permalink": None,
        "labels": ["bitbucket", "read-only", "unsupported-tracker"],
    }


def issue(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Bitbucket issue."""
    summary = issue_summary(kind, raw)
    content = raw.get("content")
    summary["description"] = _cloud_issue_content(content)
    summary["raw"] = raw
    return summary


def issue_list(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Bitbucket issue list response."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "issues": [issue_summary(kind, item) for item in values if isinstance(item, dict)],
        "raw": raw,
    }


def issue_comments(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize read-only Bitbucket issue comments."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    comments = [
        _cloud_issue_comment(item) if kind == "cloud" else _unsupported_issue_comment(item)
        for item in values
        if isinstance(item, dict)
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "issue_id": _string(raw.get("issue_id")),
        "comments": comments,
        "participants": _participants(comments),
        "raw": raw,
    }


def issue_attachments(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize read-only Bitbucket issue attachments."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    attachments = [
        _cloud_issue_attachment(item) if kind == "cloud" else _unsupported_issue_attachment(item)
        for item in values
        if isinstance(item, dict)
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "issue_id": _string(raw.get("issue_id")),
        "attachments": attachments,
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


def pull_request_merge_checks(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize read-only pull request merge-check context from Bitbucket."""
    pull_request_raw = raw.get("pull_request")
    pull_request = pull_request_raw if isinstance(pull_request_raw, dict) else {}

    merge_raw = raw.get("merge")
    merge = merge_raw if isinstance(merge_raw, dict) else {}

    status_raw = raw.get("status")
    if not isinstance(status_raw, dict):
        status_raw = {
            "pull_request_id": raw.get("pull_request_id"),
            "pull_request": pull_request,
            "values": [],
        }

    reviews_raw = raw.get("reviews")
    if not isinstance(reviews_raw, dict):
        reviews_raw = {
            "pull_request_id": raw.get("pull_request_id"),
            "pull_request": pull_request,
            "values": [],
        }

    status = pull_request_status(kind, status_raw)
    reviews = pull_request_reviews(kind, reviews_raw)
    can_merge = _pull_request_can_merge(pull_request, merge)
    conflicted = _pull_request_conflicted(pull_request, merge)
    mergeable = _mergeable_vocabulary(can_merge, conflicted)
    blockers = _merge_check_blockers(status, reviews, merge, can_merge, conflicted)
    merge_check_state = _merge_check_state(blockers, can_merge, conflicted, status, reviews)

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "state": _pull_request_state(kind, pull_request),
        "merge_check_state": merge_check_state,
        "has_known_blockers": bool(blockers),
        "mergeable": mergeable,
        "can_merge": can_merge,
        "conflicted": conflicted,
        "blockers": blockers,
        "checks": status.get("checks"),
        "review_decision": reviews.get("review_decision"),
        "status": status,
        "reviews": reviews,
        "merge": merge,
        "raw": raw,
    }


def pull_request_commits(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize pull request commits from Bitbucket."""
    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    commits = [
        _cloud_commit(item) if kind == "cloud" else _datacenter_commit(item)
        for item in values
        if isinstance(item, dict)
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "commits": commits,
        "raw": raw,
    }


def pull_request_diff(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize pull request diff text from Bitbucket."""
    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "diff": _string(raw.get("body")) or "",
        "content_type": _string(raw.get("content_type")),
        "url": _string(raw.get("url")),
        "raw": raw,
    }


def pull_request_reviews(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize pull request review-state activity from Bitbucket."""
    pull_request_raw = raw.get("pull_request")
    pull_request_data = pull_request_raw if isinstance(pull_request_raw, dict) else {}

    values = raw.get("values")
    if not isinstance(values, list):
        values = []

    review_events: list[dict[str, Any]] = []
    for item in values:
        if not isinstance(item, dict):
            continue

        event = _cloud_review_event(item) if kind == "cloud" else _datacenter_review_event(item)
        if event is not None:
            review_events.append(event)

    reviewers = (
        _cloud_reviewers(pull_request_data) if kind == "cloud" else _datacenter_reviewers(pull_request_data)
    )

    current_approvals = _current_review_signals(reviewers, "approved")
    current_changes_requested = _current_review_signals(reviewers, "changes_requested")

    latest_events = _latest_review_events(review_events)
    event_approvals = [event for event in latest_events if event.get("kind") == "approval"]
    event_changes_requested = [event for event in latest_events if event.get("kind") == "changes_requested"]

    current_approval_authors = {item.get("author") for item in current_approvals}
    current_change_authors = {item.get("author") for item in current_changes_requested}

    approvals = current_approvals or [
        item for item in event_approvals if item.get("author") not in current_change_authors
    ]
    changes_requested = current_changes_requested or [
        item for item in event_changes_requested if item.get("author") not in current_approval_authors
    ]

    return {
        "backend": "bitbucket-cloud" if kind == "cloud" else "bitbucket-datacenter",
        "coverage": "partial-read-only",
        "pull_request_id": _string(raw.get("pull_request_id")),
        "review_decision": _review_decision_from_signals(
            reviewers, latest_events, approvals, changes_requested
        ),
        "reviewers": reviewers,
        "approvals": approvals,
        "changes_requested": changes_requested,
        "review_requests": _review_requests(reviewers),
        "review_events": review_events,
        "raw": raw,
    }


def _pull_request_can_merge(pull_request: dict[str, Any], merge: dict[str, Any]) -> bool | None:
    for source in (merge, pull_request):
        for key in ("canMerge", "can_merge", "mergeable"):
            value = _boolish(source.get(key))
            if value is not None:
                return value

        properties = source.get("properties")
        if isinstance(properties, dict):
            for key in ("canMerge", "can_merge", "mergeable"):
                value = _boolish(properties.get(key))
                if value is not None:
                    return value

    return None


def _pull_request_conflicted(pull_request: dict[str, Any], merge: dict[str, Any]) -> bool | None:
    for source in (merge, pull_request):
        for key in ("conflicted", "has_conflicts", "hasConflicts"):
            value = _boolish(source.get(key))
            if value is not None:
                return value

        properties = source.get("properties")
        if isinstance(properties, dict):
            for key in ("conflicted", "has_conflicts", "hasConflicts"):
                value = _boolish(properties.get(key))
                if value is not None:
                    return value

    return None


def _mergeable_vocabulary(can_merge: bool | None, conflicted: bool | None) -> str:
    if conflicted is True:
        return "conflicting"
    if can_merge is True and conflicted is not True:
        return "clean"
    return "unknown"


def _merge_check_blockers(
    status: dict[str, Any],
    reviews: dict[str, Any],
    merge: dict[str, Any],
    can_merge: bool | None,
    conflicted: bool | None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    if can_merge is False:
        blockers.append(
            {
                "kind": "mergeability",
                "state": "blocked",
                "message": "Pull request is reported as not mergeable.",
            }
        )

    if conflicted is True:
        blockers.append(
            {
                "kind": "merge_conflict",
                "state": "blocked",
                "message": "Pull request is reported as conflicted.",
            }
        )

    blockers.extend(_merge_veto_blockers(merge))

    checks = status.get("checks")
    if checks in {"failing", "pending"}:
        blockers.append(
            {
                "kind": "status_checks",
                "state": checks,
                "message": f"Pull request status checks are {checks}.",
            }
        )

    review_decision = reviews.get("review_decision")
    if review_decision in {"changes_requested", "review_required"}:
        blockers.append(
            {
                "kind": "reviews",
                "state": review_decision,
                "message": f"Pull request review decision is {review_decision}.",
            }
        )

    return blockers


def _merge_veto_blockers(merge: dict[str, Any]) -> list[dict[str, Any]]:
    vetoes = merge.get("vetoes")
    if not isinstance(vetoes, list):
        return []

    blockers: list[dict[str, Any]] = []
    for veto in vetoes:
        if not isinstance(veto, dict):
            continue
        summary = _string(veto.get("summaryMessage") or veto.get("summary"))
        details = _string(veto.get("detailedMessage") or veto.get("details"))
        blockers.append(
            {
                "kind": "merge_veto",
                "state": "blocked",
                "message": summary or details or "Bitbucket reported a merge veto.",
                "details": details,
                "raw": veto,
            }
        )

    return blockers


def _merge_check_state(
    blockers: list[dict[str, Any]],
    can_merge: bool | None,
    conflicted: bool | None,
    status: dict[str, Any],
    reviews: dict[str, Any],
) -> str:
    if blockers:
        return "blocked"

    known_clean_merge = can_merge is True and conflicted is not True
    checks_known_clean = status.get("checks") in {"none", "passing"}
    review_known_clean = reviews.get("review_decision") in {"approved", "unknown"}

    if known_clean_merge and checks_known_clean and review_known_clean:
        return "passing"

    return "unknown"


def _boolish(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _cloud_reviewers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    reviewers = raw.get("reviewers")
    participants = raw.get("participants")
    normalized: dict[str, dict[str, Any]] = {}

    if isinstance(reviewers, list):
        for item in reviewers:
            if isinstance(item, dict):
                reviewer = _cloud_reviewer(item, requested=True)
                key = reviewer.get("user")
                if isinstance(key, str):
                    normalized[key] = reviewer

    if isinstance(participants, list):
        for item in participants:
            if isinstance(item, dict):
                participant = _cloud_reviewer(item, requested=False)
                key = participant.get("user")
                if not isinstance(key, str):
                    continue
                existing = normalized.get(key)
                if existing is None:
                    normalized[key] = participant
                elif (
                    existing.get("review_state") == "pending" and participant.get("review_state") != "unknown"
                ):
                    # A participants[] entry refines a requested reviewer's state,
                    # but only when it carries a definite signal (approved /
                    # changes_requested). Never downgrade a pending request to
                    # "unknown" — that would drop the reviewer from review_requests
                    # and collapse review_decision to "unknown".
                    normalized[key] = participant

    return list(normalized.values())


def _cloud_reviewer(raw: dict[str, Any], *, requested: bool) -> dict[str, Any]:
    state = _cloud_reviewer_state(raw, requested=requested)
    return {
        "user": _cloud_user(raw.get("user") or raw),
        "approved": state == "approved",
        "review_state": state,
        "role": _string(raw.get("role")),
        "raw": raw,
    }


def _cloud_reviewer_state(raw: dict[str, Any], *, requested: bool) -> str:
    if raw.get("approved") is True:
        return "approved"

    state = _string(raw.get("state") or raw.get("status"))
    normalized = state.upper() if state is not None else ""
    if normalized in {"CHANGES_REQUESTED", "NEEDS_WORK"}:
        return "changes_requested"
    if normalized in {"APPROVED"}:
        return "approved"
    if normalized in {"UNAPPROVED", "PENDING", "REVIEW_REQUESTED"}:
        return "pending"

    return "pending" if requested else "unknown"


def _datacenter_reviewers(raw: dict[str, Any]) -> list[dict[str, Any]]:
    reviewers = raw.get("reviewers")
    if not isinstance(reviewers, list):
        return []

    return [_datacenter_reviewer(item) for item in reviewers if isinstance(item, dict)]


def _datacenter_reviewer(raw: dict[str, Any]) -> dict[str, Any]:
    review_state = _datacenter_reviewer_state(raw)

    return {
        "user": _datacenter_user(raw.get("user") or raw),
        "approved": review_state == "approved",
        "status": _string(raw.get("status")),
        "review_state": review_state,
        "role": _string(raw.get("role")),
        "raw": raw,
    }


def _datacenter_reviewer_state(raw: dict[str, Any]) -> str:
    approved = raw.get("approved")
    if approved is True:
        return "approved"

    status = _string(raw.get("status"))
    normalized = status.upper() if status is not None else ""
    if normalized == "APPROVED":
        return "approved"
    if normalized in {"NEEDS_WORK", "CHANGES_REQUESTED"}:
        return "changes_requested"
    if normalized in {"UNAPPROVED", "PENDING", "NOT_APPROVED"}:
        return "pending"

    return "unknown"


def _cloud_review_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    approval = raw.get("approval")
    if isinstance(approval, dict):
        return {
            "kind": "approval",
            "author": _cloud_user(approval.get("user")),
            "date": _cloud_timestamp(approval.get("date")),
            "raw": raw,
        }

    changes_requested = raw.get("changes_requested")
    if isinstance(changes_requested, dict):
        return {
            "kind": "changes_requested",
            "author": _cloud_user(changes_requested.get("user")),
            "date": _cloud_timestamp(changes_requested.get("date")),
            "raw": raw,
        }

    approval_removed = raw.get("approval_removed") or raw.get("unapproval")
    if isinstance(approval_removed, dict):
        return {
            "kind": "approval_removed",
            "author": _cloud_user(approval_removed.get("user")),
            "date": _cloud_timestamp(approval_removed.get("date")),
            "raw": raw,
        }

    update = raw.get("update")
    if isinstance(update, dict):
        return {
            "kind": "updated",
            "author": _cloud_user(update.get("author")),
            "date": _cloud_timestamp(update.get("date")),
            "raw": raw,
        }

    return None


def _datacenter_review_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    action = _string(raw.get("action") or raw.get("type"))
    normalized_action = action.upper() if action is not None else ""

    if normalized_action == "APPROVED":
        return _datacenter_activity_event("approval", raw)
    if normalized_action in {"UNAPPROVED", "APPROVAL_REMOVED"}:
        return _datacenter_activity_event("approval_removed", raw)
    if normalized_action in {"NEEDS_WORK", "CHANGES_REQUESTED"}:
        return _datacenter_activity_event("changes_requested", raw)
    if normalized_action in {"REVIEWED", "UPDATED", "RESCOPED"}:
        return _datacenter_activity_event(normalized_action.lower(), raw)

    return None


def _datacenter_activity_event(kind: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "author": _datacenter_user(raw.get("user")),
        "date": _epoch_millis_to_iso(raw.get("createdDate")),
        "raw": raw,
    }


def _current_review_signals(
    reviewers: list[dict[str, Any]],
    review_state: str,
) -> list[dict[str, Any]]:
    return [
        {
            "kind": review_state,
            "author": reviewer.get("user"),
            "status": reviewer.get("status"),
            "raw": reviewer.get("raw"),
        }
        for reviewer in reviewers
        if reviewer.get("review_state") == review_state
    ]


def _review_decision_from_signals(
    reviewers: list[dict[str, Any]],
    latest_events: Any,
    approvals: list[dict[str, Any]],
    changes_requested: list[dict[str, Any]],
) -> str:
    if changes_requested:
        return "changes_requested"
    if approvals:
        return "approved"
    return _review_decision(reviewers, latest_events)


def _review_decision(
    reviewers: list[dict[str, Any]],
    latest_events: list[dict[str, Any]],
) -> str:
    reviewer_states = {reviewer.get("review_state") for reviewer in reviewers}
    if "changes_requested" in reviewer_states:
        return "changes_requested"
    if "approved" in reviewer_states:
        return "approved"
    if "pending" in reviewer_states:
        return "review_required"

    event_states = {event.get("kind") for event in latest_events}
    if "changes_requested" in event_states:
        return "changes_requested"
    if "approval" in event_states:
        return "approved"
    if "approval_removed" in event_states:
        return "review_required"

    return "unknown"


def _latest_review_events(review_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, tuple[str, int, dict[str, Any]]] = {}
    for index, event in enumerate(review_events):
        kind = event.get("kind")
        if kind not in {"approval", "approval_removed", "changes_requested"}:
            continue

        author = event.get("author")
        if not isinstance(author, str):
            continue

        date = _string(event.get("date")) or ""
        previous = latest.get(author)
        if previous is None or (date, index) >= (previous[0], previous[1]):
            latest[author] = (date, index, event)

    return [item[2] for item in latest.values()]


def _review_requests(reviewers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [reviewer for reviewer in reviewers if reviewer.get("review_state") == "pending"]


def _cloud_commit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": _string(raw.get("hash")),
        "message": _string(raw.get("message")),
        "author": _cloud_commit_author(raw.get("author")),
        "date": _cloud_timestamp(raw.get("date")),
        "links": _cloud_links(raw),
        "raw": raw,
    }


def _datacenter_commit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "hash": _string(raw.get("id") or raw.get("displayId")),
        "display_hash": _string(raw.get("displayId")),
        "message": _string(raw.get("message")),
        "author": _datacenter_commit_author(raw.get("author")),
        "date": _epoch_millis_to_iso(raw.get("authorTimestamp") or raw.get("committerTimestamp")),
        "links": _datacenter_links(raw),
        "raw": raw,
    }


def _cloud_commit_author(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None

    user = raw.get("user")
    if isinstance(user, dict):
        display_name = _cloud_user(user)
        if display_name:
            return display_name

    raw_author = raw.get("raw")
    if isinstance(raw_author, str):
        return raw_author

    return None


def _datacenter_commit_author(raw: object) -> str | None:
    if isinstance(raw, dict):
        return _datacenter_user(raw)
    if isinstance(raw, str):
        return raw
    return None


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


def _cloud_issue_attachment(raw: dict[str, Any]) -> dict[str, Any]:
    name = _string(raw.get("name") or raw.get("filename"))
    size = raw.get("size")
    normalized_size = size if isinstance(size, int) and not isinstance(size, bool) and size >= 0 else None

    return {
        "id": _string(raw.get("id") or raw.get("uuid")) or name,
        "name": name,
        "filename": _string(raw.get("filename") or raw.get("name")),
        "size": normalized_size,
        "user": _cloud_user(raw.get("user")),
        "created": _cloud_timestamp(raw.get("created_on")),
        "updated": _cloud_timestamp(raw.get("updated_on")),
        "download_url": _cloud_link(raw, "self") or _cloud_link(raw, "html"),
        "permalink": _cloud_link(raw, "html"),
        "raw": raw,
    }


def _unsupported_issue_attachment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _string(raw.get("id")),
        "name": None,
        "filename": None,
        "size": None,
        "user": None,
        "created": None,
        "updated": None,
        "download_url": None,
        "permalink": None,
        "raw": raw,
    }


def _cloud_issue_comment(raw: dict[str, Any]) -> dict[str, Any]:
    body = _cloud_issue_content(raw.get("content"))
    return {
        "id": _string(raw.get("id")),
        "author": _cloud_user(raw.get("user")),
        "body": body,
        "created": _cloud_timestamp(raw.get("created_on")),
        "updated": _cloud_timestamp(raw.get("updated_on")),
        "date": _cloud_timestamp(raw.get("created_on")),
        "kind": "comment",
        "deleted": _bool_or_none(raw.get("deleted")),
        "permalink": _cloud_link(raw, "html"),
        "raw": raw,
    }


def _unsupported_issue_comment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _string(raw.get("id")),
        "author": None,
        "body": None,
        "created": None,
        "updated": None,
        "date": None,
        "kind": "unsupported",
        "deleted": None,
        "permalink": None,
        "raw": raw,
    }


def _normalize_issue_state(value: object) -> str:
    state = _string(value)
    if not state:
        return "unknown"

    normalized = state.lower().replace(" ", "_").replace("-", "_")
    if normalized in {"new", "open"}:
        return "open"
    if normalized in {"resolved", "closed", "duplicate", "invalid", "wontfix", "wont_fix"}:
        return "closed"
    return normalized


def _cloud_issue_content(raw: object) -> str | None:
    if isinstance(raw, dict):
        value = raw.get("raw") or raw.get("html") or raw.get("markup")
        return _string(value)
    return _string(raw)


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


def _cloud_branch_restriction(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _string(raw.get("id")),
        "kind": _string(raw.get("kind") or raw.get("type")),
        "pattern": _string(raw.get("pattern")),
        "branch_match_kind": _string(raw.get("branch_match_kind")),
        "branch_type": _string(raw.get("branch_type")),
        "users": _cloud_users(raw.get("users")),
        "groups": _cloud_groups(raw.get("groups")),
        "value": raw.get("value"),
        "raw": raw,
    }


def _datacenter_branch_restriction(raw: dict[str, Any]) -> dict[str, Any]:
    matcher = raw.get("matcher")
    matcher_data = matcher if isinstance(matcher, dict) else {}

    return {
        "id": _string(raw.get("id")),
        "kind": _string(raw.get("type") or raw.get("kind")),
        "pattern": _datacenter_matcher_pattern(matcher_data),
        "branch_match_kind": _datacenter_matcher_type(matcher_data),
        "branch_type": _string(matcher_data.get("id")),
        "users": _datacenter_users(raw.get("users")),
        "groups": _datacenter_groups(raw.get("groups")),
        "access_keys": _datacenter_access_keys(raw.get("accessKeys")),
        "raw": raw,
    }


def _datacenter_matcher_pattern(raw: dict[str, Any]) -> str | None:
    value = raw.get("displayId") or raw.get("id")
    return _string(value)


def _datacenter_matcher_type(raw: dict[str, Any]) -> str | None:
    matcher_type = raw.get("type")
    if isinstance(matcher_type, dict):
        return _string(matcher_type.get("id") or matcher_type.get("name"))
    return _string(matcher_type or raw.get("displayId"))


def _cloud_users(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    users: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            user = _cloud_user(item)
            if user:
                users.append(user)
        elif isinstance(item, str):
            users.append(item)
    return users


def _cloud_groups(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    groups: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            group = _string(item.get("name") or item.get("slug") or item.get("full_slug"))
            if group:
                groups.append(group)
        elif isinstance(item, str):
            groups.append(item)
    return groups


def _datacenter_users(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    users: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            user = _datacenter_user(item)
            if user:
                users.append(user)
        elif isinstance(item, str):
            users.append(item)
    return users


def _datacenter_groups(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    groups: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            group = _string(item.get("name") or item.get("slug"))
            if group:
                groups.append(group)
        elif isinstance(item, str):
            groups.append(item)
    return groups


def _datacenter_access_keys(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    keys: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            key = _string(item.get("key") or item.get("label") or item.get("id"))
            if key:
                keys.append(key)
        elif isinstance(item, str):
            keys.append(item)
    return keys


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
