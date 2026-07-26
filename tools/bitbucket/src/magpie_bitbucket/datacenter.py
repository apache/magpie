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

"""Bitbucket Data Center API operations."""

from __future__ import annotations

from typing import Any

from magpie_bitbucket.client import BitbucketConfig, BitbucketError, get_json, get_text, quote_path, require


def _api_base(config: BitbucketConfig) -> str:
    """Return the normalized Bitbucket Data Center REST API base URL."""
    base_url = require(config.base_url, "BITBUCKET_BASE_URL").rstrip("/")
    return f"{base_url}/rest/api/1.0"


def get_repository(config: BitbucketConfig) -> dict[str, Any]:
    """Fetch repository metadata from Bitbucket Data Center."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}"
    return get_json(url, config)


def get_repository_restrictions(config: BitbucketConfig) -> dict[str, Any]:
    """Fetch branch restrictions from a Bitbucket Data Center repository."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    # Bitbucket Data Center Branch Permissions REST API:
    # search repository branch restrictions using the branch-permissions resource.
    # Atlassian documents this as REPO_ADMIN-gated even though this bridge only
    # performs a read-only GET.
    base_url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/branch-permissions/search"

    start = 0
    combined: dict[str, Any] = {
        "values": [],
        "paginated": True,
        "pages": [],
        "permission_required": "REPO_ADMIN",
    }

    while True:
        page = get_json(f"{base_url}?start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined


def list_open_issues(config: BitbucketConfig) -> dict[str, Any]:
    """Reject native Bitbucket issue listing for Data Center."""
    _ = config
    msg = "Bitbucket Data Center native issue reads are not supported; use linked Jira coverage instead."
    raise BitbucketError(msg)


def get_issue(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Reject native Bitbucket issue fetch for Data Center."""
    _ = (config, issue_id)
    msg = "Bitbucket Data Center native issue reads are not supported; use linked Jira coverage instead."
    raise BitbucketError(msg)


def get_issue_comments(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Reject native Bitbucket issue comment fetch for Data Center."""
    _ = (config, issue_id)
    msg = "Bitbucket Data Center native issue comments are not supported; use linked Jira coverage instead."
    raise BitbucketError(msg)


def get_issue_attachments(config: BitbucketConfig, issue_id: str) -> dict[str, Any]:
    """Reject native Bitbucket issue attachment fetch for Data Center."""
    _ = (config, issue_id)
    msg = (
        "Bitbucket Data Center native issue attachments are not supported; use linked Jira coverage instead."
    )
    raise BitbucketError(msg)


def list_open_pull_requests(config: BitbucketConfig) -> dict[str, Any]:
    """List all open pull requests from Bitbucket Data Center."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    base_url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests"

    start = 0
    combined: dict[str, Any] = {
        "values": [],
        "paginated": True,
        "pages": [],
    }

    while True:
        page = get_json(f"{base_url}?state=OPEN&start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined


def get_pull_request(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch one pull request from Bitbucket Data Center."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}"
    return get_json(url, config)


def get_pull_request_commits(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch commits from a Bitbucket Data Center pull request."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    base_url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/commits"

    start = 0
    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    while True:
        page = get_json(f"{base_url}?start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined


def get_pull_request_diff(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch the unified diff for a Bitbucket Data Center pull request."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/diff"
    response = get_text(url, config, accept="text/plain")

    return {
        "pull_request_id": pull_request_id,
        "body": response["body"],
        "content_type": response["content_type"],
        "url": response["url"],
    }


def get_pull_request_merge_status(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Test whether a Bitbucket Data Center pull request can be merged."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/merge"
    return get_json(url, config)


def get_pull_request_merge_checks(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch read-only merge-check context for a Bitbucket Data Center pull request."""
    merge_status = get_pull_request_merge_status(config, pull_request_id)
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
        "merge": merge_status,
        "status": status,
        "reviews": reviews,
    }


def get_pull_request_status(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch build statuses for the source commit of a Bitbucket Data Center pull request."""
    pull_request = get_pull_request(config, pull_request_id)
    commit = _pull_request_source_commit(pull_request)
    commit_id = quote_path(commit)

    base_url = f"{require(config.base_url, 'BITBUCKET_BASE_URL').rstrip('/')}/rest/build-status/1.0/commits/{commit_id}"

    start = 0
    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "commit": commit,
        "values": [],
        "paginated": True,
        "pages": [],
        "pull_request": pull_request,
    }

    while True:
        page = get_json(f"{base_url}?start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined


def get_pull_request_reviews(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch review-state activity for a Bitbucket Data Center pull request."""
    pull_request = get_pull_request(config, pull_request_id)

    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    base_url = (
        f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/activities"
    )

    start = 0
    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "pull_request": pull_request,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    while True:
        page = get_json(f"{base_url}?start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined


def _pull_request_source_commit(raw: dict[str, Any]) -> str:
    """Return the Bitbucket Data Center source commit hash for a pull request."""
    from_ref = raw.get("fromRef")
    if isinstance(from_ref, dict):
        latest_commit = from_ref.get("latestCommit")
        if isinstance(latest_commit, str) and latest_commit:
            return latest_commit

    msg = "Bitbucket Data Center pull request response did not include fromRef.latestCommit"
    raise BitbucketError(msg)


# Bitbucket Data Center exposes PR comments through the broader activities feed.
# We fetch the paginated feed here and filter comment-bearing activities during
# normalization so review/merge/rescope lifecycle events are not exposed as
# discussion comments.
def get_pull_request_discussion(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch pull request activities from Bitbucket Data Center."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    base_url = (
        f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/activities"
    )

    start = 0
    combined: dict[str, Any] = {
        "pull_request_id": pull_request_id,
        "values": [],
        "paginated": True,
        "pages": [],
    }

    while True:
        page = get_json(f"{base_url}?start={start}", config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        if page.get("isLastPage") is True:
            break

        next_start = page.get("nextPageStart")
        if not isinstance(next_start, int):
            break

        if next_start <= start:
            break

        start = next_start

    return combined
