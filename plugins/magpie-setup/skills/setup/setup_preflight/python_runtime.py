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
"""Whether uv has the Python the framework's tools require.

The tools run through `uv`, which fetches a missing interpreter on first use.
Under the secure setup it cannot: uv installs interpreters into
`~/.local/share/uv/python`, which the sandbox can read but never write (an
interpreter there also runs outside the sandbox, so a sandbox-written one
would be a way out). The first tool run then fails with "Permission denied".
Checked at every skill start, so the user installs it once, in their own
terminal, before a tool needs it.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

from .core import Finding

#: The Python the framework's uv-run tools require: the workspace's root
#: `.python-version` (a test keeps the two in step).
REQUIRED_PYTHON = "3.14"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def findings(
    which: Callable[[str], str | None] = shutil.which, run: Runner = subprocess.run
) -> list[Finding]:
    """A `python-missing` finding when uv can find no Python `REQUIRED_PYTHON`.

    `uv python find` only looks: it reads the interpreters uv manages and the
    ones on `PATH`, downloads nothing and writes nothing, so it works inside the
    sandbox. Without uv on `PATH` there is nothing to ask, and other checks
    report a missing uv.
    """
    uv = which("uv")
    if uv is None:
        return []
    try:
        done = run(
            [uv, "python", "find", "--no-project", REQUIRED_PYTHON],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if done.returncode == 0:
        return []
    return [Finding("machine", "python-missing", "python-missing", {"version": REQUIRED_PYTHON})]
