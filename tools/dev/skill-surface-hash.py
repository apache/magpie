#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Stamp a reconciliation fingerprint (`surface_hash:`) into every
`skills/*/SKILL.md`.

A running skill needs to answer a question it cannot answer by inspecting
itself: *has my own reconciliation surface moved since this project was last
configured for me?* "Surface" here means the two things an adopter's
configuration actually has to track — the skill's `requires_config:` list
(which project files it reads) and its structural anchors (the step and
golden-rule headings that name the contract the skill executes). A reworded
paragraph is not a surface change; a renamed step or an added config
dependency is.

A skill's anchors are not confined to its own `SKILL.md`. A multi-file
skill (`setup`, `pr-management-triage`, `security-issue-sync`, …) keeps
steps and golden rules in sibling detail files, and an adopter override can
anchor to a heading there just as easily as to one in `SKILL.md` itself. So
the fingerprint spans the skill's whole **directory**: `SKILL.md` plus every
`*.md` file directly inside it (no recursion into subdirectories such as
`guards/` or `fixtures/`), each with the generated pre-flight region
stripped. The file a heading came from is folded into the hashed payload
alongside the heading text — otherwise a heading moving from one detail
file to another, or between `SKILL.md` and a detail file, would leave the
digest unchanged, which is exactly the class of silent drift this
fingerprint exists to catch. `requires_config:` still comes from
`SKILL.md`'s frontmatter alone; detail files carry no frontmatter of their
own. One detail file is excluded by name: `preflight-detail.md`, the
generated pre-flight sidecar, which is byte-identical in all 65 skills that
carry it — hashing it would move every digest on every edit to that shared
text and tell every adopter their configuration went stale when nothing
about their skill changed. That is the same reason the generated pre-flight
region inside `SKILL.md` is stripped.

The skill cannot compute this itself at invocation time. An agent reads a
`SKILL.md` as static instructions — there is no code execution hook on most
harnesses (the same constraint `check-shared-blocks.py` documents), so the
skill has no way to hash its own body and compare it against what the
adopter last reconciled against. The fingerprint has to be computed once,
here, deterministically, and carried in the frontmatter where the skill (or
a future reconciliation check) can read it as plain data.

So: **one generator, one derived field per skill.** `surface_hash(skill_dir)`
folds `requires_config:` (order-independent — a re-sorted list is not a
change) and the sorted set of structural anchors, tagged with the file each
came from (`##` through `####` headings and `**Golden rule ...**` callouts,
markdown decoration stripped so `**Step 1**` and `Step 1` hash the same)
into a short `sha256:` digest, deliberately
excluding the shared pre-flight block that `check-shared-blocks.py`
manages — that block is identical everywhere and moving it is a framework
change, not a project-specific reconciliation event — and deliberately
excluding ordinary prose, which is free to be reworded without telling
every adopter their configuration went stale.

Fourth-level headings count. Twelve shipped skills use `####` for real
structure — `#### Pass B — Security`, `#### Category C — ...`, `#### 4c-ii
— ...` — and an override anchors to one of those exactly as it anchors to
a `##` step. Stopping at `###` left those renames silent, which is the
class of drift this fingerprint exists to catch. `#####` and deeper stay
out: nothing in the catalogue uses them as a contract surface.

Unlike the shared-blocks hook, this script exempts nothing. The `setup`
family is exempt from the pre-flight block because those are the skills
that *perform* setup and would otherwise ask users to set up before setting
up — but a `setup` skill's own configuration surface (its `requires_config:`
list, its steps) can drift just like any other skill's, and a project can
fall out of sync with it the same way. Every skill gets a hash.

**Stated consequence of the exclusion.** A heading that lives *inside* a
generated region — the auto pre-flight block, or any declared block — is
never a structural anchor, on purpose: editing shared framework prose is a
framework change, not a project-specific reconciliation event, and it must
not tell every adopter their own configuration drifted. The trade this
buys is real and deliberate, not an accident of a regex: an override
anchored to a heading that happens to live inside shared text will **not**
be detected as drift by this fingerprint. That is correct for the same
reason the exclusion exists — the shared text is framework-owned, not
project-owned — but it means `surface_hash` alone cannot catch every stale
override; an override anchored inside a shared block relies on the shared
block itself staying stable, not on this fingerprint.

This script does not keep its own copy of what "a generated region" looks
like. It loads `check-shared-blocks.py` — the script that actually writes
every generated region — and reuses its `PREFLIGHT_RE`, `DECLARED_RE`, and
`strip_generated_regions()` directly, so the two scripts' notion of
"generated" cannot drift apart: a `check-shared-blocks.py` marker-format
change is automatically picked up here, rather than requiring a matching
edit to a second regex that happened to also know about markers.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType


def _load_shared_blocks() -> ModuleType:
    """Load `check-shared-blocks.py` as a module so this script can reuse
    its marker regexes and `strip_generated_regions()` directly, instead of
    keeping a second, driftable definition of "a generated region" here."""
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
strip_generated_regions = _SHARED_BLOCKS.strip_generated_regions

SKILLS = Path("skills")

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
REQUIRES_RE = re.compile(r"^requires_config:\n((?:[ \t]+-[ \t]*\S+\n)+)", re.M)
ITEM_RE = re.compile(r"^[ \t]+-[ \t]*(\S+)[ \t]*$", re.M)
HEADING_RE = re.compile(r"^#{2,4}[ \t]+(.+?)[ \t]*$", re.M)
GOLDEN_RE = re.compile(r"^\*\*(Golden rule[^*]+)\*\*", re.M)
HASH_RE = re.compile(r"^surface_hash:[ \t]*\S+\n", re.M)


def _normalise(text: str) -> str:
    """Anchor text without markdown decoration, so `**Step 1**` == `Step 1`."""
    text = re.sub(r"[`*_]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _anchors_in(body: str) -> set[str]:
    """Structural anchors (headings + golden-rule callouts) in one file's body."""
    return {_normalise(m) for m in HEADING_RE.findall(body)} | {
        _normalise(m) for m in GOLDEN_RE.findall(body)
    }


# `SKILL.md` is hashed separately (its frontmatter supplies `requires_config`),
# and `preflight-detail.md` is the generated pre-flight sidecar
# `check-shared-blocks.py` writes into every non-exempt skill directory. The
# sidecar is excluded for the same reason the generated pre-flight region
# inside `SKILL.md` is: it is identical in all 65 skills, so including it
# would move every digest on every edit to the shared text and tell every
# adopter their configuration went stale when nothing about their skill
# changed.
EXCLUDED_DETAIL_FILES = frozenset({"SKILL.md", "preflight-detail.md"})


def surface_inputs(skill_dir: Path) -> tuple[list[str], list[str]]:
    """Return `(requires_config, anchors)` — the two inputs the hash folds in.

    `requires_config` comes from `SKILL.md`'s frontmatter alone.
    `anchors` spans `SKILL.md` and every sibling `*.md` file directly inside
    `skill_dir` (sorted by filename; no recursion into subdirectories).
    `SKILL.md`'s own anchors stay bare, exactly as the pre-widening
    algorithm recorded them, so a skill directory with no detail files
    hashes identically to before. Each detail file's anchors are recorded
    as `"<filename>: <anchor>"`, appended in sorted-filename order after
    `SKILL.md`'s — the file an anchor came from is part of the payload, so
    a heading moving between files (including into or out of `SKILL.md`)
    changes the hash even though the heading text itself did not.
    """
    text = (skill_dir / "SKILL.md").read_text()
    front = FRONTMATTER_RE.match(text)
    body = text[front.end() :] if front else text
    body = strip_generated_regions(body)

    requires: list[str] = []
    block = REQUIRES_RE.search(front.group(1) + "\n") if front else None
    if block:
        requires = sorted(ITEM_RE.findall(block.group(1)))

    anchors = sorted(_anchors_in(body))

    detail_files = sorted(
        (
            p
            for p in skill_dir.iterdir()
            if p.is_file() and p.suffix == ".md" and p.name not in EXCLUDED_DETAIL_FILES
        ),
        key=lambda p: p.name,
    )
    for detail in detail_files:
        detail_body = strip_generated_regions(detail.read_text())
        for anchor in sorted(_anchors_in(detail_body)):
            anchors.append(f"{detail.name}: {anchor}")

    return requires, anchors


def surface_hash(skill_dir: Path) -> str:
    """The reconciliation fingerprint: `sha256:` plus the first 16 hex characters."""
    requires, anchors = surface_inputs(skill_dir)
    payload = "\n".join(["requires_config:", *requires, "anchors:", *anchors])
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def apply(path: Path, digest: str) -> tuple[bool, str | None]:
    """Return (changed, error). Rewrites `path` only when it differs.

    Removes any existing `surface_hash:` line from the frontmatter and
    re-inserts the given digest immediately before `license:` — a stable
    position, and `license:` is required on every skill.
    """
    text = path.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        return False, f"{path}: no YAML frontmatter"

    lines = [line for line in match.group(1).split("\n") if not HASH_RE.match(line + "\n")]
    try:
        index = next(i for i, line in enumerate(lines) if line.startswith("license:"))
    except StopIteration:
        return False, f"{path}: no 'license:' line to anchor surface_hash to"
    lines.insert(index, f"surface_hash: {digest}")

    updated = text[: match.start()] + "---\n" + "\n".join(lines) + "\n---\n" + text[match.end() :]
    if updated == text:
        return False, None
    path.write_text(updated)
    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="write the surface_hash field into every SKILL.md instead of only reporting",
    )
    args = parser.parse_args()

    skills = sorted(SKILLS.glob("*/SKILL.md"))
    if not skills:
        print(f"{SKILLS}: no SKILL.md files found", file=sys.stderr)
        return 1

    errors: list[str] = []
    changed: list[Path] = []
    for path in skills:
        text = path.read_text()
        digest = surface_hash(path.parent)
        if args.fix:
            did, err = apply(path, digest)
            if err:
                errors.append(err)
            elif did:
                changed.append(path)
        else:
            if f"surface_hash: {digest}" not in text:
                errors.append(f"{path}: surface_hash is missing or stale (expected {digest})")

    if errors:
        print("Skill surface_hash is out of sync:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if not args.fix:
            print(
                f"\nRun `python3 {Path(__file__).name} --fix`.",
                file=sys.stderr,
            )
        return 1
    if changed:
        print(f"Updated surface_hash in {len(changed)} skill(s):")
        for path in changed:
            print(f"  - {path}")
        return 1
    print(f"surface_hash in sync across {len(skills)} skills.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
