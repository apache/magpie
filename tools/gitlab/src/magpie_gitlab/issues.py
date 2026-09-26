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

import urllib.parse
from typing import Any

from .client import GitLabConfig, get_json, get_paged_json, quote_path


def list_issues(
    project: str,
    config: GitLabConfig,
    state: str = "opened",
    limit: int | None = None,
) -> list[Any]:
    query = urllib.parse.urlencode({"state": state})
    url = f"{config.instance_url}/api/v4/projects/{quote_path(project)}/issues?{query}"
    return get_paged_json(url, config, limit=limit)


def get_issue(project: str, issue_iid: int | str, config: GitLabConfig) -> Any:
    url = f"{config.instance_url}/api/v4/projects/{quote_path(project)}/issues/{quote_path(str(issue_iid))}"
    return get_json(url, config)
