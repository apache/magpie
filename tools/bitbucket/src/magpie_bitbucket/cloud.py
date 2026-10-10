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

"""Bitbucket Cloud API operations."""

from __future__ import annotations

import re
import urllib.error
from typing import Any
from urllib.parse import urlparse

from magpie_bitbucket.client import (
    BitbucketConfig,
    BitbucketError,
    get_json,
    get_text,
    post_json,
    quote_path,
    require,
    write_request,
    write_request_with_metadata,
)

CLOUD_API_BASE = "https://api.bitbucket.org/2.0"

_SHA_PREFIX_RE = re.compile(r"[0-9a-f]{7,40}")


def _is_timeout(exc: BaseException) -> bool:
    """True when ``exc`` was raised because a request timed out."""
    cause = exc.__cause__
    if isinstance(cause, TimeoutError):
        return True
    return isinstance(cause, urllib.error.URLError) and isinstance(cause.reason, TimeoutError)


def _validated_next_url(next_url: object, seen_urls: set[str]) -> str:
    """Return a safe Bitbucket Cloud pagination URL or an empty string."""
    if not isinstance(next_url, str):
        return ""

    parsed_next = urlparse(next_url)
    parsed_base = urlparse(CLOUD_API_BASE)
    if parsed_next.scheme != parsed_base.scheme or parsed_next.hostname != parsed_base.hostname:
        msg = "Bitbucket Cloud pagination URL changed scheme or host"
        raise BitbucketError(msg)

    if next_url in seen_urls:
        msg = "Bitbucket Cloud pagination returned a repeated URL"
        raise BitbucketError(msg)

    seen_urls.add(next_url)
    return next_url


def get_repository(config: BitbucketConfig) -> dict[str, Any]:
    """Fetch repository metadata from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}"
    return get_json(url, config)


def get_repository_restrictions(config: BitbucketConfig) -> dict[str, Any]:
    """Fetch branch restrictions from a Bitbucket Cloud repository."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/branch-restrictions"

    combined: dict[str, Any] = {
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def list_open_issues(config: BitbucketConfig) -> dict[str, Any]:
    """List open issues from a Bitbucket Cloud repository."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/issues?q=state%3D%22new%22%20OR%20state%3D%22open%22%20OR%20state%3D%22on%20hold%22"

    combined: dict[str, Any] = {
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_issue(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Fetch one issue from a Bitbucket Cloud repository."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    issue = quote_path(issue_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/issues/{issue}"
    return get_json(url, config)


def create_issue_comment(
    config: BitbucketConfig,
    issue_id: str,
    body: str,
) -> dict[str, Any]:
    """Create one comment on a Bitbucket Cloud issue."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    issue = quote_path(issue_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/issues/{issue}/comments"

    comment = post_json(
        url,
        config,
        {"content": {"raw": body}},
    )
    return {
        "issue_id": issue_id,
        "comment": comment,
    }


def get_issue_comments(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Fetch comments for a Bitbucket Cloud issue."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    issue = quote_path(issue_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/issues/{issue}/comments"

    combined: dict[str, Any] = {
        "issue_id": issue_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_issue_attachments(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Fetch attachment metadata and links for a Bitbucket Cloud issue."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    issue = quote_path(issue_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/issues/{issue}/attachments"

    combined: dict[str, Any] = {
        "issue_id": issue_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def list_open_pull_requests(config: BitbucketConfig) -> dict[str, Any]:
    """List all open pull requests from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests?state=OPEN"

    combined: dict[str, Any] = {
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_pull_request(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch one pull request from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
    return get_json(url, config)


def get_pull_request_commits(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch commits from a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/commits"

    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_pull_request_diff(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch the unified diff for a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff"
    response = get_text(url, config, accept="text/x-diff")

    return {
        "pull_request_id": pull_request_id,
        "body": response["body"],
        "content_type": response["content_type"],
        "url": response["url"],
    }


def approve_pull_request(
    config: BitbucketConfig,
    pull_request_id: str,
) -> dict[str, Any]:
    """Approve one Bitbucket Cloud pull request as the authenticated user."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/approve"

    participant = write_request(
        url,
        config,
        method="POST",
    )
    if participant is None:
        raise BitbucketError("Bitbucket approve response did not contain participant data")

    return {
        "pull_request_id": pull_request_id,
        "participant": participant,
    }


def unapprove_pull_request(
    config: BitbucketConfig,
    pull_request_id: str,
) -> dict[str, Any]:
    """Withdraw the authenticated user's approval from a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/approve"

    result = write_request(
        url,
        config,
        method="DELETE",
    )
    if result is not None:
        raise BitbucketError("Bitbucket unapprove response unexpectedly contained JSON")

    return {
        "pull_request_id": pull_request_id,
    }


def request_pull_request_changes(
    config: BitbucketConfig,
    pull_request_id: str,
) -> dict[str, Any]:
    """Request changes on one Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/request-changes"

    participant = write_request(
        url,
        config,
        method="POST",
    )
    if participant is None:
        raise BitbucketError("Bitbucket request-changes response did not contain participant data")

    return {
        "pull_request_id": pull_request_id,
        "participant": participant,
    }


def remove_pull_request_changes_request(
    config: BitbucketConfig,
    pull_request_id: str,
) -> dict[str, Any]:
    """Remove the authenticated user's change request from a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/request-changes"

    result = write_request(
        url,
        config,
        method="DELETE",
    )
    if result is not None:
        raise BitbucketError("Bitbucket remove-request-changes response unexpectedly contained JSON")

    return {
        "pull_request_id": pull_request_id,
    }


def decline_pull_request(
    config: BitbucketConfig,
    pull_request_id: str,
) -> dict[str, Any]:
    """Decline one Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/decline"

    pull_request = write_request(
        url,
        config,
        method="POST",
    )
    if pull_request is None:
        raise BitbucketError("Bitbucket decline response did not contain pull request data")

    return {
        "pull_request_id": pull_request_id,
        "pull_request": pull_request,
    }


def merge_pull_request(
    config: BitbucketConfig,
    pull_request_id: str,
    strategy: str,
    expected_source_commit: str,
) -> dict[str, Any]:
    """Submit a merge for one Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/merge"

    # Validate the pin before any request: a one- or two-character prefix
    # would match a large share of heads, so the guard could pass by accident.
    expected = expected_source_commit.strip().lower()
    if not _SHA_PREFIX_RE.fullmatch(expected):
        raise BitbucketError(
            f"Expected source commit must be 7 to 40 hexadecimal characters, got {expected_source_commit!r}"
        )

    pull_request = get_pull_request(config, pull_request_id)
    source = pull_request.get("source")
    source_data = source if isinstance(source, dict) else {}
    commit = source_data.get("commit")
    commit_data = commit if isinstance(commit, dict) else {}
    source_commit = commit_data.get("hash")

    if not isinstance(source_commit, str) or not source_commit:
        raise BitbucketError("Bitbucket pull request response did not contain a source commit hash")

    actual = source_commit.lower()

    if not (actual.startswith(expected) or expected.startswith(actual)):
        raise BitbucketError(
            "Bitbucket pull request source commit changed: "
            f"expected {expected_source_commit}, found {source_commit}"
        )

    strategy_map = {
        "merge": "merge_commit",
        "squash": "squash",
        "rebase": "rebase_fast_forward",
    }

    try:
        merge_strategy = strategy_map[strategy]
    except KeyError as exc:
        raise BitbucketError(f"Unsupported pull request merge strategy: {strategy}") from exc

    try:
        response = write_request_with_metadata(
            url,
            config,
            method="POST",
            payload={
                "type": "pullrequest",
                "merge_strategy": merge_strategy,
            },
        )
    except BitbucketError as exc:
        # A synchronous merge can outlast the client timeout while Bitbucket
        # carries on with it, so a timeout here does not mean nothing merged.
        if _is_timeout(exc):
            raise BitbucketError(
                "Bitbucket did not answer the merge request in time; the merge may "
                f"still have been submitted. Check `pr get {pull_request_id}` before retrying."
            ) from exc
        raise

    # Bitbucket may accept a slow merge asynchronously. An empty response
    # body is valid for HTTP 202; Location identifies the merge task.
    if response.status == 202:
        return {
            "pull_request_id": pull_request_id,
            "strategy": strategy,
            "backend_strategy": merge_strategy,
            "source_commit": source_commit,
            "http_status": response.status,
            "task_url": response.location,
            "result": response.body,
        }

    if response.body is None:
        raise BitbucketError("Bitbucket merge response did not contain result data")

    return {
        "pull_request_id": pull_request_id,
        "strategy": strategy,
        "backend_strategy": merge_strategy,
        "source_commit": source_commit,
        "http_status": response.status,
        "task_url": None,
        "result": response.body,
    }


def get_pull_request_merge_task_status(
    config: BitbucketConfig,
    pull_request_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Fetch the status of one asynchronous Bitbucket Cloud merge task."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    merge_task_id = quote_path(task_id)

    url = (
        f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/"
        f"pullrequests/{pr_id}/merge/task-status/{merge_task_id}"
    )

    result = get_json(url, config)

    return {
        "pull_request_id": pull_request_id,
        "task_id": task_id,
        "task_url": url,
        "result": result,
    }


def get_pull_request_reviews(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch review-state activity for a Bitbucket Cloud pull request."""
    pull_request = get_pull_request(config, pull_request_id)

    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/activity"

    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "pull_request": pull_request,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_pull_request_tasks(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch tasks for a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/tasks"

    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def get_pull_request_task(config: BitbucketConfig, pull_request_id: str, task_id: str) -> dict[str, Any]:
    """Fetch one task from a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    task = quote_path(task_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/tasks/{task}"

    raw = get_json(url, config)
    return {
        "pull_request_id": pull_request_id,
        "task": raw,
    }


def get_pull_request_merge_checks(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch read-only merge-check context for a Bitbucket Cloud pull request."""
    status = get_pull_request_status(config, pull_request_id)
    reviews = get_pull_request_reviews(config, pull_request_id)

    pull_request = status.get("pull_request")
    if not isinstance(pull_request, dict):
        pull_request = reviews.get("pull_request")
    if not isinstance(pull_request, dict):
        pull_request = {}

    return {
        "pull_request_id": pull_request_id,
        "pull_request": pull_request,
        "status": status,
        "reviews": reviews,
    }


def get_pull_request_status(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch a Bitbucket Cloud pull request and its build statuses."""
    pull_request = get_pull_request(config, pull_request_id)
    source = pull_request.get("source")
    source_commit = source.get("commit") if isinstance(source, dict) else None

    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/statuses"

    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "commit": source_commit.get("hash") if isinstance(source_commit, dict) else None,
        "values": [],
        "paginated": True,
        "pages": [],
        "pull_request": pull_request,
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined


def create_pull_request_comment(
    config: BitbucketConfig,
    pull_request_id: str,
    body: str,
) -> dict[str, Any]:
    """Create one top-level comment on a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"

    comment = post_json(
        url,
        config,
        {"content": {"raw": body}},
    )
    return {
        "pull_request_id": pull_request_id,
        "comment": comment,
    }


def post_pull_request_review(
    config: BitbucketConfig,
    pull_request_id: str,
    verdict: str,
    body: str,
) -> dict[str, Any]:
    """Post a confirmed review body and verdict to a Bitbucket Cloud pull request."""
    if verdict not in {"comment", "approve", "request-changes"}:
        raise BitbucketError(f"Unsupported pull request review verdict: {verdict}")

    comment_result = create_pull_request_comment(
        config,
        pull_request_id,
        body,
    )

    comment = comment_result.get("comment")

    if verdict == "comment":
        return {
            "pull_request_id": pull_request_id,
            "verdict": verdict,
            "comment": comment,
            "participant": None,
        }

    try:
        if verdict == "approve":
            verdict_result = approve_pull_request(
                config,
                pull_request_id,
            )
        else:
            verdict_result = request_pull_request_changes(
                config,
                pull_request_id,
            )
    except BitbucketError as exc:
        raise BitbucketError(
            "Bitbucket pull request review body was posted, but the "
            f"{verdict} verdict failed. Inspect `pr discussion {pull_request_id}` "
            f"and `pr reviews {pull_request_id}` before retrying to avoid "
            "duplicating the review comment."
        ) from exc

    return {
        "pull_request_id": pull_request_id,
        "verdict": verdict,
        "comment": comment,
        "participant": verdict_result.get("participant"),
    }


def get_pull_request_discussion(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch pull request comments from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments"

    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    seen_urls = {url}
    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        url = _validated_next_url(page.get("next"), seen_urls)

    return combined
