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

"""The workspace static-check hooks must fire on every workspace member.

The hooks discover their members from the root ``pyproject.toml`` and run the
check across all of them, so the ``files:`` filter only decides when to start.
A filter that names only ``tools/`` leaves the ``plugins`` and ``ai-tutors``
members unchecked on a pull request, which is how a formatting break reached
``main`` in #2201.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

HOOKS = ("workspace-ruff-check", "workspace-ruff-format", "workspace-mypy")

# One path per member and per shape the filter has to recognise: Python at the
# member root, Python inside a skill, a test, and the member's own config.
MEMBER_PATHS = (
    "plugins/pyproject.toml",
    "plugins/magpie-setup/skills/setup/scripts/example.py",
    "plugins/magpie-setup/skills/setup/tests/test_example.py",
    "ai-tutors/pyproject.toml",
    "ai-tutors/inject-knowledge-base.py",
    "ai-tutors/test_inject_knowledge_base.py",
    "tools/dev/pyproject.toml",
    "tools/dev/src/magpie_dev/example.py",
    "tools/cve-tool-vulnogram/generate-cve-json/src/example.py",
)


def files_pattern(hook_id: str) -> str:
    text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    block = text.split(f"- id: {hook_id}\n", 1)[1].split("pass_filenames:", 1)[0]
    match = re.search(r"files: (.+)", block)
    assert match is not None
    return match.group(1)


def test_every_workspace_static_check_fires_on_every_member():
    for hook in HOOKS:
        pattern = files_pattern(hook)
        for path in MEMBER_PATHS:
            assert re.match(pattern, path), f"{hook} would skip {path}"
