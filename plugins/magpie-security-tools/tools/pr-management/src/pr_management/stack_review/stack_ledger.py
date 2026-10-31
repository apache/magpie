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

"""Build the file-by-layer ledger of a pull-request stack from its layer diffs.

The ledger is the deterministic half of ``pr-management-stack-review``: it
answers every structural question that scales with the number of files
(which files several layers touch, which layers are mechanical, which hunks
do not look like the rest of their layer, where release notes or generated
files were regenerated twice) and plans what the model reads, so the model
only reads what the ledger points at. It never reads code semantics; that
is the model's job.

Usage::

    python3 stack_ledger.py ledger --layer 1=/tmp/s/1.diff --layer 2=/tmp/s/2.diff \\
        [--generated-globs 'docs/**/*.svg,build/*'] [--gitattributes <clone>/.gitattributes] \\
        [--read-budget 4000] [--full-read-max-lines 1500] > ledger.json
    python3 stack_ledger.py render ledger.json            # markdown coverage table + detectors
    python3 stack_ledger.py hunks ledger.json --layer 2=/tmp/s/2.diff   # planned hunks with line numbers

Each ``--layer`` names the layer's position (1 = bottom, closest to the
trunk) and a unified diff of that layer alone (``gh pr diff <N>`` or
``git diff <below>...<head>``). The script is standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import keyword
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

# Files whose content is produced by a tool. They are counted, never read,
# and never sized: a layer that regenerates a 2,000-line lock file next to a
# 20-line manifest change is a 20-line layer. Adopters extend the list
# through `--generated-globs` or `.gitattributes` `linguist-generated`
# entries; the skill passes both. A glob matches the whole path, the file
# name, or any directory suffix of the path (`generated/*` matches a
# root-level `generated/README.md` as well as `a/b/generated/x`). The list
# names tool output only; a directory name a project happens to use for
# hand-written code (`datamodels/`, `models/`) never belongs here — adopters
# add their own patterns through the override file.
DEFAULT_GENERATED_GLOBS: tuple[str, ...] = (
    "*.lock",
    "*.md5sum",
    "*.min.js",
    "*.min.css",
    "*.snap",
    "*.svg",
    "__snapshots__/*",
    "*.pb.go",
    "*.gen.go",
    "*.gen.ts",
    "*_generated.*",
    "*_pb2.py",
    "*_pb2_grpc.py",
    "generated/*",
    # Lock files are resolver output whatever their suffix.
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.sum",
    "Pipfile.lock",
)

# Where projects keep per-change release notes; the same path touched in two
# layers means the note was written twice.
RELEASE_NOTE_GLOBS: tuple[str, ...] = (
    "newsfragments/*",
    "CHANGELOG*",
    "changelog.rst",
    "RELEASE_NOTES*",
)

# A lock file and the manifest it is resolved from belong in the same layer.
LOCK_MANIFESTS: dict[str, tuple[str, ...]] = {
    "uv.lock": ("pyproject.toml",),
    "poetry.lock": ("pyproject.toml",),
    "Pipfile.lock": ("Pipfile",),
    "package-lock.json": ("package.json",),
    "pnpm-lock.yaml": ("package.json",),
    "yarn.lock": ("package.json",),
    "Cargo.lock": ("Cargo.toml",),
    "go.sum": ("go.mod",),
    "Gemfile.lock": ("Gemfile",),
}

DOC_SUFFIXES = (".md", ".rst", ".txt", ".adoc")

# Shape thresholds. A layer is *mechanical* when repeated line shapes (a
# skeleton seen at least REPEATED_LINE_MIN times in the layer) cover this
# share of its hand-written changed lines: a formatter, codemod or sed pass
# produced it. In a mechanical layer every outlier (a hunk whose shape occurs
# once) is a hand edit and is always read; in a hand-written layer an outlier
# is just a hunk, and a demoted layer reads them ranked within its share of
# the budget.
REPEATED_LINE_MIN = 3
MECHANICAL_MIN_LINES = 20
MECHANICAL_COVERAGE = 0.80
# A full read is planned only up to this many hand-written changed lines per
# layer and within the overall read budget; `[D]eepen` doubles both.
DEFAULT_FULL_READ_MAX_LINES = 1500
DEFAULT_READ_BUDGET = 4000
# When a hand-written layer is demoted, its outliers are planned in this
# class order (then smallest first) until the layer's share of the remaining
# budget is spent.
CLASS_RANK = {"source": 0, "config": 1, "release-note": 1, "test": 2, "docs": 3, "generated": 9}

_KEYWORDS = frozenset(keyword.kwlist) | {
    "None",
    "True",
    "False",
    "self",
    "cls",
    "function",
    "const",
    "let",
    "var",
    "new",
    "this",
    "null",
    "undefined",
    "public",
    "private",
    "static",
    "void",
    "int",
    "string",
    "bool",
    "struct",
    "fn",
    "pub",
    "mut",
}
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_COMMA_LIST = re.compile(r"(?:_\s*,\s*)+_")
_NUMBER = re.compile(r"\b\d+(\.\d+)?\b")
_STRING = re.compile(r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')")
_DIFF_HEADER = re.compile(r"^diff --git a/(?P<a>.*?) b/(?P<b>.*)$")
_HUNK_HEADER = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_len>\d+))? \+(?P<new>\d+)(?:,(?P<new_len>\d+))? @@")


@dataclass
class Hunk:
    path: str
    new_start: int
    new_len: int = 0
    lines: list[str] = field(default_factory=list)  # raw diff lines with their +/-/space prefix

    @property
    def removed(self) -> list[str]:
        return [line[1:] for line in self.lines if line.startswith("-")]

    @property
    def added(self) -> list[str]:
        return [line[1:] for line in self.lines if line.startswith("+")]

    @property
    def ref(self) -> str:
        return f"{self.path}:{self.new_start}"

    @property
    def span(self) -> str:
        end = self.new_start + max(self.new_len, 1) - 1
        return f"{self.path}:{self.new_start}-{end}"

    @property
    def changed_lines(self) -> int:
        return sum(1 for line in self.lines if line[:1] in "+-")


@dataclass
class FileDiff:
    path: str
    status: str  # A added, D deleted, M modified, R renamed
    old_path: str | None
    hunks: list[Hunk] = field(default_factory=list)
    binary: bool = False


def parse_unified_diff(text: str) -> list[FileDiff]:
    """Parse ``git diff`` / ``gh pr diff`` output into files and hunks.

    File-header lines (``---``/``+++``/``index``/modes) are skipped only
    before a file's first hunk; inside a hunk every line is classified by its
    first character, so a removed ``--`` SQL comment or an added ``++`` line
    is counted like any other change.
    """
    files: list[FileDiff] = []
    current: FileDiff | None = None
    hunk: Hunk | None = None
    for raw in text.splitlines():
        header = _DIFF_HEADER.match(raw)
        if header:
            old, new = header.group("a"), header.group("b")
            current = FileDiff(
                path=new, status="R" if old != new else "M", old_path=old if old != new else None
            )
            files.append(current)
            hunk = None
            continue
        if current is None:
            continue
        hunk_header = _HUNK_HEADER.match(raw)
        if hunk_header:
            hunk = Hunk(
                path=current.path,
                new_start=int(hunk_header.group("new")),
                new_len=int(hunk_header.group("new_len") or 1),
            )
            current.hunks.append(hunk)
            continue
        if hunk is None:
            if raw.startswith("new file mode"):
                current.status = "A"
            elif raw.startswith("deleted file mode"):
                current.status = "D"
            elif raw.startswith("rename from "):
                current.old_path = raw[len("rename from ") :]
                current.status = "R"
            elif raw.startswith(("Binary files", "GIT binary patch")):
                current.binary = True
            continue
        if raw.startswith("\\ No newline"):
            continue
        if raw[:1] in "+- ":
            hunk.lines.append(raw)
    return files


def skeleton(line: str) -> str:
    """Reduce a source line to its shape: literals, identifiers and list arity masked."""
    text = _STRING.sub('""', line)
    text = _NUMBER.sub("0", text)
    text = _IDENT.sub(lambda m: m.group(0) if m.group(0) in _KEYWORDS else "_", text)
    text = _COMMA_LIST.sub("_,+", text)
    return " ".join(text.split())


def line_skeletons(hunk: Hunk) -> list[str]:
    return [skeleton(line) for line in hunk.removed + hunk.added if line.strip()]


def hunk_shape(hunk: Hunk) -> str:
    """Fingerprint a hunk by the set of its line shapes.

    Two hunks share a shape when a tool applied the same kinds of rewrite to
    both, whatever the identifiers were and however many lines each touched.
    """
    digest = hashlib.sha256("\n".join(sorted(set(line_skeletons(hunk)))).encode()).hexdigest()
    return digest[:12]


def matches_any(path: str, globs: tuple[str, ...] | list[str]) -> bool:
    parts = PurePosixPath(path).parts
    candidates = {path, parts[-1]} | {"/".join(parts[i:]) for i in range(1, len(parts))}
    return any(fnmatch.fnmatch(c, g) for g in globs for c in candidates)


def parse_gitattributes_generated(text: str) -> list[str]:
    """Return the path patterns `.gitattributes` marks `linguist-generated`."""
    globs: list[str] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "linguist-generated" not in line:
            continue
        pattern, *attrs = line.split()
        if any(a in ("linguist-generated", "linguist-generated=true") for a in attrs):
            globs.append(pattern.lstrip("/"))
    return globs


def classify_path(path: str, generated_globs: tuple[str, ...] | list[str]) -> str:
    if matches_any(path, generated_globs):
        return "generated"
    if matches_any(path, RELEASE_NOTE_GLOBS):
        return "release-note"
    parts = PurePosixPath(path).parts
    name = parts[-1]
    if (
        "tests" in parts
        or "test" in parts
        or name.startswith("test_")
        or name.endswith(("_test.py", "_test.go", ".test.ts", ".spec.ts", "Test.java", "Test.kt"))
    ):
        return "test"
    if name.lower().endswith(DOC_SUFFIXES) or "docs" in parts[:2]:
        return "docs"
    manifests = {m for ms in LOCK_MANIFESTS.values() for m in ms}
    if (
        name in LOCK_MANIFESTS
        or name in manifests
        or name.endswith((".toml", ".cfg", ".ini", ".yaml", ".yml", ".json"))
    ):
        return "config"
    return "source"


def top_dir(path: str, depth: int = 2) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) <= 1:
        return "(root)"
    return "/".join(parts[: min(depth, len(parts) - 1)])


@dataclass
class LayerLedger:
    position: int
    files: int
    changed_lines: int  # hand-written: generated and binary files excluded
    generated_lines: int
    hunks: int  # hand-written hunks
    generated_hunks: int
    classes: dict[str, int]
    generated_files: list[str]
    dir_histogram: dict[str, int]
    dir_outliers: list[str]
    line_shapes: int
    repeated_line_coverage: float
    mechanical: bool
    exemplars: list[str]
    outliers: list[str]
    binary_files: int
    deleted_files: list[str]
    plan: str = ""
    plan_reason: str = ""
    planned_hunks: int = 0
    planned_lines: int = 0
    planned_hunk_refs: list[str] = field(default_factory=list)
    outliers_planned: int = 0
    outliers_in_share: int = 0  # outliers bought with the share, not already read as Tier A
    outlier_share: int = 0  # lines of ranked outliers a demoted hand-written layer may read
    overlap_hunks: int = 0


@dataclass
class Ledger:
    layers: list[LayerLedger]
    distinct_files: int
    overlap: dict[str, list[int]]
    overlap_pairs: dict[str, int]
    detectors: dict[str, list[dict[str, object]]]
    read_fully_files: dict[str, list[int]]
    touched_files: list[str]
    read_budget: int
    full_read_max_lines: int
    planned_total_hunks: int
    total_hunks: int
    total_generated_hunks: int


@dataclass
class _LayerWork:
    """Per-layer parse products the plan pass needs after the layer summary is built."""

    files: list[FileDiff]
    classes_by_path: dict[str, str]
    hand_hunks: list[Hunk]
    outlier_refs: list[str]
    exemplar_refs: list[str]


def _summarise_layer(
    position: int, files: list[FileDiff], generated_globs: tuple[str, ...] | list[str]
) -> tuple[LayerLedger, _LayerWork]:
    classes: Counter[str] = Counter()
    classes_by_path: dict[str, str] = {}
    dirs: Counter[str] = Counter()
    line_counts: Counter[str] = Counter()
    hand_hunks: list[Hunk] = []
    generated_files: list[str] = []
    changed_lines = generated_lines = generated_hunks = binary = 0
    deleted: list[str] = []
    for f in files:
        path_class = classify_path(f.path, generated_globs)
        classes[path_class] += 1
        classes_by_path[f.path] = path_class
        dirs[top_dir(f.path)] += 1
        if f.binary:
            binary += 1
        if f.status == "D":
            deleted.append(f.path)
        skip = path_class == "generated" or f.binary
        if skip:
            generated_files.append(f.path)
        for h in f.hunks:
            if skip:
                generated_lines += h.changed_lines
                generated_hunks += 1
                continue
            changed_lines += h.changed_lines
            line_counts.update(line_skeletons(h))
            hand_hunks.append(h)
    total_lines = sum(line_counts.values())
    repeated = sum(c for c in line_counts.values() if c >= REPEATED_LINE_MIN)
    coverage = (repeated / total_lines) if total_lines else 0.0
    mechanical = total_lines >= MECHANICAL_MIN_LINES and coverage >= MECHANICAL_COVERAGE
    # An outlier is a hunk whose shape occurs once in the layer: in a
    # mechanical layer that is the hand edit, and a value-only edit counts
    # because the shape holds the removed and the added line together.
    shape_counts: Counter[str] = Counter(hunk_shape(h) for h in hand_hunks)
    outliers = sorted(
        (h for h in hand_hunks if shape_counts[hunk_shape(h)] == 1), key=lambda h: (h.changed_lines, h.ref)
    )
    first_by_shape: dict[str, Hunk] = {}
    for h in hand_hunks:
        shape = hunk_shape(h)
        if shape_counts[shape] > 1:
            first_by_shape.setdefault(shape, h)
    dominant_share = (sum(c for _, c in dirs.most_common(3)) / len(files)) if files else 0.0
    dir_outliers = (
        sorted(
            f.path
            for f in files
            if dirs[top_dir(f.path)] <= 2 and not f.binary and classes_by_path[f.path] != "generated"
        )
        if len(files) >= 10 and dominant_share >= 0.70
        else []
    )
    summary = LayerLedger(
        position=position,
        files=len(files),
        changed_lines=changed_lines,
        generated_lines=generated_lines,
        hunks=len(hand_hunks),
        generated_hunks=generated_hunks,
        classes=dict(classes),
        generated_files=sorted(generated_files),
        dir_histogram=dict(dirs.most_common(8)),
        dir_outliers=dir_outliers,
        line_shapes=len(line_counts),
        repeated_line_coverage=round(coverage, 3),
        mechanical=mechanical,
        exemplars=[h.ref for h in first_by_shape.values()],
        outliers=[h.ref for h in outliers],
        binary_files=binary,
        deleted_files=deleted,
    )
    return summary, _LayerWork(
        files,
        classes_by_path,
        hand_hunks,
        [h.ref for h in outliers],
        [h.ref for h in first_by_shape.values()],
    )


def build_ledger(
    layers: dict[int, list[FileDiff]],
    generated_globs: tuple[str, ...] | list[str] = DEFAULT_GENERATED_GLOBS,
    read_budget: int = DEFAULT_READ_BUDGET,
    full_read_max_lines: int = DEFAULT_FULL_READ_MAX_LINES,
) -> Ledger:
    by_file: dict[str, list[int]] = defaultdict(list)
    for position in sorted(layers):
        for f in layers[position]:
            by_file[f.path].append(position)
    overlap = {p: ls for p, ls in sorted(by_file.items()) if len(ls) > 1}
    pairs: Counter[str] = Counter("+".join(str(x) for x in ls) for ls in overlap.values())

    detectors: dict[str, list[dict[str, object]]] = {
        "release_note_in_several_layers": [],
        "generated_in_several_layers": [],
        "lock_without_manifest": [],
    }
    for path, ls in overlap.items():
        if matches_any(path, RELEASE_NOTE_GLOBS):
            detectors["release_note_in_several_layers"].append({"path": path, "layers": ls})
        if matches_any(path, generated_globs):
            detectors["generated_in_several_layers"].append({"path": path, "layers": ls})
    for path, ls in by_file.items():
        name = PurePosixPath(path).name
        if name not in LOCK_MANIFESTS:
            continue
        parent = str(PurePosixPath(path).parent)
        manifest_layers: set[int] = set()
        for manifest in LOCK_MANIFESTS[name]:
            manifest_path = manifest if parent == "." else f"{parent}/{manifest}"
            manifest_layers.update(by_file.get(manifest_path, []))
        for layer in ls:
            if manifest_layers and layer not in manifest_layers:
                detectors["lock_without_manifest"].append(
                    {"path": path, "layer": layer, "manifest_layers": sorted(manifest_layers)}
                )

    summaries: dict[int, LayerLedger] = {}
    work: dict[int, _LayerWork] = {}
    for pos in sorted(layers):
        summaries[pos], work[pos] = _summarise_layer(pos, layers[pos], generated_globs)
    # Files several layers edit are Tier A by construction; they are not
    # "off-theme" for any of them.
    for ll in summaries.values():
        ll.dir_outliers = [p for p in ll.dir_outliers if p not in overlap]

    read_fully: dict[str, list[int]] = dict(overlap)
    for entries in detectors.values():
        for entry in entries:
            path = str(entry["path"])
            read_fully.setdefault(path, sorted(by_file[path]))

    # Pass 1 — plan. Generated-only layers are skipped. Every other layer is
    # read in full while it fits the per-layer limit and the shared budget,
    # spent on hand-written layers first and mechanical layers last so a
    # demotion lands where an exemplar loses least.
    budget_left = read_budget
    demoted_hand_written: list[int] = []
    for ll in sorted(summaries.values(), key=lambda x: (x.mechanical, x.changed_lines)):
        if ll.files > 0 and ll.changed_lines == 0:
            ll.plan, ll.plan_reason = "skip", "generated or binary files only"
            continue
        if ll.changed_lines <= full_read_max_lines and ll.changed_lines <= budget_left:
            ll.plan, ll.plan_reason = "full", f"{ll.changed_lines} hand-written lines"
            budget_left -= ll.changed_lines
            continue
        ll.plan = "exemplar"
        ll.plan_reason = (
            f"{ll.changed_lines} hand-written lines exceed the per-layer limit of {full_read_max_lines}"
            if ll.changed_lines > full_read_max_lines
            else f"read budget of {read_budget} lines exhausted"
        )
        if not ll.mechanical:
            demoted_hand_written.append(ll.position)

    # Pass 2 — what each layer reads. Tier A (overlap and detector files,
    # off-theme files) and the exemplars are always planned and never count
    # against any share. Outliers are all planned in a mechanical layer (they
    # are the hand edits); a demoted hand-written layer ranks them by class,
    # then smallest first, and takes every one that still fits its equal
    # share of the budget the full reads left over — skipping, not stopping
    # at, a hunk too large for what is left.
    share = (budget_left // len(demoted_hand_written)) if demoted_hand_written else 0
    for pos, ll in summaries.items():
        w = work[pos]
        hunk_by_ref = {h.ref: h for h in w.hand_hunks}
        overlap_refs = [h.ref for h in w.hand_hunks if h.path in read_fully]
        ll.overlap_hunks = len(overlap_refs)
        if ll.plan == "skip":
            continue
        if ll.plan == "full":
            ll.planned_hunk_refs = [h.ref for h in w.hand_hunks]
            ll.planned_hunks = len(w.hand_hunks)
            ll.planned_lines = ll.changed_lines
            ll.outliers_planned = len(w.outlier_refs)
            continue
        planned: dict[str, Hunk] = {}
        for ref in overlap_refs + w.exemplar_refs:
            planned[ref] = hunk_by_ref[ref]
        for h in w.hand_hunks:
            if h.path in ll.dir_outliers:
                planned[h.ref] = h
        if ll.mechanical:
            chosen = list(w.outlier_refs)
            ll.outliers_in_share = sum(1 for r in chosen if r not in planned)
        else:
            ll.outlier_share = share
            spent = 0
            chosen = []
            ranked = sorted(
                (hunk_by_ref[r] for r in w.outlier_refs),
                key=lambda h: (CLASS_RANK.get(w.classes_by_path[h.path], 5), h.changed_lines, h.ref),
            )
            for h in ranked:
                if h.ref in planned:
                    chosen.append(h.ref)
                    continue
                if spent + h.changed_lines > share:
                    continue
                chosen.append(h.ref)
                spent += h.changed_lines
                ll.outliers_in_share += 1
        for ref in chosen:
            planned[ref] = hunk_by_ref[ref]
        ll.outliers_planned = len(chosen)
        ll.planned_hunk_refs = sorted(planned, key=lambda r: (hunk_by_ref[r].path, hunk_by_ref[r].new_start))
        ll.planned_hunks = len(planned)
        ll.planned_lines = sum(h.changed_lines for h in planned.values())

    layer_ledgers = [summaries[pos] for pos in sorted(summaries)]
    return Ledger(
        layers=layer_ledgers,
        distinct_files=len(by_file),
        overlap=overlap,
        overlap_pairs=dict(pairs.most_common()),
        detectors=detectors,
        read_fully_files=read_fully,
        touched_files=sorted(by_file),
        read_budget=read_budget,
        full_read_max_lines=full_read_max_lines,
        planned_total_hunks=sum(ll.planned_hunks for ll in layer_ledgers),
        total_hunks=sum(ll.hunks for ll in layer_ledgers),
        total_generated_hunks=sum(ll.generated_hunks for ll in layer_ledgers),
    )


def render(ledger: Ledger) -> str:
    """Render the coverage table and detector hits as markdown."""
    lines = [
        "| Layer | Files | Hand-written lines | Generated lines | Hand-written hunks | Mechanical | Plan | Hunks to read | Why |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for ll in ledger.layers:
        lines.append(
            f"| {ll.position} | {ll.files} | {ll.changed_lines} | {ll.generated_lines} | {ll.hunks} | "
            f"{'yes' if ll.mechanical else 'no'} | {ll.plan} | {ll.planned_hunks} | {ll.plan_reason} |"
        )
    lines.append("")
    lines.append(
        f"Distinct files: {ledger.distinct_files}. Files touched by more than one layer: {len(ledger.overlap)} "
        f"(all read in full). Hand-written hunks planned: {ledger.planned_total_hunks} of {ledger.total_hunks} "
        f"({sum(ll.planned_lines for ll in ledger.layers)} of {sum(ll.changed_lines for ll in ledger.layers)} hand-written lines); "
        f"{ledger.total_generated_hunks} hunks in generated or binary files are counted, never read. "
        f"Budget {ledger.read_budget} lines, per-layer limit {ledger.full_read_max_lines} lines."
    )
    if ledger.overlap:
        lines.append("")
        lines.append("Files touched by several layers:")
        for path, ls in ledger.overlap.items():
            lines.append(f"- `{path}` — layers {', '.join(map(str, ls))}")
    for name, entries in ledger.detectors.items():
        if entries:
            lines.append("")
            lines.append(f"Detector `{name}`:")
            for entry in entries:
                lines.append(f"- {json.dumps(entry)}")
    for ll in ledger.layers:
        if ll.plan == "exemplar":
            lines.append("")
            already = ll.outliers_planned - ll.outliers_in_share
            how = (
                "all read: in a mechanical layer every outlier is a hand edit"
                if ll.mechanical
                else f"ranked source > config > test > docs, smallest first, within a {ll.outlier_share}-line share"
            )
            lines.append(
                f"Layer {ll.position}: {len(ll.exemplars)} exemplar hunks, outliers {ll.outliers_in_share} of {len(ll.outliers)} ({how}"
                f"{f'; {already} more already read as overlap or off-theme' if already else ''}), "
                f"{ll.overlap_hunks} overlap-file hunks, {len(ll.dir_outliers)} off-theme files; "
                f"{ll.planned_lines} of {ll.changed_lines} hand-written lines planned; "
                f"{ll.line_shapes} line shapes, repeated ones cover {ll.repeated_line_coverage:.0%}; "
                f"{ll.hunks - ll.planned_hunks} hunks not read"
            )
            for ref in ll.planned_hunk_refs:
                lines.append(f"- `{ref}`")
    generated = [(ll.position, ll.generated_files) for ll in ledger.layers if ll.generated_files]
    if generated:
        lines.append("")
        lines.append("Generated or binary files (counted, never read) — check the tagging:")
        for position, files in generated:
            shown = ", ".join(f"`{f}`" for f in files[:12])
            more = f" … and {len(files) - 12} more" if len(files) > 12 else ""
            lines.append(f"- layer {position}: {shown}{more}")
    return "\n".join(lines) + "\n"


def render_hunks(ledger: Ledger, position: int, files: list[FileDiff], everything: bool = False) -> str:
    """Print a layer's planned hunks with new-side line numbers, for reading and anchoring notes."""
    ll = next((x for x in ledger.layers if x.position == position), None)
    if ll is None:
        raise SystemExit(f"layer {position} is not in the ledger")
    wanted = None if everything else set(ll.planned_hunk_refs)
    tags = dict.fromkeys(ll.exemplars, "exemplar")
    tags.update(dict.fromkeys(ll.outliers, "outlier"))
    out: list[str] = []
    for f in files:
        if f.path in ll.generated_files or f.binary:
            continue
        for h in f.hunks:
            if wanted is not None and h.ref not in wanted:
                continue
            tag = tags.get(h.ref, "full")
            if f.path in ledger.overlap:
                tag += ", overlap"
            if f.path in ll.dir_outliers:
                tag += ", off-theme"
            out.append(f"### {position}:{h.span} ({tag})")
            new_no = h.new_start
            for line in h.lines:
                if line.startswith("-"):
                    out.append(f"      -|{line[1:]}")
                else:
                    out.append(f"{new_no:>6} {line[:1]}|{line[1:]}")
                    new_no += 1
            out.append("")
    return "\n".join(out) + ("\n" if out else "")


def _parse_layer_arg(value: str) -> tuple[int, str]:
    position, sep, path = value.partition("=")
    if not sep or not position.isdigit():
        raise argparse.ArgumentTypeError("expected <position>=<diff-file>")
    return int(position), path


def _load_ledger(path: str) -> Ledger:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return Ledger(layers=[LayerLedger(**layer) for layer in data.pop("layers")], **data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ledger_cmd = sub.add_parser("ledger", help="build the ledger JSON from layer diffs")
    ledger_cmd.add_argument(
        "--layer", action="append", required=True, type=_parse_layer_arg, metavar="POS=DIFF"
    )
    ledger_cmd.add_argument(
        "--generated-globs", default="", help="comma-separated extra generated-file globs"
    )
    ledger_cmd.add_argument(
        "--gitattributes", help="a .gitattributes whose linguist-generated entries count as generated"
    )
    ledger_cmd.add_argument(
        "--read-budget",
        type=int,
        default=DEFAULT_READ_BUDGET,
        help="hand-written lines read in full across the stack",
    )
    ledger_cmd.add_argument(
        "--full-read-max-lines",
        type=int,
        default=DEFAULT_FULL_READ_MAX_LINES,
        help="largest layer still read in full",
    )
    render_cmd = sub.add_parser("render", help="render a ledger JSON as markdown")
    render_cmd.add_argument("ledger_json")
    hunks_cmd = sub.add_parser("hunks", help="print a layer's planned hunks with new-side line numbers")
    hunks_cmd.add_argument("ledger_json")
    hunks_cmd.add_argument("--layer", required=True, type=_parse_layer_arg, metavar="POS=DIFF")
    hunks_cmd.add_argument(
        "--all", action="store_true", help="every hand-written hunk, not only the planned ones"
    )
    args = parser.parse_args(argv)

    if args.command == "render":
        sys.stdout.write(render(_load_ledger(args.ledger_json)))
        return 0
    if args.command == "hunks":
        position, path = args.layer
        with open(path, encoding="utf-8", errors="replace") as fh:
            files = parse_unified_diff(fh.read())
        sys.stdout.write(render_hunks(_load_ledger(args.ledger_json), position, files, args.all))
        return 0

    globs = list(DEFAULT_GENERATED_GLOBS)
    if args.generated_globs:
        globs.extend(g.strip() for g in args.generated_globs.split(",") if g.strip())
    if args.gitattributes:
        with open(args.gitattributes, encoding="utf-8") as fh:
            globs.extend(parse_gitattributes_generated(fh.read()))
    layers: dict[int, list[FileDiff]] = {}
    for position, path in args.layer:
        with open(path, encoding="utf-8", errors="replace") as fh:
            layers[position] = parse_unified_diff(fh.read())
    ledger = build_ledger(layers, globs, args.read_budget, args.full_read_max_lines)
    json.dump(asdict(ledger), sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
