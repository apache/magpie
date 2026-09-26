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
from magpie_gitlab.merge_requests import get_mr, get_mr_commits, get_mr_diff, list_mrs

from .conftest import build_mock_response


def test_list_mrs(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1, "title": "MR 1"}])
    cfg = load_config()
    res = list_mrs("group/project", cfg)
    assert len(res) == 1
    req = mock_urlopen.call_args[0][0]
    assert (
        req.full_url
        == "https://gitlab.example.com/api/v4/projects/group%2Fproject/merge_requests?state=opened&per_page=100"
    )


def test_list_mrs_limit(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1}, {"id": 2}])
    cfg = load_config()
    res = list_mrs("group/project", cfg, limit=2)
    assert len(res) == 2


def test_get_mr(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response({"id": 1})
    cfg = load_config()
    res = get_mr("group/project", 1, cfg)
    assert res["id"] == 1
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://gitlab.example.com/api/v4/projects/group%2Fproject/merge_requests/1"


def test_get_mr_diff(mock_urlopen, mock_env):
    """MR diff must use the paginated /diffs endpoint."""
    mock_urlopen.return_value = build_mock_response([{"diff": "@@ -1 +1 @@\n-a\n+b", "new_path": "foo.py"}])
    cfg = load_config()
    res = get_mr_diff("group/project", 1, cfg)
    assert len(res) == 1
    assert res[0]["new_path"] == "foo.py"
    req = mock_urlopen.call_args[0][0]
    assert (
        req.full_url
        == "https://gitlab.example.com/api/v4/projects/group%2Fproject/merge_requests/1/diffs?per_page=100"
    )


def test_get_mr_diff_limit(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"diff": "chunk 1"}, {"diff": "chunk 2"}])
    cfg = load_config()
    res = get_mr_diff("group/project", 1, cfg, limit=2)
    assert len(res) == 2


def test_get_mr_commits(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": "abc"}])
    cfg = load_config()
    res = get_mr_commits("group/project", 1, cfg)
    assert len(res) == 1
    req = mock_urlopen.call_args[0][0]
    assert (
        req.full_url
        == "https://gitlab.example.com/api/v4/projects/group%2Fproject/merge_requests/1/commits?per_page=100"
    )
