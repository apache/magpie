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

from pathlib import Path

import pytest

from skill_token_count import END, START, main, prepare_tokenizer, render, replace_block, vocabulary_path


@pytest.fixture(scope="session", autouse=True)
def installed_tokenizer() -> None:
    # Installation is explicit; measurement tests below must not fetch data.
    prepare_tokenizer()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "skills/hello").mkdir(parents=True)
    (tmp_path / "skills/hello/SKILL.md").write_text("hello world", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/mode-economics.md").write_text(f"Before\n{START}\n{END}\nAfter\n", encoding="utf-8")
    return tmp_path


def test_known_token_count_and_coverage(repo: Path) -> None:
    block = render(repo)
    assert "[hello](../skills/hello/SKILL.md) | 2 |" in block
    assert "1 of 1" in block
    assert "cl100k_base" in block


def test_check_never_writes_and_write_preserves_surroundings(repo: Path) -> None:
    target = repo / "docs/mode-economics.md"
    original = target.read_bytes()
    assert main(["--root", str(repo)]) == 1
    assert target.read_bytes() == original
    assert main(["--root", str(repo), "--write"]) == 0
    generated = target.read_bytes()
    assert generated.startswith(b"Before\n") and generated.endswith(b"\nAfter\n")
    assert main(["--root", str(repo), "--check"]) == 0
    assert main(["--root", str(repo), "--write"]) == 0
    assert target.read_bytes() == generated


@pytest.mark.parametrize("change", ["edit", "add", "delete", "rename"])
def test_source_drift(repo: Path, change: str) -> None:
    other = repo / "skills/other"
    other.mkdir()
    (other / "SKILL.md").write_text("another skill", encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 0
    target = repo / "skills/hello/SKILL.md"
    if change == "edit":
        # Same token count, different content must still invalidate provenance.
        target.write_text("hello earth", encoding="utf-8")
    elif change == "add":
        (repo / "skills/new").mkdir()
        (repo / "skills/new/SKILL.md").write_text("new", encoding="utf-8")
    elif change == "delete":
        target.unlink()
    else:
        target.parent.rename(repo / "skills/renamed")
    assert main(["--root", str(repo), "--check"]) == 1


def test_no_git_or_clock_dependency_and_line_endings(repo: Path) -> None:
    target = repo / "skills/hello/SKILL.md"
    target.write_bytes("Olá\n世界\n<|endoftext|>\n".encode())
    first = render(repo)
    target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    (repo / "unrelated.txt").write_text("unrelated", encoding="utf-8")
    assert render(repo) == first


def test_frontmatter_and_comments_are_measured(repo: Path) -> None:
    before = render(repo)
    target = repo / "skills/hello/SKILL.md"
    target.write_text("---\nname: hello\n---\n<!-- comment -->\nhello world", encoding="utf-8")
    assert render(repo) != before


def test_redirects_and_harness_copies_are_not_skills(repo: Path) -> None:
    before = render(repo)
    (repo / "skills/external").mkdir()
    (repo / "skills/external/source.md").write_text("redirect", encoding="utf-8")
    (repo / ".agents/skills").mkdir(parents=True)
    (repo / ".agents/skills/hello").symlink_to(repo / "skills/hello", target_is_directory=True)
    assert render(repo) == before


@pytest.mark.parametrize("document", ["missing", f"{START}{START}{END}", f"{END}{START}"])
def test_invalid_markers_fail_without_writing(repo: Path, document: str) -> None:
    target = repo / "docs/mode-economics.md"
    target.write_text(document, encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 2
    assert target.read_text(encoding="utf-8") == document


def test_symlinked_file_is_rejected(repo: Path) -> None:
    target = repo / "skills/hello/SKILL.md"
    target.unlink()
    target.symlink_to(repo / "docs/mode-economics.md")
    assert main(["--root", str(repo), "--write"]) == 2


def test_empty_catalogue_is_error(repo: Path) -> None:
    (repo / "skills/hello/SKILL.md").unlink()
    assert main(["--root", str(repo), "--write"]) == 2


def test_manual_table_tampering_is_detected(repo: Path) -> None:
    assert main(["--root", str(repo), "--write"]) == 0
    target = repo / "docs/mode-economics.md"
    target.write_text(target.read_text().replace("| 2 |", "| 999 |"), encoding="utf-8")
    assert main(["--root", str(repo)]) == 1


def test_only_one_block_is_replaced() -> None:
    assert replace_block(f"prefix{START}old{END}suffix", f"{START}new{END}") == f"prefix{START}new{END}suffix"


@pytest.mark.parametrize("corrupt", [False, True])
def test_cold_or_corrupt_cache_fails_before_network(
    repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    corrupt: bool,
) -> None:
    import requests

    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", str(tmp_path / "empty-cache"))
    if corrupt:
        cache = vocabulary_path()
        cache.parent.mkdir()
        cache.write_bytes(b"corrupt vocabulary")

    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("Measurement must not attempt a vocabulary download")

    monkeypatch.setattr(requests, "get", no_network)
    assert main(["--root", str(repo), "--check"]) == 2
    assert "--prepare-tokenizer" in capsys.readouterr().err


def test_prepared_cache_works_in_fresh_offline_process(repo: Path) -> None:
    import subprocess
    import sys

    script = """
from pathlib import Path
from unittest.mock import patch
from skill_token_count import render
import sys
with patch('requests.get', side_effect=AssertionError('unexpected network')):
    print(render(Path(sys.argv[1])))
"""
    result = subprocess.run([sys.executable, "-c", script, str(repo)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "| 2 |" in result.stdout


def test_measurement_date_is_preserved_until_content_changes(repo: Path) -> None:
    import re

    assert main(["--root", str(repo), "--write"]) == 0
    target = repo / "docs/mode-economics.md"
    dated = re.sub(r"Measured on \(UTC\): .*?\.", "Measured on (UTC): 2020-01-01.", target.read_text())
    target.write_text(dated, encoding="utf-8")
    assert main(["--root", str(repo), "--check"]) == 0
    assert main(["--root", str(repo), "--write"]) == 0
    assert target.read_text() == dated
    (repo / "skills/hello/SKILL.md").write_text("changed content", encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 0
    assert "2020-01-01" not in target.read_text()
