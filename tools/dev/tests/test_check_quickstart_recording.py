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

"""Tests for ``check-quickstart-recording.py``.

Every test builds a miniature repository in ``tmp_path`` and runs one check
against it. The point of each is the **red** case: a gate that cannot fail is
worse than no gate, because a green run reads as evidence while measuring
nothing. So each check is exercised in both directions — the broken tree is
reported, and the corrected one is silent.

The staleness check is the one worth the most care. It is the whole reason the
renderer is byte-deterministic, and it is the only thing standing between an
authored screenshot and silent drift from its source, so it is tested by
actually mutating a rendered file rather than by asserting on a mock.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_HERE = Path(__file__).resolve().parents[1]
_SCRIPT = _HERE / "check-quickstart-recording.py"
_RENDERER = _HERE / "render-screenshot.sh"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_quickstart_recording", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()

LICENCE = "Licensed to the Apache Software Foundation"
TRANSCRIPT = "> /magpie-pairing:self-review\n\n  Nothing was sent.\n"


def _skill(repo: Path, name: str, family: str) -> None:
    """A skill in the flat tree, and the plugin directory that ships it."""
    d = repo / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\nfamily: {family}\n---\n", encoding="utf-8")


def _alias(repo: Path, family: str, alias: str) -> None:
    (repo / "plugins" / f"magpie-{family}" / "skills" / alias).mkdir(parents=True, exist_ok=True)


def _svg(path: Path, *, licence: bool = True, valid: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f"<!--\n  {LICENCE}\n-->\n" if licence else ""
    body = '<svg xmlns="http://www.w3.org/2000/svg"></svg>\n' if valid else "<svg>\n"
    path.write_text(header + body, encoding="utf-8")


def _render(repo: Path, txt: Path) -> None:
    """Render through the real script, so a test tree matches a real one."""
    subprocess.run(
        ["bash", str(_RENDERER), str(txt.relative_to(repo))],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Iterator[Path]:
    """A miniature repo, cd'd into — the script resolves paths relative to cwd.

    One family, one skill, one screenshot, and the setup recording: the
    smallest tree the checker calls complete.
    """
    (tmp_path / "tools" / "dev").mkdir(parents=True)
    (tmp_path / "tools" / "dev" / "render-screenshot.sh").symlink_to(_RENDERER)

    _skill(tmp_path, "pairing-self-review", "pairing")
    _alias(tmp_path, "pairing", "self-review")

    shots = tmp_path / "assets" / "quickstart" / "families" / "pairing"
    shots.mkdir(parents=True)
    (shots / "self-review.txt").write_text(TRANSCRIPT, encoding="utf-8")

    _svg(tmp_path / "assets" / "quickstart" / "magpie-setup.svg")

    (tmp_path / "docs" / "pairing").mkdir(parents=True)
    (tmp_path / "docs" / "pairing" / "README.md").write_text(
        "![a run](../../assets/quickstart/families/pairing/self-review.svg)\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "quick-start.md").write_text(
        "![setup](assets/quickstart/magpie-setup.svg)\n", encoding="utf-8"
    )

    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        _render(tmp_path, shots / "self-review.txt")
        yield tmp_path
    finally:
        os.chdir(cwd)


def test_a_complete_tree_is_silent(repo: Path) -> None:
    assert mod.main() == 0


# ---------------------------------------------------------------------------
# Pairing: a transcript and its rendered SVG travel together
# ---------------------------------------------------------------------------


def test_a_transcript_with_no_svg_is_reported(repo: Path) -> None:
    (repo / "assets/quickstart/families/pairing/self-review.svg").unlink()
    errs = mod.check_screenshots(["pairing"])
    assert any("self-review.svg" in e and "missing" in e for e in errs)


def test_an_svg_with_no_transcript_is_reported(repo: Path) -> None:
    _svg(repo / "assets/quickstart/families/pairing/orphan.svg")
    errs = mod.check_screenshots(["pairing"])
    assert any("orphan.svg" in e and "no transcript" in e for e in errs)


# ---------------------------------------------------------------------------
# Staleness: the guard a hand-authored image cannot have
# ---------------------------------------------------------------------------


def test_an_svg_that_no_longer_matches_its_transcript_is_reported(repo: Path) -> None:
    svg = repo / "assets/quickstart/families/pairing/self-review.svg"
    svg.write_text(svg.read_text().replace("Nothing was sent.", "Everything was sent."))
    errs = mod.check_regenerates()
    assert any("stale" in e for e in errs), errs


def test_editing_the_transcript_alone_is_reported(repo: Path) -> None:
    """The direction that actually happens: someone fixes a line in the .txt
    and forgets to re-render."""
    txt = repo / "assets/quickstart/families/pairing/self-review.txt"
    txt.write_text(TRANSCRIPT + "  One more line.\n", encoding="utf-8")
    assert any("stale" in e for e in mod.check_regenerates())


def test_re_rendering_clears_the_staleness(repo: Path) -> None:
    txt = repo / "assets/quickstart/families/pairing/self-review.txt"
    txt.write_text(TRANSCRIPT + "  One more line.\n", encoding="utf-8")
    _render(repo, txt)
    assert mod.check_regenerates() == []


# ---------------------------------------------------------------------------
# Coverage and naming
# ---------------------------------------------------------------------------


def test_a_family_with_no_screenshots_is_reported(repo: Path) -> None:
    _skill(repo, "security-issue-triage", "security")
    _alias(repo, "security", "issue-triage")
    errs = mod.check_screenshots(["pairing", "security"])
    assert any("security" in e and "no screenshots" in e for e in errs)


def test_a_screenshot_directory_no_family_claims_is_reported(repo: Path) -> None:
    (repo / "assets/quickstart/families/ghost").mkdir()
    errs = mod.check_screenshots(["pairing"])
    assert any("ghost" in e for e in errs)


def test_a_screenshot_naming_a_skill_the_family_does_not_ship_is_reported(repo: Path) -> None:
    shots = repo / "assets/quickstart/families/pairing"
    (shots / "not-a-skill.txt").write_text(TRANSCRIPT, encoding="utf-8")
    _render(repo, shots / "not-a-skill.txt")
    errs = mod.check_screenshots(["pairing"])
    assert any("not-a-skill" in e and "ships no skill" in e for e in errs)


def test_a_screenshot_the_readme_does_not_embed_is_reported(repo: Path) -> None:
    (repo / "docs/pairing/README.md").write_text("no images here\n", encoding="utf-8")
    errs = mod.check_screenshots(["pairing"])
    assert any("does not embed" in e for e in errs)


# ---------------------------------------------------------------------------
# The SVG itself
# ---------------------------------------------------------------------------


def test_an_svg_without_the_licence_header_is_reported(repo: Path) -> None:
    path = repo / "assets/quickstart/magpie-setup.svg"
    _svg(path, licence=False)
    assert any("licence header" in e for e in mod.check_svg(path))


def test_an_unparsable_svg_is_reported(repo: Path) -> None:
    path = repo / "assets/quickstart/magpie-setup.svg"
    _svg(path, valid=False)
    assert any("not parsable" in e for e in mod.check_svg(path))


def test_an_oversized_svg_is_reported(repo: Path) -> None:
    path = repo / "assets/quickstart/magpie-setup.svg"
    _svg(path)
    path.write_text(path.read_text() + "<!--" + "x" * (mod.MAX_BYTES + 1) + "-->")
    assert any("exceeds" in e for e in mod.check_svg(path))


# ---------------------------------------------------------------------------
# Retirement: three sets are gone and must stay gone
# ---------------------------------------------------------------------------


def test_a_surviving_first_run_recording_is_reported(repo: Path) -> None:
    _svg(repo / "assets/quickstart/families/pairing-first-run.svg")
    assert any("first-run" in e for e in mod.check_no_retired_references())


def test_a_doc_referencing_a_first_run_recording_is_reported(repo: Path) -> None:
    (repo / "docs/pairing/README.md").write_text(
        "![old](../../assets/quickstart/families/pairing-first-run.svg)\n", encoding="utf-8"
    )
    assert any("retired asset" in e for e in mod.check_no_retired_references())


def test_a_revived_examples_directory_is_reported(repo: Path) -> None:
    (repo / "assets/examples").mkdir(parents=True)
    assert any("assets/examples" in e for e in mod.check_no_retired_references())


def test_a_new_png_still_is_reported(repo: Path) -> None:
    (repo / "assets/quickstart/install.png").write_bytes(b"\x89PNG\r\n")
    assert any("install.png" in e for e in mod.check_no_retired_references())


def test_a_design_document_may_name_what_was_retired(repo: Path) -> None:
    """A design records what was replaced. Rewriting the record to satisfy a
    linter would make it wrong."""
    designs = repo / "docs" / "designs"
    designs.mkdir(parents=True)
    (designs / "2026-01-01-x.md").write_text(
        "the nine assets/quickstart/families/pairing-first-run.svg files are gone\n",
        encoding="utf-8",
    )
    assert mod.check_no_retired_references() == []


# ---------------------------------------------------------------------------
# The one real recording
# ---------------------------------------------------------------------------


def test_the_quick_start_must_embed_the_recording(repo: Path) -> None:
    (repo / "docs/quick-start.md").write_text("no recording here\n", encoding="utf-8")
    errs = mod.check_embedded(Path("docs/quick-start.md"), mod.SETUP_RECORDING)
    assert any("does not embed" in e for e in errs)


def test_a_missing_recording_is_an_error_not_a_note(repo: Path) -> None:
    """There is no placeholder state any more: one recording is a thing a
    person does once."""
    (repo / "assets/quickstart/magpie-setup.svg").unlink()
    assert any("missing" in e for e in mod.check_svg(mod.SETUP_RECORDING))
