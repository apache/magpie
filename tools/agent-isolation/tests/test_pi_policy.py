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

"""Run the Pi extension's policy tests (``pi/policy.test.ts``) under Node.

The policy module is TypeScript that imports nothing from Pi, so Node's type
stripping runs it directly. Node 22.18+ strips types by default; 22.6+ needs
``--experimental-strip-types``; anything older, or no Node, skips.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

TEST = Path(__file__).resolve().parents[1] / "pi" / "policy.test.ts"


def _node_args() -> list[str]:
    node = shutil.which("node")
    if node is None:
        return pytest.skip("node is not installed")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=False).stdout
    match = re.match(r"v(\d+)\.(\d+)", version.strip())
    if not match:
        return pytest.skip(f"cannot read the node version: {version!r}")
    major, minor = int(match[1]), int(match[2])
    if (major, minor) >= (22, 18):
        return [node]
    if (major, minor) >= (22, 6):
        return [node, "--experimental-strip-types"]
    # pytest.skip raises; returning it keeps every exit explicit.
    return pytest.skip(f"node {version.strip()} cannot strip TypeScript types")


def test_pi_policy_suite_passes() -> None:
    result = subprocess.run(
        [*_node_args(), "--test", str(TEST)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
