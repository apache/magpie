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

"""Tests for the harness-neutral posture check (sandbox_lint.posture)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sandbox_lint import main
from sandbox_lint.posture import PostureViolation, check_posture_violations, find_framework_root

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]


def _plant_agent_iso(root: Path) -> Path:
    p = root / "tools" / "agent-isolation" / "agent-iso.sh"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/bash\n# stub\n")
    return p


def _plant_agent_guard(root: Path) -> Path:
    p = root / "tools" / "agent-guard" / "src" / "agent_guard" / "__init__.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# stub dispatch core\ndef dispatch(cmd, cwd): return None\n")
    return p


# ---------------------------------------------------------------------------
# check_posture_violations
# ---------------------------------------------------------------------------


def test_both_components_present_no_violations(tmp_path: Path) -> None:
    _plant_agent_iso(tmp_path)
    _plant_agent_guard(tmp_path)
    assert check_posture_violations(tmp_path) == []


def test_missing_agent_iso_yields_layer0_violation(tmp_path: Path) -> None:
    _plant_agent_guard(tmp_path)
    violations = check_posture_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0].layer == "layer-0"
    assert "clean-env" in violations[0].detail
    assert "agent-iso" in violations[0].detail


def test_missing_agent_guard_yields_layer3_violation(tmp_path: Path) -> None:
    _plant_agent_iso(tmp_path)
    violations = check_posture_violations(tmp_path)
    assert len(violations) == 1
    assert violations[0].layer == "layer-3"
    assert "action guard" in violations[0].detail
    assert "agent-guard" in violations[0].detail


def test_both_missing_yields_two_violations(tmp_path: Path) -> None:
    violations = check_posture_violations(tmp_path)
    assert len(violations) == 2
    layers = {v.layer for v in violations}
    assert layers == {"layer-0", "layer-3"}


def test_violation_is_frozen_dataclass() -> None:
    v = PostureViolation(layer="layer-0", detail="something missing")
    assert v.layer == "layer-0"
    with pytest.raises(Exception):
        # `setattr`: the write the type checkers reject is what is under test.
        setattr(v, "layer", "mutated")


# ---------------------------------------------------------------------------
# find_framework_root
# ---------------------------------------------------------------------------


def test_find_framework_root_locates_repo_root(tmp_path: Path) -> None:
    # Plant a tools/agent-isolation dir so the search terminates at tmp_path.
    (tmp_path / "tools" / "agent-isolation").mkdir(parents=True)
    # Search from a child directory.
    child = tmp_path / "a" / "b" / "c"
    child.mkdir(parents=True)
    assert find_framework_root(child) == tmp_path


def test_find_framework_root_falls_back_to_start(tmp_path: Path) -> None:
    # No tools/agent-isolation anywhere — should return the start path.
    result = find_framework_root(tmp_path)
    assert result == tmp_path


def test_find_framework_root_detects_adopter_snapshot(tmp_path: Path) -> None:
    # Adopter layout: the snapshot lives under .apache-magpie/. A bare
    # --any-harness from the repo root must resolve to the snapshot dir, not
    # fall back to the repo root (which would falsely report both layers
    # missing).
    snapshot = tmp_path / ".apache-magpie"
    (snapshot / "tools" / "agent-isolation").mkdir(parents=True)
    assert find_framework_root(tmp_path) == snapshot


def test_cli_any_harness_auto_detects_adopter_snapshot(tmp_path: Path) -> None:
    """Bare --any-harness from an adopter repo root passes when the snapshot is complete."""
    import os

    snapshot = tmp_path / ".apache-magpie"
    _plant_agent_iso(snapshot)
    _plant_agent_guard(snapshot)
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        assert main(["--any-harness"]) == 0
    finally:
        os.chdir(old_cwd)


def test_cli_opencode_and_any_harness_mutually_exclusive(tmp_path: Path) -> None:
    """Passing both --opencode and --any-harness is a usage error (SystemExit)."""
    with pytest.raises(SystemExit):
        main(["--opencode", str(tmp_path / "opencode.json"), "--any-harness"])


# ---------------------------------------------------------------------------
# CLI integration (--any-harness)
# ---------------------------------------------------------------------------


def test_cli_any_harness_ok_on_repo_root() -> None:
    """--any-harness on the actual Magpie repo returns 0 (both components present)."""
    rc = main(["--any-harness", str(REPO_ROOT)])
    assert rc == 0


def test_cli_any_harness_fails_on_empty_dir(tmp_path: Path) -> None:
    """--any-harness on an empty directory returns 1 (components missing)."""
    rc = main(["--any-harness", str(tmp_path)])
    assert rc == 1


def test_cli_any_harness_auto_detects_root() -> None:
    """--any-harness with no path auto-detects the framework root from CWD."""
    import os

    old_cwd = os.getcwd()
    try:
        os.chdir(REPO_ROOT)
        rc = main(["--any-harness"])
        assert rc == 0
    finally:
        os.chdir(old_cwd)


def test_cli_any_harness_partial_setup_fails(tmp_path: Path) -> None:
    """--any-harness with only one component still fails."""
    _plant_agent_iso(tmp_path)
    rc = main(["--any-harness", str(tmp_path)])
    assert rc == 1


def test_cli_any_harness_full_setup_passes(tmp_path: Path) -> None:
    _plant_agent_iso(tmp_path)
    _plant_agent_guard(tmp_path)
    rc = main(["--any-harness", str(tmp_path)])
    assert rc == 0
