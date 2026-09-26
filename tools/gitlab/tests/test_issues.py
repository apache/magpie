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

from magpie_gitlab.client import load_config
from magpie_gitlab.issues import get_issue, list_issues

from .conftest import build_mock_response


def test_list_issues(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1, "title": "Issue 1"}])
    cfg = load_config()
    res = list_issues("group/project", cfg)
    assert len(res) == 1
    assert res[0]["title"] == "Issue 1"

    req = mock_urlopen.call_args[0][0]
    assert (
        req.full_url
        == "https://gitlab.example.com/api/v4/projects/group%2Fproject/issues?state=opened&per_page=100"
    )


def test_list_issues_limit(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1}, {"id": 2}])
    cfg = load_config()
    res = list_issues("group/project", cfg, limit=2)
    assert len(res) == 2


def test_get_issue(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response({"id": 1, "title": "Issue 1"})
    cfg = load_config()
    res = get_issue("group/project", 1, cfg)
    assert res["id"] == 1

    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://gitlab.example.com/api/v4/projects/group%2Fproject/issues/1"
