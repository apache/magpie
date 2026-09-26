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

import json
import urllib.request
from typing import Any
from unittest import mock

import pytest


@pytest.fixture
def mock_urlopen(monkeypatch):
    """Patch both urlopen and build_opener so the safe-redirect opener
    created inside get_json / get_paged_json goes through the same mock.
    """
    mock_open = mock.MagicMock()
    mock_opener = mock.MagicMock()
    mock_opener.open = mock_open
    monkeypatch.setattr(urllib.request, "urlopen", mock_open)
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *args, **kwargs: mock_opener,
    )
    return mock_open


def build_mock_response(
    json_data: Any,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> mock.MagicMock:
    body = json.dumps(json_data).encode("utf-8")
    resp = mock.MagicMock()
    resp.read.return_value = body
    resp.status = status
    _headers = headers if headers is not None else {}
    resp.headers = _headers
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = None
    return resp


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("GITLAB_TOKEN", "glpat-test123")
    monkeypatch.setenv("GITLAB_INSTANCE_URL", "https://gitlab.example.com")
