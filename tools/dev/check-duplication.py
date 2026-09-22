#!/usr/bin/env python3
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
"""Fail the build on new cross-file near-duplicate prose in `skills/` —
the gate that keeps the duplication `check-shared-blocks.py` and
`skill-surface-hash.py` removed from coming back.

`check-shared-blocks.py` gives skills a way to carry shared prose once and
propagate it everywhere it is used. That mechanism only works if something
stops a contributor from doing the easy thing instead: pasting a paragraph
copied from another skill straight into a new one. Nothing about that paste
looks wrong in review — it reads fine in isolation, the diff is small, and
the reviewer would have to already know the other skill's wording by heart
to catch it. This script is that check: it scans every scoped file for
paragraphs that are near-duplicates of a paragraph in a *different* file and
fails the build when the overlap is high enough that it should have been a
declared block instead.

**What it measures.** Paragraphs of more than 25 words, normalised to
lowercase word tokens, compared across files as sets of 9-grams (nine
consecutive tokens), scored `|A ∩ B| / min(|A|, |B|)` — containment rather
than Jaccard, so a short paragraph fully quoted inside a much longer one
still scores high even though the longer paragraph carries plenty of text
the short one does not. The score is symmetric by construction (the
denominator does not depend on which paragraph is "A") and does not depend
on the order files are scanned in, since every unordered pair of paragraphs
from two different files is scored exactly once.

**What it must not see.** Generated regions — the auto pre-flight block
`check-shared-blocks.py` inserts into every non-`setup` skill, and any
declared block filled in from `tools/dev/blocks/<name>.md` — are duplicates
*by design*: 65 skills carry the same pre-flight block on purpose. This
script reuses `check-shared-blocks.py`'s own `PREFLIGHT_RE` / `DECLARED_RE`
marker regexes (not a second, driftable copy of what "a generated region"
looks like) to blank those spans out before paragraph-splitting — blanked
rather than deleted, specifically so that removing a generated region can
never fuse the paragraph before it and the paragraph after it into one. YAML
frontmatter and fenced code blocks are excluded the same way: frontmatter is
metadata, not prose, and a shared command sequence in a code fence is
legitimately identical across skills.

**Thresholds**, measured against the tree at the time this check was
written (574 paragraphs in scope, maximum cross-file score 0.45):

* **Fail above 0.50.** Nothing in the tree reaches it today, so the gate
  ships with no allowlist and no grandfathered debt, while still blocking a
  return to the 0.56-0.88 range the shared-block extraction removed.
* **Report, without failing, everything in [0.30, 0.50].** That tail stays
  visible in every run's output so it can be reduced deliberately, instead
  of being hidden behind an ignore file that nobody revisits.
* **Say nothing below 0.30.** A quiet, high-bar report is the point: a
  gate that cries wolf on ordinary shared vocabulary teaches the next
  contributor to add an ignore entry instead of fixing the duplication, and
  becomes decoration.

**Scope.** `skills/` (recursively — a multi-file skill's sibling detail
files carry just as much prose as `SKILL.md` itself) plus
`tools/dev/blocks/*.md` and `tools/dev/preflight-block.md` — the declared-
block sources themselves are in scope, so a paragraph pasted into a skill
that already duplicates a block's *source* text is caught too, which is
exactly the case that should have used the block instead of copying it.
`docs/`, `.superpowers/`, and eval fixtures are out of scope: fixtures
repeat each other by design, and this check is about the skill surface the
shared-block mechanism actually owns.

Run standalone (`python3 tools/dev/check-duplication.py`) or as the
`check-duplication` prek hook, wired `pass_filenames: false` and whole-tree:
a diff-scoped run cannot see that a paragraph added in this PR duplicates
one that already exists somewhere the PR never touched.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from types import ModuleType


def _load_shared_blocks() -> ModuleType:
    """Load `check-shared-blocks.py` as a module so this script reuses its
    exact `PREFLIGHT_RE` / `DECLARED_RE` marker regexes instead of keeping a
    second, driftable definition of "a generated region" here."""
    path = Path(__file__).resolve().parent / "check-shared-blocks.py"
    spec = importlib.util.spec_from_file_location("check_shared_blocks", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SHARED_BLOCKS = _load_shared_blocks()
# Re-exported, not redefined: the exact regex objects `check-shared-blocks.py`
# compiles, so a marker-format change there is automatically reflected here.
PREFLIGHT_RE = _SHARED_BLOCKS.PREFLIGHT_RE
DECLARED_RE = _SHARED_BLOCKS.DECLARED_RE

SKILLS = Path("skills")
BLOCKS_DIR = Path("tools/dev/blocks")
PREFLIGHT_SOURCE = Path("tools/dev/preflight-block.md")

WORD_FLOOR = 25  # a paragraph must have MORE than this many words to be scored
NGRAM_SIZE = 9
FAIL_THRESHOLD = 0.50  # score strictly greater than this fails the check
REPORT_THRESHOLD = 0.30  # score at/above this (and at/below FAIL_THRESHOLD) is reported, not failed

WORD_RE = re.compile(r"[A-Za-z0-9']+")
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
CODE_FENCE_RE = re.compile(r"^[ \t]*```.*?\n.*?^[ \t]*```[ \t]*$\n?", re.M | re.S)
BLANK_LINE_RE = re.compile(r"\n[ \t]*\n+")


@dataclass(frozen=True)
class Paragraph:
    path: Path
    line: int
    text: str
    grams: frozenset[tuple[str, ...]]


@dataclass(frozen=True)
class DuplicatePair:
    a: Paragraph
    b: Paragraph
    score: float


def _blank_out(pattern: re.Pattern[str], text: str) -> str:
    """Replace every match of `pattern` with a single blank line rather than
    deleting it outright. A generated region or a code fence sits between
    two ordinary paragraphs; deleting it outright can join the paragraph
    before it directly onto the paragraph after it (no blank line survives
    between them), silently fusing two unrelated paragraphs into one. A
    blank-line replacement always leaves a paragraph boundary in its place,
    so removal can only ever *drop* a paragraph, never merge two others."""
    return pattern.sub("\n\n", text)


def strip_generated_regions(text: str) -> str:
    """Blank out the auto pre-flight block and every declared block, using
    `check-shared-blocks.py`'s own marker regexes."""
    text = _blank_out(PREFLIGHT_RE, text)
    text = _blank_out(DECLARED_RE, text)
    return text


def strip_frontmatter(text: str) -> str:
    """Blank out a leading YAML frontmatter block (`SKILL.md` files only —
    sibling detail files and the declared-block sources carry none, so this
    is a no-op for them)."""
    return _blank_out(FRONTMATTER_RE, text) if FRONTMATTER_RE.match(text) else text


def strip_code_fences(text: str) -> str:
    """Blank out fenced code blocks — shared command sequences are
    legitimately identical across skills and are not prose duplication."""
    return _blank_out(CODE_FENCE_RE, text)


def _line_of(original: str, paragraph_text: str) -> int:
    """1-based line number of `paragraph_text` inside `original`. The
    paragraph's own characters are never altered by the blanking passes
    above — only the spans *around* it are — so its text (or at least its
    first line) is always a literal substring of the untouched original
    file, and `str.find` locates it directly."""
    idx = original.find(paragraph_text)
    if idx == -1:
        idx = original.find(paragraph_text.split("\n", 1)[0])
    if idx == -1:
        return 1
    return original.count("\n", 0, idx) + 1


def extract_paragraphs(path: Path, text: str | None = None) -> list[Paragraph]:
    """Every paragraph in `path` (or `text`, for tests) at or above the word
    floor, with its 9-gram set and its line number in the original file."""
    original = text if text is not None else path.read_text()
    body = strip_generated_regions(original)
    body = strip_frontmatter(body)
    body = strip_code_fences(body)

    paragraphs: list[Paragraph] = []
    for raw in BLANK_LINE_RE.split(body):
        para = raw.strip("\n")
        if not para.strip():
            continue
        words = [w.lower() for w in WORD_RE.findall(para)]
        if len(words) <= WORD_FLOOR:
            continue
        grams = frozenset(tuple(words[i : i + NGRAM_SIZE]) for i in range(len(words) - NGRAM_SIZE + 1))
        paragraphs.append(Paragraph(path=path, line=_line_of(original, para), text=para, grams=grams))
    return paragraphs


def discover_targets(
    skills_root: Path = SKILLS,
    blocks_dir: Path = BLOCKS_DIR,
    preflight_source: Path = PREFLIGHT_SOURCE,
) -> list[Path]:
    """Every file in scope: `skills/` recursively (symlink-aware — a
    self-adopted `skills/<name>` is a symlink into `plugins/magpie-<family>/
    skills/<name>`, which `Path.glob("**/...")` does not follow but
    `os.walk(..., followlinks=True)` does), plus the declared-block sources
    and the pre-flight source. Cache directories (`__pycache__`,
    `.pytest_cache`, …) are skipped."""
    targets: list[Path] = []
    if skills_root.is_dir():
        for root, dirs, files in os.walk(skills_root, followlinks=True):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for name in files:
                if name.endswith(".md"):
                    targets.append(Path(root) / name)
    if blocks_dir.is_dir():
        targets.extend(sorted(blocks_dir.glob("*.md")))
    if preflight_source.is_file():
        targets.append(preflight_source)
    return sorted(set(targets))


def scan(paths: list[Path]) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for path in paths:
        paragraphs.extend(extract_paragraphs(path))
    return paragraphs


def find_pairs(paragraphs: list[Paragraph], min_score: float = REPORT_THRESHOLD) -> list[DuplicatePair]:
    """Cross-file near-duplicate pairs scored at or above `min_score`.
    Same-file paragraph pairs are never compared — this gate polices
    duplication *across* files; a skill quoting itself is not the failure
    mode `check-shared-blocks.py` exists to prevent. The score
    (`|A ∩ B| / min(|A|, |B|)`) is symmetric by construction, and comparing
    every unordered pair exactly once (via `itertools.combinations`) makes
    the result independent of the order `paragraphs` was built in."""
    pairs: list[DuplicatePair] = []
    for a, b in combinations(paragraphs, 2):
        if a.path == b.path:
            continue
        overlap = len(a.grams & b.grams)
        if not overlap:
            continue
        score = overlap / min(len(a.grams), len(b.grams))
        if score >= min_score:
            pairs.append(DuplicatePair(a=a, b=b, score=score))
    pairs.sort(key=lambda pair: pair.score, reverse=True)
    return pairs


def _snippet(text: str, limit: int = 160) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


def _format_pair(pair: DuplicatePair) -> str:
    return f"  {pair.a.path}:{pair.a.line} <-> {pair.b.path}:{pair.b.line}  score {pair.score:.2f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    targets = discover_targets()
    if not targets:
        print(f"{SKILLS}: no target files found", file=sys.stderr)
        return 1

    paragraphs = scan(targets)
    pairs = find_pairs(paragraphs)
    fail_pairs = [pair for pair in pairs if pair.score > FAIL_THRESHOLD]
    report_pairs = [pair for pair in pairs if pair.score <= FAIL_THRESHOLD]

    if report_pairs:
        print(
            f"Near-duplicate prose in the report band "
            f"(score {REPORT_THRESHOLD:.2f}-{FAIL_THRESHOLD:.2f}, not failing — worth reducing deliberately):"
        )
        for pair in report_pairs:
            print(_format_pair(pair))
        print()

    if fail_pairs:
        print(
            f"Cross-file near-duplicate prose exceeds the fail threshold (score > {FAIL_THRESHOLD:.2f}):",
            file=sys.stderr,
        )
        for pair in fail_pairs:
            print(_format_pair(pair), file=sys.stderr)
            print(f"    {pair.a.path}:{pair.a.line}: {_snippet(pair.a.text)}", file=sys.stderr)
            print(f"    {pair.b.path}:{pair.b.line}: {_snippet(pair.b.text)}", file=sys.stderr)
        print(
            "\nMove the shared paragraph into tools/dev/blocks/<name>.md as a declared block "
            "(see check-shared-blocks.py) and let it propagate to both files, or reword one side "
            "so it is no longer a near-duplicate.",
            file=sys.stderr,
        )
        return 1

    max_score = pairs[0].score if pairs else 0.0
    print(
        f"check-duplication: {len(paragraphs)} paragraph(s) across {len(targets)} file(s) scanned; "
        f"{len(report_pairs)} pair(s) in the report band, 0 above the fail threshold "
        f"(highest score {max_score:.2f})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
