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
"""Tests for ``check-symlink-links.py``, on a small tree with a symlinked directory."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "check-symlink-links.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_symlink_links", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # the dataclass looks its module up there
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """``plugins/fam/skills/demo/`` is real; ``skills/demo`` links to it; ``docs/`` links into both."""
    real = tmp_path / "plugins" / "fam" / "skills" / "demo"
    real.mkdir(parents=True)
    (real / "SKILL.md").write_text("# Demo\n")
    (real / "notes.md").write_text("# Notes\n")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "demo").symlink_to(Path("..") / "plugins" / "fam" / "skills" / "demo")
    (tmp_path / "docs").mkdir()
    (tmp_path / "real-file.md").write_text("x\n")
    (tmp_path / "file-link.md").symlink_to("real-file.md")
    return tmp_path


def check(tree: Path, text: str):
    return mod.check_text(text, tree / "docs" / "page.md", tree)


def test_a_link_through_a_symlinked_directory_is_reported(tree: Path) -> None:
    findings, fixed = check(tree, "See [demo](../skills/demo/SKILL.md).\n")
    assert [(f.line, f.target, f.symlink) for f in findings] == [
        (1, "../skills/demo/SKILL.md", "skills/demo")
    ]
    assert fixed == "See [demo](../plugins/fam/skills/demo/SKILL.md).\n"


def test_the_real_path_is_left_alone(tree: Path) -> None:
    text = "See [demo](../plugins/fam/skills/demo/SKILL.md).\n"
    assert check(tree, text) == ([], text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("[a](../skills/demo/SKILL.md#step-2)\n", "[a](../plugins/fam/skills/demo/SKILL.md#step-2)\n"),
        ("![img](../skills/demo/notes.md)\n", "![img](../plugins/fam/skills/demo/notes.md)\n"),
        ('[a](../skills/demo/SKILL.md "title")\n', '[a](../plugins/fam/skills/demo/SKILL.md "title")\n'),
        ("[a](<../skills/demo/SKILL.md>)\n", "[a](<../plugins/fam/skills/demo/SKILL.md>)\n"),
        ("[ref]: ../skills/demo/SKILL.md\n", "[ref]: ../plugins/fam/skills/demo/SKILL.md\n"),
        (
            '<a href="../skills/demo/SKILL.md">a</a>\n',
            '<a href="../plugins/fam/skills/demo/SKILL.md">a</a>\n',
        ),
        ("[dir](../skills/demo/)\n", "[dir](../plugins/fam/skills/demo/)\n"),
        (
            "[a](../skills/demo/SKILL.md) and [b](../skills/demo/notes.md)\n",
            "[a](../plugins/fam/skills/demo/SKILL.md) and [b](../plugins/fam/skills/demo/notes.md)\n",
        ),
    ],
)
def test_each_link_form_is_rewritten(tree: Path, text: str, expected: str) -> None:
    findings, fixed = check(tree, text)
    assert findings
    assert fixed == expected


@pytest.mark.parametrize(
    "text",
    [
        "```\n[a](../skills/demo/SKILL.md)\n```\n",
        "~~~md\n[a](../skills/demo/SKILL.md)\n~~~\n",
        "Use `[a](../skills/demo/SKILL.md)` as an example.\n",
        "[site](https://example.org/skills/demo/SKILL.md)\n",
        "[root](/skills/demo/SKILL.md)\n",
        "[anchor](#skills)\n",
        "[gone](../skills/missing/SKILL.md)\n",
        "[file symlink](../file-link.md)\n",
        "[outside](../../elsewhere/skills/demo/SKILL.md)\n",
    ],
)
def test_what_is_not_a_link_through_a_symlinked_directory_is_skipped(tree: Path, text: str) -> None:
    assert check(tree, text) == ([], text)


def test_a_fence_closes_only_on_its_own_marker(tree: Path) -> None:
    text = "````\n```\n[a](../skills/demo/SKILL.md)\n````\n[b](../skills/demo/SKILL.md)\n"
    findings, _ = check(tree, text)
    assert [f.line for f in findings] == [5]


def test_main_reports_and_fixes(
    tree: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    page = tree / "docs" / "page.md"
    page.write_text("See [demo](../skills/demo/SKILL.md).\n")
    monkeypatch.chdir(tree)
    assert mod.main(["docs/page.md"], tree) == 1
    out = capsys.readouterr()
    assert "docs/page.md:1:" in out.out
    assert "`skills/demo`" in out.out
    assert "--fix" in out.err
    assert mod.main(["--fix", "docs/page.md"], tree) == 0
    assert page.read_text() == "See [demo](../plugins/fam/skills/demo/SKILL.md).\n"
    assert mod.main(["docs/page.md"], tree) == 0


def test_the_repository_docs_have_no_such_links() -> None:
    # The files the prek hook covers, checked against the real tree.
    root = Path(__file__).resolve().parents[3]
    pages = sorted((root / "docs").rglob("*.md"))
    assert pages
    findings = [f for page in pages for f in mod.check_text(page.read_text(encoding="utf-8"), page, root)[0]]
    assert findings == []
