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

from typing import Any
from urllib.parse import urlparse

from magpie_bitbucket.client import BitbucketConfig, BitbucketError, get_json, get_text, quote_path, require

CLOUD_API_BASE = "https://api.bitbucket.org/2.0"


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
    """Fetch build statuses for a Bitbucket Cloud pull request."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/statuses"

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
