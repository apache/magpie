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

from skill_token_count import (
    FIELD,
    main,
    measure,
    offline_encoding,
    prepare_tokenizer,
    split_stamp,
    stamp,
    vocabulary_path,
)

SKILL = "---\nname: hello\nsurface_hash: sha256:0123456789abcdef\nlicense: Apache-2.0\n---\nhello world\n"


@pytest.fixture(scope="session", autouse=True)
def installed_tokenizer() -> None:
    # Installation is explicit; measurement tests below must not fetch data.
    prepare_tokenizer()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "skills/hello").mkdir(parents=True)
    (tmp_path / "skills/hello/SKILL.md").write_text(SKILL, encoding="utf-8")
    return tmp_path


def stamped_value(repo: Path, name: str = "hello") -> str | None:
    return split_stamp((repo / f"skills/{name}/SKILL.md").read_text(encoding="utf-8"))[1]


def test_check_never_writes_and_write_is_idempotent(repo: Path) -> None:
    target = repo / "skills/hello/SKILL.md"
    original = target.read_bytes()
    assert main(["--root", str(repo)]) == 1
    assert target.read_bytes() == original
    assert main(["--root", str(repo), "--write"]) == 0
    stamped = target.read_bytes()
    assert main(["--root", str(repo), "--check"]) == 0
    assert main(["--root", str(repo), "--write"]) == 0
    assert target.read_bytes() == stamped


def test_stamp_excludes_itself_so_writing_never_changes_the_count(repo: Path) -> None:
    encoder = offline_encoding()
    before = measure(SKILL, encoder)
    assert main(["--root", str(repo), "--write"]) == 0
    after = (repo / "skills/hello/SKILL.md").read_text(encoding="utf-8")
    assert f"{FIELD}: {before}" in after
    assert measure(after, encoder) == before


def test_stamp_sits_after_license_so_surface_hash_never_reorders_it() -> None:
    # surface_hash anchors immediately *before* license:; the stamp anchors
    # immediately *after*. Neither tool then moves the other's line.
    lines = stamp(SKILL, 7).split("\n")
    assert lines.index("license: Apache-2.0") == lines.index("surface_hash: sha256:0123456789abcdef") + 1
    assert lines.index(f"{FIELD}: 7") == lines.index("license: Apache-2.0") + 1


def test_restamp_replaces_rather_than_duplicates() -> None:
    twice = stamp(stamp(SKILL, 7), 9)
    assert twice.count(f"{FIELD}:") == 1 and f"{FIELD}: 9" in twice


@pytest.mark.parametrize("change", ["edit", "tamper", "remove"])
def test_drift_is_detected(repo: Path, change: str) -> None:
    assert main(["--root", str(repo), "--write"]) == 0
    target = repo / "skills/hello/SKILL.md"
    text = target.read_text(encoding="utf-8")
    if change == "edit":
        target.write_text(text.replace("hello world", "hello brave new world"), encoding="utf-8")
    elif change == "tamper":
        target.write_text(text.replace(f"{FIELD}: {stamped_value(repo)}", f"{FIELD}: 999"), encoding="utf-8")
    else:
        target.write_text(split_stamp(text)[0], encoding="utf-8")
    assert main(["--root", str(repo), "--check"]) == 1


def test_editing_one_skill_never_touches_another(repo: Path) -> None:
    # The point of per-file stamps: a PR that edits one skill writes one file.
    (repo / "skills/other").mkdir()
    (repo / "skills/other/SKILL.md").write_text(SKILL.replace("hello", "other"), encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 0
    other = (repo / "skills/other/SKILL.md").read_bytes()
    target = repo / "skills/hello/SKILL.md"
    target.write_text(target.read_text(encoding="utf-8").replace("hello world", "changed"), encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 0
    assert (repo / "skills/other/SKILL.md").read_bytes() == other


def test_line_endings_do_not_change_the_count(repo: Path) -> None:
    encoder = offline_encoding()
    text = SKILL.replace("hello world", "Olá\n世界\n<|endoftext|>")
    assert measure(text, encoder) == measure(text.replace("\n", "\r\n").replace("\r\n", "\n"), encoder)


def test_table_lists_every_skill_without_writing(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    target = repo / "skills/hello/SKILL.md"
    original = target.read_bytes()
    assert main(["--root", str(repo), "--table"]) == 0
    out = capsys.readouterr().out
    assert "[hello](../skills/hello/SKILL.md) |" in out and "cl100k_base" in out
    assert target.read_bytes() == original


def test_redirects_and_harness_copies_are_not_skills(repo: Path) -> None:
    assert main(["--root", str(repo), "--write"]) == 0
    (repo / "skills/external").mkdir()
    (repo / "skills/external/source.md").write_text("redirect", encoding="utf-8")
    (repo / ".agents/skills").mkdir(parents=True)
    (repo / ".agents/skills/hello").symlink_to(repo / "skills/hello", target_is_directory=True)
    assert main(["--root", str(repo), "--check"]) == 0


def test_symlinked_file_is_rejected(repo: Path) -> None:
    target = repo / "skills/hello/SKILL.md"
    (repo / "elsewhere.md").write_text(SKILL, encoding="utf-8")
    target.unlink()
    target.symlink_to(repo / "elsewhere.md")
    assert main(["--root", str(repo), "--write"]) == 2


def test_empty_catalogue_is_error(repo: Path) -> None:
    (repo / "skills/hello/SKILL.md").unlink()
    assert main(["--root", str(repo), "--write"]) == 2


def test_skill_without_license_cannot_be_stamped(repo: Path) -> None:
    (repo / "skills/hello/SKILL.md").write_text("---\nname: hello\n---\nbody\n", encoding="utf-8")
    assert main(["--root", str(repo), "--write"]) == 2


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


def test_repository_skills_are_all_stamped() -> None:
    root = Path(__file__).resolve().parents[3]
    if not (root / ".github/workflows/skill-token-count.yml").is_file():
        pytest.skip("Not the framework checkout")
    assert main(["--root", str(root), "--check"]) == 0


def test_ci_path_filter_covers_every_measured_skill() -> None:
    """A filter that matches nothing fails open: the job simply never runs.

    `skills/<name>` is a symlink into the family plugin that owns the skill, so
    a skill edit changes `plugins/magpie-<family>/skills/<name>/SKILL.md` and
    the mirror entry stays an unchanged symlink blob. A `paths:` filter written
    against the mirror therefore matches no changed path, the `measure` job
    never fires, and the committed measurements drift until some unrelated
    branch touching `uv.lock` inherits the red check.
    """
    import re

    root = Path(__file__).resolve().parents[3]
    workflow = root / ".github/workflows/skill-token-count.yml"
    if not workflow.is_file():
        pytest.skip("Not the framework checkout; an adopter's snapshot has no CI workflow")

    # Read the anchor's own list rather than parsing YAML: this project depends
    # on tiktoken alone, and a parser is not worth a dependency here.
    tail = workflow.read_text(encoding="utf-8").split("paths: &measurement_paths", 1)[1]
    globs = []
    for line in tail.splitlines()[1:]:
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if not entry.startswith("- "):
            break
        globs.append(entry[2:].strip().strip("'\""))
    assert globs, "No path filter entries found under the measurement_paths anchor"

    def translate(glob: str) -> re.Pattern[str]:
        # GitHub's filter globs: `**` spans separators, a lone `*` does not.
        parts, index = [], 0
        while index < len(glob):
            if glob.startswith("**", index):
                parts.append(".*")
                index += 2
            elif glob[index] == "*":
                parts.append("[^/]*")
                index += 1
            else:
                parts.append(re.escape(glob[index]))
                index += 1
        return re.compile("^" + "".join(parts) + "$")

    patterns = [translate(glob) for glob in globs]
    entries = sorted((root / "skills").iterdir())
    measured = [e / "SKILL.md" for e in entries if e.is_dir() and (e / "SKILL.md").is_file()]
    assert measured, "No skills to measure"
    for path in measured:
        # The path git reports as changed is the real file, not the mirror.
        changed = path.resolve().relative_to(root).as_posix()
        assert any(pattern.match(changed) for pattern in patterns), (
            f"No `paths:` entry in skill-token-count.yml matches {changed}; "
            "editing that skill would not run the measurement job"
        )
