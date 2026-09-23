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

import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

HARNESS_MARKERS = ("CLAUDECODE", "GEMINI_CLI", "CODEX_SANDBOX", "CODEX_THREAD_ID", "COPILOT_CLI")


@pytest.fixture(autouse=True)
def _clean_harness_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests must not see the harness that happens to be running them."""
    for var in HARNESS_MARKERS:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def stub_bin(tmp_path: Path) -> tuple[Path, Callable[[str, str], Path]]:
    """A directory for fake CLIs; ``make(name, python_body)`` writes one."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    def make(name: str, body: str) -> Path:
        path = bin_dir / name
        path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        path.chmod(0o755)
        return path

    return bin_dir, make


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A repo on branch ``change``, one commit ahead of ``main``, touching app.py."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.org")
    git("config", "user.name", "T")
    git("config", "commit.gpgsign", "false")
    git("config", "core.hooksPath", "/dev/null")
    (repo / "app.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    git("add", "app.py")
    git("commit", "-q", "-m", "base")
    git("checkout", "-q", "-b", "change")
    (repo / "app.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    git("commit", "-q", "-am", "change")
    return repo
