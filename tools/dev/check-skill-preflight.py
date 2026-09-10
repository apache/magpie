#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Keep the shared setup pre-flight block present and identical in every
`skills/*/SKILL.md`.

Every framework skill has to answer the same question before it does anything:
*has this project actually been set up for the framework version now installed?*
`skills/setup/locks.md` already states that a drift check runs "on every
framework-skill invocation" — but nothing put that check in front of the agent,
so it ran nowhere.

It cannot be a hook. On most harnesses **no code executes when a plugin is
installed or upgraded**: Agent Plugins 1.0 defines no hook component at all, and
Claude Code's `SessionStart` hook is wired only into the all-in-one plugin, so a
per-family or non-Claude install has no automated moment to check anything. The
check therefore has to be *agentic* — instructions the agent reads when the
skill is invoked — which means it has to live in the skill body.

It also cannot be an include. A family plugin contains
`plugins/magpie-<family>/skills/<skill>` symlinked to `skills/<skill>`, and
Agent Plugins 1.0 forbids a symlink whose final target escapes the plugin root,
so a shared file at `skills/_shared/` would be unreachable from exactly the
install shape most adopters use (the same constraint that keeps per-family
plugins Claude Code-only). Every skill needs its own copy of the text.

So: **one source, many generated copies.** `tools/dev/preflight-block.md` is the
only place the wording is edited; this script propagates it into a delimited
block in each `SKILL.md`, and the pre-commit hook runs it with `--fix`, so
editing the source is the whole workflow and drift is repaired rather than
merely reported. The duplication costs nothing at rest: a `SKILL.md` *body* is
read only when the skill is invoked, unlike the frontmatter that
`estimate-skill-tokens.py` measures.

The block is inserted immediately after the skill's first body-level `#`
heading, so it is the first instruction the agent reads.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILLS = Path("skills")
SOURCE = Path("tools/dev/preflight-block.md")

BEGIN = "<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->"
END = "<!-- END MAGPIE PREFLIGHT -->"
# Matches the whole delimited region including a trailing blank line, so a
# repeated --fix neither duplicates the block nor accumulates whitespace.
BLOCK_RE = re.compile(
    re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n*",
    re.S,
)
FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
HEADING_RE = re.compile(r"^# .*$", re.M)
FAMILY_RE = re.compile(r"^family:[ \t]*(\S+)[ \t]*$", re.M)

# The `setup` family is exempt, and the exemption is the point rather than an
# oversight: these are the skills that *perform* the setup. A pre-flight telling
# the agent to run `/magpie-setup` before running `/magpie-setup` is a loop, and
# `setup-isolated-setup-install` in particular has to work on a repo that has
# deliberately adopted nothing yet. Membership is read from the live `family:`
# frontmatter, so the exemption cannot drift from the family it names.
EXEMPT_FAMILIES = frozenset({"setup"})


def family_of(text: str) -> str | None:
    match = FAMILY_RE.search(text)
    return match.group(1) if match else None


def block_text() -> str:
    """The generated region: delimiters around the source file's body."""
    raw = SOURCE.read_text()
    # Drop the source file's own licence header — each SKILL.md already carries
    # one, and a second would render inside the skill body.
    body = re.sub(r"^<!--\s*SPDX-License-Identifier.*?-->\n+", "", raw, flags=re.S)
    return f"{BEGIN}\n\n{body.strip()}\n\n{END}\n"


def apply(path: Path, block: str) -> tuple[bool, str | None]:
    """Return (changed, error). Rewrites `path` only when it differs."""
    text = path.read_text()
    stripped = BLOCK_RE.sub("", text)

    match = FRONTMATTER_RE.match(stripped)
    if not match:
        return False, f"{path}: no YAML frontmatter"
    heading = HEADING_RE.search(stripped, match.end())
    if not heading:
        return False, f"{path}: no body-level '# ' heading to anchor the block to"

    cut = heading.end()
    # Exactly one blank line between the heading and the block.
    rest = stripped[cut:].lstrip("\n")
    updated = f"{stripped[:cut]}\n\n{block}\n{rest}"
    if updated == text:
        return False, None
    path.write_text(updated)
    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="write the block into every SKILL.md instead of only reporting",
    )
    args = parser.parse_args()

    if not SOURCE.is_file():
        print(f"{SOURCE}: missing — it is the only source of the block", file=sys.stderr)
        return 1

    block = block_text()
    skills = sorted(SKILLS.glob("*/SKILL.md"))
    if not skills:
        print(f"{SKILLS}: no SKILL.md files found", file=sys.stderr)
        return 1

    errors: list[str] = []
    changed: list[Path] = []
    exempt: list[Path] = []
    for path in skills:
        text = path.read_text()
        if family_of(text) in EXEMPT_FAMILIES:
            exempt.append(path)
            # An exempt skill must not carry a stale block from before it was
            # exempted, so removing one is part of keeping the set in sync.
            if BLOCK_RE.search(text):
                if args.fix:
                    path.write_text(BLOCK_RE.sub("", text))
                    changed.append(path)
                else:
                    errors.append(f"{path}: carries the pre-flight block but its family is exempt")
            continue
        if args.fix:
            did, err = apply(path, block)
            if err:
                errors.append(err)
            elif did:
                changed.append(path)
        else:
            found = BLOCK_RE.search(text)
            if not found:
                errors.append(f"{path}: missing the shared pre-flight block")
            elif found.group(0).rstrip("\n") != block.rstrip("\n"):
                errors.append(f"{path}: pre-flight block differs from {SOURCE}")

    if errors:
        print("Skill pre-flight block is out of sync:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if not args.fix:
            print(
                f"\nRun `python3 {Path(__file__).name} --fix` — or edit {SOURCE}, "
                f"which is the only place the wording should change.",
                file=sys.stderr,
            )
        return 1
    if changed:
        print(f"Updated the pre-flight block in {len(changed)} skill(s):")
        for path in changed:
            print(f"  - {path}")
        return 1
    print(
        f"Pre-flight block in sync across {len(skills) - len(exempt)} skills "
        f"({len(exempt)} exempt: {', '.join(sorted(p.parent.name for p in exempt))})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
