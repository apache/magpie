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

"""Tests for `tools/dev/sync-forbidden-terms.py`."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[1] / "sync-forbidden-terms.py"
REPO_ROOT = Path(__file__).resolve().parents[3]
TARGET_TS = REPO_ROOT / "plugins" / "magpie-security" / "hooks" / "forbidden-terms.ts"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sync_forbidden_terms", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_terms_match_canonical_publication_terms() -> None:
    mod = _load()
    terms = mod.generate_terms_data()
    assert len(terms) >= 19
    names = {t["name"] for t in terms}
    assert "CVE id" in names
    assert "CVE" in names
    assert "vulnerability" in names
    assert "security fix" in names
    assert "advisory" in names
    assert "exploit" in names
    assert "SSRF" in names
    assert "buffer overflow" in names
    assert "use-after-free" in names


def test_sync_script_check_passes_on_current_tree() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"sync-forbidden-terms --check failed: {result.stderr}"


def test_sync_script_check_fails_on_ts_drift(tmp_path: Path, monkeypatch) -> None:
    mod = _load()
    fake_ts = tmp_path / "forbidden-terms.ts"
    fake_ts.write_text("// drifted\n", encoding="utf-8")

    monkeypatch.setattr(mod, "TARGET_TS", fake_ts)
    monkeypatch.setattr(sys, "argv", [str(_SCRIPT), "--check"])
    assert mod.main() == 1
