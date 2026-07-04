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

from magpie_bitbucket.client import BitbucketConfig, get_json, quote_path, require


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

        start = next_start

    return combined


def get_pull_request(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch one pull request from Bitbucket Data Center."""
    project_key = quote_path(require(config.project_key, "BITBUCKET_PROJECT_KEY"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{_api_base(config)}/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}"
    return get_json(url, config)
