#
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

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_project_resolves_outside_the_workspace():
    """The plugin runs via `uvx --from <plugin>/tools/adversarial-review`, where
    the workspace root's sources do not exist; any dev group or uv source breaks it."""
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []
    assert "dependency-groups" not in data
    assert "sources" not in data.get("tool", {}).get("uv", {})


def test_console_script_is_declared():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["scripts"] == {"adversarial-review": "adversarial_review:main"}
