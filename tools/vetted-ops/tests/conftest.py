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

from collections.abc import Callable
from pathlib import Path

import pytest

from vetted_ops.config import DEFAULT_RELATIVE_PATH

Discovered = Callable[[Callable[[list[str]], int], list[str], Path], int]


@pytest.fixture()
def discovered(monkeypatch: pytest.MonkeyPatch) -> Discovered:
    """Run an entry point against ``cfg_path`` found by discovery, not `--config`.

    The write entry points refuse `--config` whenever an operation runs, so a
    test that executes one installs the policy at the committed path in its own
    directory and runs from there, the way an adopter's checkout does.
    """

    def run(main: Callable[[list[str]], int], argv: list[str], cfg_path: Path) -> int:
        root = cfg_path.parent
        target = root / DEFAULT_RELATIVE_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cfg_path.read_bytes())
        monkeypatch.chdir(root)
        return main(argv)

    return run
