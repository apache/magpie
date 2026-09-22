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
"""Fail the build on new cross-file near-duplicate prose — the gate that
keeps the duplication `check-shared-blocks.py` and `skill-surface-hash.py`
removed from coming back. Designed for the whole `skills/` tree; wired,
for now, over only the setup-family surface that removal actually
touched — see "Landing scope vs. the whole duplication problem" below.

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

**Thresholds.** Chosen so the *wired* scope below (not the whole tree —
see "Landing scope" above for why those two differ) passes clean today,
with no allowlist:

* **Fail above 0.50.** Nothing in the *wired* scope reaches it today, so
  the gate ships with no allowlist and no grandfathered debt there, while
  still blocking a return to the 0.56-0.88 range the shared-block
  extraction removed. The whole `skills/` tree is a different story —
  see "Landing scope" below.
* **Report, without failing, everything in [0.30, 0.50].** That tail stays
  visible in every run's output so it can be reduced deliberately, instead
  of being hidden behind an ignore file that nobody revisits.
* **Say nothing below 0.30.** A quiet, high-bar report is the point: a
  gate that cries wolf on ordinary shared vocabulary teaches the next
  contributor to add an ignore entry instead of fixing the duplication, and
  becomes decoration.

**Scope, as designed.** The whole `skills/` tree (recursively — a
multi-file skill's sibling detail files carry just as much prose as
`SKILL.md` itself) plus `tools/dev/blocks/*.md` and
`tools/dev/preflight-block.md` — the declared-block sources themselves are
in scope, so a paragraph pasted into a skill that already duplicates a
block's *source* text is caught too, which is exactly the case that should
have used the block instead of copying it. `docs/`, `.superpowers/`, and
eval fixtures are out of scope by design: fixtures repeat each other on
purpose, and this check is about the skill surface the shared-block
mechanism actually owns.

**Scope, as wired (`WIRED_SKILLS_ROOT` below).** Narrower than the design
above, on purpose — see "Landing scope vs. the whole duplication problem"
below for the measured numbers and why. The hook runs this check only
over `plugins/magpie-setup/skills/setup/*.md`, `tools/dev/blocks/*.md`,
and `tools/dev/preflight-block.md`: exactly the surfaces the shared-block
extraction this check was built to guard actually touched, where the tree
is clean today and the gate passes with no allowlist. `discover_targets`
still takes `skills_root` as a parameter — a future widening (see the
recommended sequence below) is a one-line change to `WIRED_SKILLS_ROOT`,
not a rewrite.

**Landing scope vs. the whole duplication problem.** A whole-tree run
(`discover_targets(skills_root=Path("skills"))`) finds far more than the
setup-family surface this effort covers: 4,970 paragraphs, **3,793** pairs
above `FAIL_THRESHOLD`, maximum score **1.00** — not near-duplicate,
byte-identical. Traced by hand (`grep`, independent of this script): the
`**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`...` admonition is identical in **45**
`SKILL.md` files; an "Adopter overrides" preamble paragraph (only the
skill's own filename substituted) is near-identical in **56**; a
"Snapshot drift" paragraph follows the same pattern. None of the three is
wrapped in a `<!-- BEGIN MAGPIE BLOCK -->` / auto-preflight marker, so this
script's own `strip_generated_regions` cannot see them — and
`skills/write-skill/SKILL.md` documents all three as **the framework
preamble**: "every framework skill carries these; `init_skill.py`
scaffolds them." That is the tell. This is not organic copy-paste sprawl;
it is a *second*, older propagation mechanism (a one-time scaffold copy at
skill-creation time) that was never migrated to the modern one this file
already reuses (`check-shared-blocks.py`'s auto pre-flight block, inserted
into every non-`setup` skill from one source). The fix belongs in that
*auto*-propagation path, not in declared regions hand-placed into 56
files one at a time: a declared block only fills a region a target
already carries by hand, which is the multiplication problem all over
again at extraction time, whereas the auto block is inserted and kept in
sync by the tool itself. `check-shared-blocks.py` currently supports
exactly **one** auto block (the pre-flight block); carrying several
(pre-flight, `Adopter overrides`, `Snapshot drift`, …) is a mechanism
change to that script, not something this file can do on its own.
Recommended sequence for whoever picks this up: **(1)** extend
`check-shared-blocks.py`'s auto-block mechanism to carry more than one
named auto block, migrate `Adopter overrides` / `Snapshot drift` (and
likely the `Hard rule` admonition) onto it; **(2)** re-run this checker
whole-tree and confirm the fail-band count has actually dropped, not just
moved; **(3)** widen `WIRED_SKILLS_ROOT` below (or drop it in favour of
the full `skills/` tree) once the tree is clean at that scope too. None of
that is done here — the maintainer scoped it out of this landing
deliberately, and this file does not touch `check-shared-blocks.py`.

Run standalone (`python3 tools/dev/check-duplication.py`) or as the
`check-duplication` prek hook, wired `pass_filenames: false` and
whole-scope: a diff-scoped run cannot see that a paragraph added in this
PR duplicates one that already exists in a file the PR never touched.
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

BLOCKS_DIR = Path("tools/dev/blocks")
PREFLIGHT_SOURCE = Path("tools/dev/preflight-block.md")
PREFLIGHT_DETAIL_SOURCE = _SHARED_BLOCKS.PREFLIGHT_DETAIL_SOURCE
PREFLIGHT_DETAIL_NAME = _SHARED_BLOCKS.PREFLIGHT_DETAIL_NAME

# The wired scope is deliberately narrower than the design's `skills/`
# tree — see the module docstring's "Landing scope vs. the whole
# duplication problem" section for the measured whole-tree numbers
# (4,970 paragraphs, 3,793 fail-band pairs, max score 1.00) and why. This
# is the ONLY root the design scans that is clean today: the setup family
# is exactly the surface tasks A-C's shared-block extraction touched.
# Widening this constant to the full `skills/` tree before the preamble
# duplication documented in the docstring is migrated onto the auto-block
# mechanism will immediately fail `prek run --all-files` on ~3800
# pre-existing pairs this script did not introduce and is not scoped to
# fix. Do not widen it without re-running the whole-tree scan first.
WIRED_SKILLS_ROOT = Path("plugins/magpie-setup/skills/setup")

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
    skills_root: Path = WIRED_SKILLS_ROOT,
    blocks_dir: Path = BLOCKS_DIR,
    preflight_source: Path = PREFLIGHT_SOURCE,
    detail_source: Path = PREFLIGHT_DETAIL_SOURCE,
) -> list[Path]:
    """Every file in scope: `skills_root` recursively (symlink-aware — a
    self-adopted `skills/<name>` is a symlink into `plugins/magpie-<family>/
    skills/<name>`, which `Path.glob("**/...")` does not follow but
    `os.walk(..., followlinks=True)` does — relevant when `skills_root` is
    widened back to the full `skills/` tree; the wired default,
    `WIRED_SKILLS_ROOT`, is a real directory, not a symlink), plus the
    declared-block sources and the pre-flight source. Cache directories
    (`__pycache__`, `.pytest_cache`, …) are skipped, and so is every generated
    `preflight-detail.md` sidecar: 65 byte-identical copies of one source
    would be 65 x 64 perfect-score pairs saying nothing except that
    propagation worked. Its source is scanned in their place, exactly as the
    pre-flight block's is. Pass
    `skills_root=Path("skills")` for the whole-tree scan described in the
    module docstring's "Landing scope" section."""
    targets: list[Path] = []
    if skills_root.is_dir():
        for root, dirs, files in os.walk(skills_root, followlinks=True):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for name in files:
                if name.endswith(".md") and name != PREFLIGHT_DETAIL_NAME:
                    targets.append(Path(root) / name)
    if blocks_dir.is_dir():
        targets.extend(sorted(blocks_dir.glob("*.md")))
    if preflight_source.is_file():
        targets.append(preflight_source)
    if detail_source.is_file():
        targets.append(detail_source)
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
        print(f"{WIRED_SKILLS_ROOT}: no target files found", file=sys.stderr)
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
