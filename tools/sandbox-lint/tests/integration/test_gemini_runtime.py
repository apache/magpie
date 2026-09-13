# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0

"""Opt-in integration tests using the installed Gemini runtime, without a model.

MAGPIE_GEMINI_BUNDLE selects a Gemini 0.59.0 bundle directory. The JavaScript helper is
only an ESM bridge to upstream APIs; pytest owns discovery, skips, and failures.
MAGPIE_GEMINI_SANDBOX_TEST=1 additionally permits live Linux namespace creation.
Neither test installs Gemini, logs in, or reads the operator's credentials.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HELPER = Path(__file__).with_name("gemini_runtime.mjs")


@pytest.fixture
def gemini_runtime() -> tuple[str, str]:
    bundle = os.environ.get("MAGPIE_GEMINI_BUNDLE")
    if not bundle:
        pytest.skip("set MAGPIE_GEMINI_BUNDLE to test an installed Gemini 0.59.0 runtime")
    node = shutil.which("node")
    assert node, "Node.js is required for the requested Gemini integration tests"
    assert Path(bundle).is_dir(), f"Gemini bundle directory does not exist: {bundle}"
    return node, str(Path(bundle).resolve())


def _run(gemini_runtime: tuple[str, str], *args: str) -> str:
    node, bundle = gemini_runtime
    result = subprocess.run([node, str(HELPER), bundle, *args], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout, end="")
    return result.stdout


def test_native_policy_engine(gemini_runtime: tuple[str, str]) -> None:
    assert "native policy decisions passed" in _run(gemini_runtime)


@pytest.mark.skipif(
    sys.platform != "linux" or os.environ.get("MAGPIE_GEMINI_SANDBOX_TEST") != "1",
    reason="set MAGPIE_GEMINI_SANDBOX_TEST=1 on Linux to test live bubblewrap isolation",
)
def test_linux_sandbox(gemini_runtime: tuple[str, str]) -> None:
    output = _run(gemini_runtime, "--sandbox")
    assert "synthetic home outside workspace remains readable" in output
    assert "outside write and network blocked" in output
