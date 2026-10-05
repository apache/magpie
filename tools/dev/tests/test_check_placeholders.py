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

"""Tests for ``check-placeholders.sh``, run as a CLI against a miniature repository."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "check-placeholders.sh"


def test_reports_forbidden_pattern_in_symlinked_skill(tmp_path: Path) -> None:
    # The real layout: skills/<flat> is a symlink into the plugin that ships it.
    real = tmp_path / "plugins" / "magpie-x" / "skills" / "alias"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("Clone apache/airflow first.\n", encoding="utf-8")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "x-flat").symlink_to(
        Path("..", "plugins", "magpie-x", "skills", "alias"), target_is_directory=True
    )

    # The script scans from the git top level, else from the working directory;
    # the ceiling stops git from finding a repository above the fixture.
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        cwd=tmp_path,
        env={**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path.parent)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "skills/x-flat/SKILL.md:1:Clone apache/airflow first." in result.stderr
