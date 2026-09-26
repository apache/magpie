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
from magpie_gitlab.pipelines import get_pipeline_status, list_mr_pipelines

from .conftest import build_mock_response


def test_get_pipeline_status(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response({"id": 1, "status": "success"})
    cfg = load_config()
    res = get_pipeline_status("group/project", 1, cfg)
    assert res["status"] == "success"
    req = mock_urlopen.call_args[0][0]
    assert req.full_url == "https://gitlab.example.com/api/v4/projects/group%2Fproject/pipelines/1"


def test_list_mr_pipelines(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1, "status": "success"}])
    cfg = load_config()
    res = list_mr_pipelines("group/project", 1, cfg)
    assert len(res) == 1
    req = mock_urlopen.call_args[0][0]
    assert (
        req.full_url
        == "https://gitlab.example.com/api/v4/projects/group%2Fproject/merge_requests/1/pipelines?per_page=100"
    )


def test_list_mr_pipelines_limit(mock_urlopen, mock_env):
    mock_urlopen.return_value = build_mock_response([{"id": 1}, {"id": 2}])
    cfg = load_config()
    res = list_mr_pipelines("group/project", 1, cfg, limit=2)
    assert len(res) == 2
