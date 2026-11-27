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
"""Shared fixtures."""

from __future__ import annotations

import pytest

from security_management.shared import cve_tool


@pytest.fixture(autouse=True)
def _plugin_link_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render cve-tool commands as a plugin install would, whatever this host has."""
    monkeypatch.setattr(cve_tool, "stable_installed", lambda: True)


@pytest.fixture(autouse=True)
def _no_project_config(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Run each test from an empty directory, so `title_product_prefix`, when no
    input names it, never resolves through the project the suite is run from."""
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
