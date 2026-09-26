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

"""Tests for `check-duplication.py`, the gate that fails the build on new
cross-file near-duplicate prose in `skills/`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[3]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_duplication", REPO / "tools" / "dev" / "check-duplication.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered in sys.modules before exec: the module defines dataclasses,
    # and the dataclass machinery looks its own module up by name to resolve
    # forward-referenced annotations — an unregistered module fails that
    # lookup with a confusing AttributeError instead of the real error.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load()

# A 30-word filler paragraph, repeated with small variations below. Comfortably
# over the 25-word floor on its own.
LONG_PARAGRAPH = (
    "This paragraph exists purely to carry enough words past the floor for "
    "the duplication scanner to score it, since a short admonition or a "
    "heading is never long enough to be mistaken for prose duplication here."
)
assert len(MOD.WORD_RE.findall(LONG_PARAGRAPH)) > MOD.WORD_FLOOR

SHORT_PARAGRAPH = "This paragraph is short and must never be scored."
assert len(MOD.WORD_RE.findall(SHORT_PARAGRAPH)) <= MOD.WORD_FLOOR


def _skill(name: str, body: str) -> str:
    return (
        "---\n"
        f"name: magpie-{name}\n"
        "family: issue\n"
        "description: |\n"
        "  A demo skill.\n"
        "license: Apache-2.0\n"
        "---\n\n"
        f"# {name}\n\n{body}\n"
    )


# --- extraction: word floor + paragraph splitting ------------------------------------


def test_short_paragraph_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "demo.md"
    path.write_text(f"{SHORT_PARAGRAPH}\n")
    assert MOD.extract_paragraphs(path) == []


def test_long_paragraph_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "demo.md"
    path.write_text(f"{LONG_PARAGRAPH}\n")
    paragraphs = MOD.extract_paragraphs(path)
    assert len(paragraphs) == 1
    assert paragraphs[0].text.startswith("This paragraph exists")


def test_blank_line_separates_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "demo.md"
    path.write_text(f"{LONG_PARAGRAPH}\n\n{LONG_PARAGRAPH} And then some more words follow right here.\n")
    paragraphs = MOD.extract_paragraphs(path)
    assert len(paragraphs) == 2


# --- exclusions: generated regions, frontmatter, code fences --------------------------


def test_identical_text_inside_generated_regions_is_invisible() -> None:
    """Two skills carrying the byte-identical auto pre-flight block must
    produce zero paragraphs from that block — the whole reason
    `strip_generated_regions` exists. Reuses a real propagated block from the
    live tree so the test tracks the real marker text, not a hand-written
    stand-in."""
    match = None
    for live_skill in (REPO / "skills").glob("*/SKILL.md"):
        text = live_skill.read_text()
        match = MOD.PREFLIGHT_RE.search(text)
        if match:
            break
    assert match, "expected a live skill to carry the auto pre-flight block"
    block = match.group(0)

    paragraphs = MOD.extract_paragraphs(
        Path("virtual.md"), text=f"# Heading\n\n{block}\n## Next\n\nSome unrelated text.\n"
    )
    # The block's own long paragraphs must not survive into the result.
    assert not any("first, before anything else" in p.text for p in paragraphs)


def test_declared_block_region_is_invisible(tmp_path: Path) -> None:
    body = (
        "# Heading\n\n"
        "<!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n\n"
        f"{LONG_PARAGRAPH}\n\n"
        "<!-- END MAGPIE BLOCK: widget -->\n\n"
        "## Next\n"
    )
    paragraphs = MOD.extract_paragraphs(Path("virtual.md"), text=body)
    assert paragraphs == []


def test_generated_region_removal_does_not_fuse_neighbouring_paragraphs(tmp_path: Path) -> None:
    """A generated region sits between two ordinary paragraphs; stripping it
    must leave a paragraph boundary behind rather than joining the paragraph
    before it directly onto the paragraph after it into one blob."""
    other_long_paragraph = (
        "Here is a second, unrelated paragraph that also comfortably clears "
        "the word floor on its own, so it should be counted as its own "
        "distinct unit once the block between the two has been removed."
    )
    body = (
        f"{LONG_PARAGRAPH}\n\n"
        "<!-- BEGIN MAGPIE BLOCK: widget — generated from tools/dev/blocks/widget.md -->\n\n"
        "Shared widget body text that must not appear in the result at all.\n\n"
        "<!-- END MAGPIE BLOCK: widget -->\n\n"
        f"{other_long_paragraph}\n"
    )
    paragraphs = MOD.extract_paragraphs(Path("virtual.md"), text=body)
    assert len(paragraphs) == 2
    assert paragraphs[0].text == LONG_PARAGRAPH
    assert paragraphs[1].text == other_long_paragraph


def test_frontmatter_is_excluded() -> None:
    text = _skill("demo", LONG_PARAGRAPH)
    paragraphs = MOD.extract_paragraphs(Path("virtual.md"), text=text)
    assert len(paragraphs) == 1
    assert "family: issue" not in paragraphs[0].text


def test_code_fences_are_excluded(tmp_path: Path) -> None:
    fenced = LONG_PARAGRAPH.replace("This paragraph exists", "This fenced sentence exists")
    body = f"{LONG_PARAGRAPH}\n\n```bash\n{fenced}\n```\n\n## Next\n"
    paragraphs = MOD.extract_paragraphs(Path("virtual.md"), text=body)
    assert len(paragraphs) == 1
    assert "fenced sentence" not in paragraphs[0].text


def test_code_fence_removal_does_not_fuse_neighbouring_paragraphs() -> None:
    other_long_paragraph = (
        "A second paragraph after the fence, long enough on its own to clear "
        "the floor, and it must stay a separate paragraph from the one above "
        "the fence once the fenced block itself has been removed entirely."
    )
    body = f"{LONG_PARAGRAPH}\n\n```bash\necho hello\n```\n\n{other_long_paragraph}\n"
    paragraphs = MOD.extract_paragraphs(Path("virtual.md"), text=body)
    assert len(paragraphs) == 2


# --- scoring ---------------------------------------------------------------------------


def test_exact_duplicate_scores_one() -> None:
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    b = MOD.extract_paragraphs(Path("b.md"), text=LONG_PARAGRAPH)[0]
    pairs = MOD.find_pairs([a, b], min_score=0.0)
    assert len(pairs) == 1
    assert pairs[0].score == 1.0


def test_unrelated_paragraphs_score_nothing() -> None:
    other = (
        "Completely unrelated content about an entirely different subject "
        "matter that shares essentially no nine-word sequence with the "
        "filler paragraph used everywhere else across this particular test."
    )
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    b = MOD.extract_paragraphs(Path("b.md"), text=other)[0]
    pairs = MOD.find_pairs([a, b], min_score=0.0)
    assert pairs == []


def test_same_file_pairs_are_never_compared() -> None:
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    a_again = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    pairs = MOD.find_pairs([a, a_again], min_score=0.0)
    assert pairs == []


def test_score_is_symmetric() -> None:
    """`A <-> B` and `B <-> A` must score identically — the formula's
    denominator (`min(|A|, |B|)`) does not depend on which side is which."""
    variant = LONG_PARAGRAPH.replace("purely to carry", "specifically to carry along")
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    b = MOD.extract_paragraphs(Path("b.md"), text=variant)[0]
    forward = MOD.find_pairs([a, b], min_score=0.0)[0].score
    backward = MOD.find_pairs([b, a], min_score=0.0)[0].score
    assert forward == backward


def test_pairing_is_stable_regardless_of_input_order() -> None:
    variant = LONG_PARAGRAPH.replace("purely to carry", "specifically to carry along")
    other = (
        "Completely unrelated content about an entirely different subject "
        "matter that shares essentially no nine-word sequence with the "
        "filler paragraph used everywhere else across this particular test."
    )
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    b = MOD.extract_paragraphs(Path("b.md"), text=variant)[0]
    c = MOD.extract_paragraphs(Path("c.md"), text=other)[0]

    forward = {(p.a.path, p.b.path, round(p.score, 6)) for p in MOD.find_pairs([a, b, c], min_score=0.0)}
    reverse = {(p.a.path, p.b.path, round(p.score, 6)) for p in MOD.find_pairs([c, b, a], min_score=0.0)}
    # Compare as unordered-file pairs, since which paragraph lands in `.a`
    # vs `.b` may differ with input order, but the set of (file-pair, score)
    # facts discovered must not.
    normalise = lambda pairs: {(frozenset((f1, f2)), score) for f1, f2, score in pairs}  # noqa: E731
    assert normalise(forward) == normalise(reverse)


def test_report_band_pair_does_not_fail() -> None:
    """A pair scored between REPORT_THRESHOLD and FAIL_THRESHOLD is reported
    but does not cross the fail line. Mutating every 15th word of the
    36-word `LONG_PARAGRAPH` (indices 0, 15, 30) lands the containment score
    at 0.4286 — precomputed once and fixed here, not re-derived per run."""
    words = LONG_PARAGRAPH.split()
    mutated = list(words)
    for i in range(0, len(mutated), 15):
        mutated[i] = f"altered{i}"
    variant = " ".join(mutated)
    a = MOD.extract_paragraphs(Path("a.md"), text=LONG_PARAGRAPH)[0]
    b = MOD.extract_paragraphs(Path("b.md"), text=variant)[0]
    pairs = MOD.find_pairs([a, b], min_score=0.0)
    assert pairs, "expected the mutated paragraph to still register some overlap"
    score = pairs[0].score
    assert MOD.REPORT_THRESHOLD <= score <= MOD.FAIL_THRESHOLD, score


def test_pair_above_fail_threshold_fails(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    (skills / "one").mkdir(parents=True)
    (skills / "two").mkdir(parents=True)
    (skills / "one" / "SKILL.md").write_text(_skill("one", LONG_PARAGRAPH))
    (skills / "two" / "SKILL.md").write_text(_skill("two", LONG_PARAGRAPH))

    targets = MOD.discover_targets(
        skills_root=skills, blocks_dir=tmp_path / "no-blocks", preflight_source=tmp_path / "no-preflight.md"
    )
    paragraphs = MOD.scan(targets)
    pairs = MOD.find_pairs(paragraphs)
    fail_pairs = [p for p in pairs if p.score > MOD.FAIL_THRESHOLD]
    assert len(fail_pairs) == 1
    assert fail_pairs[0].score == 1.0


# --- discovery ---------------------------------------------------------------------------


def test_discover_targets_follows_symlinked_skill_directories(tmp_path: Path) -> None:
    """`skills/<name>` is a symlink into `plugins/magpie-<family>/skills/<name>`
    in this repo's own self-adoption layout — `discover_targets` must follow
    it (`os.walk(..., followlinks=True)`), not silently skip every skill."""
    real_root = tmp_path / "real" / "demo"
    real_root.mkdir(parents=True)
    (real_root / "SKILL.md").write_text(_skill("demo", LONG_PARAGRAPH))

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    (skills_root / "demo").symlink_to(real_root, target_is_directory=True)

    targets = MOD.discover_targets(
        skills_root=skills_root,
        blocks_dir=tmp_path / "no-blocks",
        preflight_source=tmp_path / "no-preflight.md",
    )
    assert (skills_root / "demo" / "SKILL.md") in targets


def test_discover_targets_skips_cache_directories(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    cache = skills_root / ".pytest_cache"
    cache.mkdir(parents=True)
    (cache / "README.md").write_text("cache readme\n")

    targets = MOD.discover_targets(
        skills_root=skills_root,
        blocks_dir=tmp_path / "no-blocks",
        preflight_source=tmp_path / "no-preflight.md",
    )
    assert targets == []


def test_discover_targets_includes_blocks_and_preflight_source(tmp_path: Path) -> None:
    blocks_dir = tmp_path / "blocks"
    blocks_dir.mkdir()
    (blocks_dir / "widget.md").write_text("widget body\n")
    preflight = tmp_path / "preflight-block.md"
    preflight.write_text("preflight body\n")

    targets = MOD.discover_targets(
        skills_root=tmp_path / "no-skills", blocks_dir=blocks_dir, preflight_source=preflight
    )
    assert blocks_dir / "widget.md" in targets
    assert preflight in targets


# --- the real tree ---------------------------------------------------------------------


def test_real_tree_scan_does_not_crash_and_is_deterministic() -> None:
    """Not a duplication-content assertion (the live tree's actual duplicate
    count is covered by running the CLI directly, not asserted in-suite,
    since it is expected to change as skills are added or reworded) — this
    just guards that a full real-tree scan runs cleanly and produces the
    same result on a second pass. Paths are REPO-relative rather than the
    module's bare defaults, since the workspace test runner's cwd is
    `tools/dev`, not the repository root."""
    targets = MOD.discover_targets(
        skills_root=REPO / "skills",
        blocks_dir=REPO / "tools" / "dev" / "blocks",
        preflight_source=REPO / "tools" / "dev" / "preflight-block.md",
    )
    assert targets, "expected at least one file in scope"
    first = MOD.scan(targets)
    second = MOD.scan(targets)
    assert len(first) == len(second)
