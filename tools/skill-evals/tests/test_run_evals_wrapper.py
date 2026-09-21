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

"""Tests for the argument gate in magpie-run-evals.sh.

`sandbox.excludedCommands` names this wrapper, so whatever it runs, runs
outside the sandbox. The gate is what keeps that exclusion narrow, and it
has to constrain where the argument *leads*, not only how it is spelled.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

WRAPPER = Path(__file__).resolve().parent.parent / "magpie-run-evals.sh"
EVALS_REL = "tools/skill-evals/evals"


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(WRAPPER), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / EVALS_REL).mkdir(parents=True)
    return root


def test_rejects_a_target_symlinked_outside_the_evals_tree(tmp_path: Path) -> None:
    """A symlink satisfies the spelling check and still points anywhere.

    `-d` follows it, so without resolution the runner is handed a directory
    outside the repository and reads it unsandboxed.
    """
    root = _fake_repo(tmp_path)
    outside = tmp_path / "secrets"
    outside.mkdir()
    (outside / "id_rsa").write_text("PRIVATE KEY MATERIAL")
    (root / EVALS_REL / "sneaky").symlink_to(outside)

    result = _run(root, f"{EVALS_REL}/sneaky")

    assert result.returncode == 2, result.stdout + result.stderr
    assert "PRIVATE KEY MATERIAL" not in result.stdout


def test_rejects_a_target_outside_the_evals_tree(tmp_path: Path) -> None:
    """The existing spelling check, pinned so the new gate cannot loosen it."""
    root = _fake_repo(tmp_path)
    result = _run(root, "/etc")
    assert result.returncode == 2


def test_rejects_more_than_one_argument(tmp_path: Path) -> None:
    """The exclusion rests on the one-argument, no-flags shape."""
    root = _fake_repo(tmp_path)
    result = _run(root, f"{EVALS_REL}", "--verbose")
    assert result.returncode == 2


def test_lets_a_real_path_inside_the_evals_tree_through(tmp_path: Path) -> None:
    """The gate must not cost the normal case.

    A genuine directory under `evals/` reaches the runner, which then exits
    on its own terms (no cases here) rather than on the gate's — so this
    pins "allowed through" without invoking `claude -p`.
    """
    root = _fake_repo(tmp_path)
    (root / EVALS_REL / "some-skill").mkdir()

    result = _run(root, f"{EVALS_REL}/some-skill")

    assert result.returncode != 2, result.stdout + result.stderr
    assert "resolves outside" not in result.stderr
