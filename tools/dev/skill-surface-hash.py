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

The skill cannot compute this itself at invocation time. An agent reads a
`SKILL.md` as static instructions — there is no code execution hook on most
harnesses (the same constraint `check-skill-preflight.py` documents), so the
skill has no way to hash its own body and compare it against what the
adopter last reconciled against. The fingerprint has to be computed once,
here, deterministically, and carried in the frontmatter where the skill (or
a future reconciliation check) can read it as plain data.

So: **one generator, one derived field per skill.** `surface_hash(text)`
folds `requires_config:` (order-independent — a re-sorted list is not a
change) and the sorted set of structural anchors (`##`/`###` headings and
`**Golden rule ...**` callouts, markdown decoration stripped so `**Step
1**` and `Step 1` hash the same) into a short `sha256:` digest, deliberately
excluding the shared pre-flight block that `check-skill-preflight.py`
manages — that block is identical everywhere and moving it is a framework
change, not a project-specific reconciliation event — and deliberately
excluding ordinary prose, which is free to be reworded without telling
every adopter their configuration went stale.

Unlike the pre-flight-block hook, this script exempts nothing. The `setup`
family is exempt from the pre-flight block because those are the skills
that *perform* setup and would otherwise ask users to set up before setting
up — but a `setup` skill's own configuration surface (its `requires_config:`
list, its steps) can drift just like any other skill's, and a project can
fall out of sync with it the same way. Every skill gets a hash.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SKILLS = Path("skills")

BEGIN = "<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->"
END = "<!-- END MAGPIE PREFLIGHT -->"
PREFLIGHT_RE = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.S)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
REQUIRES_RE = re.compile(r"^requires_config:\n((?:[ \t]+-[ \t]*\S+\n)+)", re.M)
ITEM_RE = re.compile(r"^[ \t]+-[ \t]*(\S+)[ \t]*$", re.M)
HEADING_RE = re.compile(r"^#{2,3}[ \t]+(.+?)[ \t]*$", re.M)
GOLDEN_RE = re.compile(r"^\*\*(Golden rule[^*]+)\*\*", re.M)
HASH_RE = re.compile(r"^surface_hash:[ \t]*\S+\n", re.M)


def _normalise(text: str) -> str:
    """Anchor text without markdown decoration, so `**Step 1**` == `Step 1`."""
    text = re.sub(r"[`*_]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def surface_inputs(text: str) -> tuple[list[str], list[str]]:
    """Return `(requires_config, anchors)` — the two inputs the hash folds in."""
    front = FRONTMATTER_RE.match(text)
    body = text[front.end() :] if front else text
    body = PREFLIGHT_RE.sub("", body)

    requires: list[str] = []
    block = REQUIRES_RE.search(front.group(1) + "\n") if front else None
    if block:
        requires = sorted(ITEM_RE.findall(block.group(1)))

    anchors = sorted(
        {_normalise(m) for m in HEADING_RE.findall(body)} | {_normalise(m) for m in GOLDEN_RE.findall(body)}
    )
    return requires, anchors


def surface_hash(text: str) -> str:
    """The reconciliation fingerprint: `sha256:` plus the first 16 hex characters."""
    requires, anchors = surface_inputs(text)
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
        digest = surface_hash(text)
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
