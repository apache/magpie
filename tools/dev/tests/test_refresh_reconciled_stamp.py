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

"""Tests for ``refresh-reconciled-stamp.py``.

The rule under test: every skill is stamped at its current surface hash, except
the skills on the committed exclusion list; entries for skills that no longer
exist go away, and a listed name that no longer exists stops the run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "refresh-reconciled-stamp.py"

LOCK = """\
# .apache-magpie.lock — committed.

method: local
source: skills/

reconciled:
  version: 0.9.0.dev202610280340
  at:      2026-10-28
  skills:
    configured:                 sha256:old0000000000000
    renamed-away:               sha256:gone000000000000
"""


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("refresh_reconciled_stamp", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered first: the module's dataclasses resolve their annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _skill(root: Path, plugin: str, name: str, surface: str) -> None:
    path = root / "plugins" / plugin / "skills" / name / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"---\nname: {name}\nsurface_hash: {surface}\n---\n\n# {name}\n", encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _skill(tmp_path, "magpie-a", "configured", "sha256:new0000000000000")
    _skill(tmp_path, "magpie-a", "declined", "sha256:decl000000000000")
    _skill(tmp_path, "magpie-b", "no-config", "sha256:free000000000000")
    _skill(tmp_path, "magpie-b", "a-very-long-skill-name-here", "sha256:long000000000000")
    excluded = tmp_path / "tools" / "dev" / "reconciled-stamp-excluded.txt"
    excluded.parent.mkdir(parents=True)
    excluded.write_text("# declined here\ndeclined  # no tracker config\n\n", encoding="utf-8")
    (tmp_path / ".apache-magpie.lock").write_text(LOCK, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "apache-magpie"\nversion = "0.9.0.dev202611100900"\n', encoding="utf-8"
    )
    return tmp_path


def test_stamps_all_but_currently_excluded(repo: Path) -> None:
    mod = _load()
    assert mod.main(["--root", str(repo), "--date", "2026-11-10"]) == 0
    text = (repo / ".apache-magpie.lock").read_text(encoding="utf-8")
    assert text.startswith("# .apache-magpie.lock — committed.\n\nmethod: local\nsource: skills/\n\n")
    assert "  version: 0.9.0.dev202611100900\n  at:      2026-11-10\n" in text
    assert "    configured:                 sha256:new0000000000000\n" in text
    assert "    no-config:                  sha256:free000000000000\n" in text
    # A name past the column still gets a separating space.
    assert "    a-very-long-skill-name-here: sha256:long000000000000\n" in text
    assert "declined" not in text
    assert "renamed-away" not in text


def test_result_lists_changes(repo: Path) -> None:
    mod = _load()
    lock = (repo / ".apache-magpie.lock").read_text(encoding="utf-8")
    result = mod.refresh(lock, mod.read_skills(repo), ["declined"], "0.9.0.dev1", "2026-11-10")
    assert result.excluded == ["declined"]
    assert result.dropped == ["renamed-away"]
    assert result.added == ["a-very-long-skill-name-here", "no-config"]
    assert result.moved == ["configured"]


def test_text_after_block_is_kept(repo: Path) -> None:
    mod = _load()
    lock = LOCK + "\nfloor:\n  min_version: 0.1.0\n"
    result = mod.refresh(lock, mod.read_skills(repo), ["declined"], "0.9.0.dev1", "2026-11-10")
    assert result.text.endswith("\nfloor:\n  min_version: 0.1.0\n")


def test_check_is_idempotent(repo: Path) -> None:
    mod = _load()
    assert mod.main(["--root", str(repo), "--check"]) == 1
    assert mod.main(["--root", str(repo), "--date", "2026-11-10"]) == 0
    # A later day changes only `at:`, which --check ignores.
    assert mod.main(["--root", str(repo), "--check", "--date", "2026-11-11"]) == 0


def test_missing_block_is_an_error(repo: Path) -> None:
    mod = _load()
    with pytest.raises(mod.StampError, match="no `reconciled:` block"):
        mod.refresh("method: local\n", mod.read_skills(repo), [], "0.9.0.dev1", "2026-11-10")


def test_unknown_excluded_name_is_an_error(repo: Path) -> None:
    mod = _load()
    lock = (repo / ".apache-magpie.lock").read_text(encoding="utf-8")
    with pytest.raises(mod.StampError, match="renamed-away"):
        mod.refresh(lock, mod.read_skills(repo), ["renamed-away"], "0.9.0.dev1", "2026-11-10")


def test_new_skill_is_stamped_not_excluded(repo: Path) -> None:
    mod = _load()
    _skill(repo, "magpie-c", "brand-new", "sha256:brandnew00000000")
    lock = (repo / ".apache-magpie.lock").read_text(encoding="utf-8")
    result = mod.refresh(lock, mod.read_skills(repo), ["declined"], "0.9.0.dev1", "2026-11-10")
    assert "brand-new" in result.added
