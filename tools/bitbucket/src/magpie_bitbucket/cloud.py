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

from magpie_bitbucket.client import BitbucketConfig, get_json, quote_path, require

CLOUD_API_BASE = "https://api.bitbucket.org/2.0"


def get_repository(config: BitbucketConfig) -> dict[str, Any]:
    """Fetch repository metadata from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}"
    return get_json(url, config)


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

    while url:
        page = get_json(url, config)
        combined["pages"].append(page)

        values = page.get("values")
        if isinstance(values, list):
            combined["values"].extend(item for item in values if isinstance(item, dict))

        next_url = page.get("next")
        url = next_url if isinstance(next_url, str) else ""

    return combined


def get_pull_request(config: BitbucketConfig, pull_request_id: str) -> dict[str, Any]:
    """Fetch one pull request from Bitbucket Cloud."""
    workspace = quote_path(require(config.workspace, "BITBUCKET_WORKSPACE"))
    repo_slug = quote_path(require(config.repo_slug, "BITBUCKET_REPO_SLUG"))
    pr_id = quote_path(pull_request_id)
    url = f"{CLOUD_API_BASE}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}"
    return get_json(url, config)
