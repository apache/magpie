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
"""Import-order regression guard: decisions.py -> policy.py -> policy_shape.py, one-way only.

I6 (review findings round 1) replaced a bottom-of-file circular import
between ``policy.py`` and ``decisions.py`` with a strictly one-way
dependency chain. A fresh subprocess import of either module, on its own
(nothing else in the package imported first), is the only way to catch a
regression back to that circularity: within a single test process, whichever
module a prior test imported first is already cached in ``sys.modules``, so
the failure mode a circular import produces never surfaces there.
"""

from __future__ import annotations

import subprocess
import sys


def _import_in_fresh_subprocess(module: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_decisions_module_imports_standalone() -> None:
    result = _import_in_fresh_subprocess("container_gateway.decisions")
    assert result.returncode == 0, result.stderr


def test_policy_module_imports_standalone() -> None:
    result = _import_in_fresh_subprocess("container_gateway.policy")
    assert result.returncode == 0, result.stderr
