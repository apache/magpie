# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Tests for ``render-preflight-fixtures.py``.

Each test copies the real checker and the real `preflight-floor` suite into
``tmp_path``, so it exercises what the hook will actually run, and changes
only the copy. The point of each is the **red** case: the hook exists because
the suite once drifted silently from the checker, so a check that cannot fail
on a changed checker would be measuring nothing.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from types import ModuleType

import pytest

_HERE = Path(__file__).resolve().parents[1]
_REPO = _HERE.parents[1]
_SCRIPT = _HERE / "render-preflight-fixtures.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("render_preflight_fixtures", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()
FLOOR, WELCOME = mod.SUITES


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """The checker package and the suite, copied out of the real tree."""
    shutil.copytree(
        _REPO / mod.CHECKER / "setup_preflight",
        tmp_path / mod.CHECKER / "setup_preflight",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for suite in mod.SUITES:
        shutil.copytree(_REPO / suite, tmp_path / suite)
    return tmp_path


def test_committed_suite_matches_the_checker(repo: Path) -> None:
    assert mod.main(["--check", "--repo-root", str(repo)]) == 0


def test_a_changed_rule_makes_the_suite_stale(repo: Path) -> None:
    section = repo / mod.CHECKER / "setup_preflight/sections/step-7.md"
    section.write_text(section.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8")

    assert mod.main(["--check", "--repo-root", str(repo)]) == 1
    # Rendering repairs it, and leaves the suite clean for the next check.
    assert mod.main(["--repo-root", str(repo)]) == 1
    assert mod.main(["--check", "--repo-root", str(repo)]) == 0
    report = repo / FLOOR / "case-6-unadopted/report.md"
    assert "A new rule." in report.read_text(encoding="utf-8")


def test_a_changed_state_makes_its_case_stale(repo: Path) -> None:
    state_file = repo / FLOOR / "case-2-below-floor/state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["plugins"] = [["magpie-setup", "0.3.0"], ["magpie-pr-management", "0.3.0"]]
    state_file.write_text(json.dumps(state), encoding="utf-8")

    assert mod.main(["--check", "--repo-root", str(repo)]) == 1


def test_a_case_without_state_is_refused(repo: Path) -> None:
    (repo / FLOOR / "case-9-new").mkdir()
    assert mod.main(["--check", "--repo-root", str(repo)]) == 1


def test_render_keeps_the_prose_and_is_idempotent() -> None:
    once = mod.render_report("Some state.\n", '{"verdict": "ok"}')
    assert once.startswith("Some state.\n")
    assert mod.render_report(once, '{"verdict": "ok"}') == once


def test_a_changed_welcome_rule_makes_the_welcome_check_suite_stale(repo: Path) -> None:
    """The `setup` skill's own welcome check is rendered from the real checker too."""
    section = repo / mod.CHECKER / "setup_preflight/sections/welcome.md"
    section.write_text(section.read_text(encoding="utf-8") + "\nA new rule.\n", encoding="utf-8")

    assert mod.main(["--repo-root", str(repo)]) == 1
    assert mod.main(["--check", "--repo-root", str(repo)]) == 0
    texts = [r.read_text(encoding="utf-8") for r in sorted((repo / WELCOME).glob("case-*/report.md"))]
    assert texts and all(mod.WELCOME_MARKER in text for text in texts)
    assert any("A new rule." in text for text in texts)


def test_an_unknown_check_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="check"):
        mod.run_checker({"check": "everything", "plugins": []}, _REPO, tmp_path)
