#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Keep every shared prose block present and identical between its one
source and every place that carries a copy.

This generalises `check-skill-preflight.py` (retired — this script replaces
it rather than sitting beside it) from *one* shared block to *any number*.
The reasoning that motivated the original script carries over unchanged:

Every framework skill has to answer the same question before it does
anything: *has this project actually been set up for the framework version
now installed?* That check cannot be a hook — on most harnesses **no code
executes when a plugin is installed or upgraded** (Agent Plugins 1.0 defines
no hook component at all, and Claude Code's `SessionStart` hook is wired
only into `magpie-setup`) — so it has to be *agentic*, instructions the
agent reads when the skill is invoked, which means it has to live in the
skill body. It also cannot be an include: a family plugin contains
`plugins/magpie-<family>/skills/<skill>` symlinked to `skills/<skill>`, and
Agent Plugins 1.0 forbids a symlink whose final target escapes the plugin
root, so a shared file at `skills/_shared/` would be unreachable from the
install shape most adopters use. Every skill needs its own copy of the
text. So: **one source, many generated copies**, with a pre-commit hook
that runs this script with `--fix` so editing the source is the whole
workflow and drift is repaired rather than merely reported.

That single-block story does not scale by hand to a second, third, and
fourth repeated paragraph (the git-repo + main-checkout pre-check shared by
`install.md`/`uninstall.md`, the ASF-detection step shared by
`upgrade.md`/`verify.md`, worktree enumeration, the sandbox-allowlist
helper chain, …) without either duplicating this whole script per block or
inventing a second propagation mechanism — which would just be the
duplication this repository exists to remove, one layer up. This script is
the one mechanism for both shapes:

* **The auto block** (`preflight`) is inserted by this tool into every
  eligible target that lacks one and removed from every target that has
  become exempt — `check-skill-preflight.py`'s exact historical behaviour:
  same source (`tools/dev/preflight-block.md`), same delimiter comment
  text, same insertion point (immediately after the first body-level `#`
  heading), same exemption list read from live `family:` frontmatter. The
  source deliberately stays at its historical path and the delimiter text
  is byte-for-byte what `check-skill-preflight.py` emitted: every one of
  the 65 propagated copies is unaffected by this script replacing that one,
  and `skill-surface-hash.py`'s exclusion of the block from a skill's
  reconciliation fingerprint needs no matching update.
* **Declared blocks** are any number of additional named blocks, sourced
  from `tools/dev/blocks/<name>.md`. A target opts in by already carrying a
  delimited region for that name — `<!-- BEGIN MAGPIE BLOCK: <name> —
  generated from tools/dev/blocks/<name>.md --> ... <!-- END MAGPIE BLOCK:
  <name> -->` — empty or already filled. This script only ever *fills* that
  region; it never inserts one, because a declared block's anchor point
  (which paragraph, in which file) is a per-block editorial decision the
  extraction that adds the block makes once, not something this generic
  tool should guess at. A target that names a block with no matching
  `tools/dev/blocks/<name>.md` is an error, never a silent skip — including
  when the source existed at some point and was since removed while a
  target still declares it: the stale text is left exactly as it was and
  the run fails, rather than quietly blanking or quietly ignoring it.
  Declared-block targets are restricted to the `skills/` tree (the same
  root `skill-surface-hash.py` walks) — a region discovered outside it is
  rejected rather than filled, so the mechanism cannot be used to
  propagate prose into arbitrary documentation by accident.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILLS = Path("skills")
ALLOWED_ROOTS: tuple[Path, ...] = (SKILLS,)

BLOCKS_DIR = Path("tools/dev/blocks")

# --- the auto block: preflight ----------------------------------------------------
#
# Kept byte-for-byte identical to `check-skill-preflight.py`'s constants and
# logic: same source path, same delimiter text, same insertion rule. None of
# the 65 propagated copies change because this script replaces that one.

PREFLIGHT_SOURCE = Path("tools/dev/preflight-block.md")
PREFLIGHT_BEGIN = "<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->"
PREFLIGHT_END = "<!-- END MAGPIE PREFLIGHT -->"
# Matches the whole delimited region including a trailing blank line, so a
# repeated --fix neither duplicates the block nor accumulates whitespace.
PREFLIGHT_RE = re.compile(
    re.escape(PREFLIGHT_BEGIN) + r".*?" + re.escape(PREFLIGHT_END) + r"\n*",
    re.S,
)

# The `setup` family is exempt, and the exemption is the point rather than an
# oversight: these are the skills that *perform* the setup. A pre-flight
# telling the agent to run `/magpie-setup` before running `/magpie-setup` is
# a loop, and `setup-isolated-setup-install` in particular has to work on a
# repo that has deliberately adopted nothing yet. Membership is read from the
# live `family:` frontmatter, so the exemption cannot drift from the family
# it names.
EXEMPT_FAMILIES = frozenset({"setup"})

FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
HEADING_RE = re.compile(r"^# .*$", re.M)
FAMILY_RE = re.compile(r"^family:[ \t]*(\S+)[ \t]*$", re.M)


def family_of(text: str) -> str | None:
    match = FAMILY_RE.search(text)
    return match.group(1) if match else None


def _strip_licence_header(raw: str) -> str:
    """Drop a source file's own licence header, if it is the very first
    thing in the file — each target already carries one of its own, and a
    second would render inside the target's body."""
    return re.sub(r"^<!--\s*SPDX-License-Identifier.*?-->\n+", "", raw, flags=re.S)


def preflight_block_text(source: Path = PREFLIGHT_SOURCE) -> str:
    """The generated auto-block region: delimiters around the source
    file's body, exactly as `check-skill-preflight.py`'s `block_text()`
    produced it."""
    raw = source.read_text()
    body = _strip_licence_header(raw)
    return f"{PREFLIGHT_BEGIN}\n\n{body.strip()}\n\n{PREFLIGHT_END}\n"


def apply_preflight(path: Path, block: str) -> tuple[bool, str | None]:
    """Return (changed, error). Rewrites `path` only when it differs.
    Identical to `check-skill-preflight.py`'s `apply()`."""
    text = path.read_text()
    stripped = PREFLIGHT_RE.sub("", text)

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


# --- declared blocks ----------------------------------------------------------------

_BLOCK_NAME = r"[a-z][a-z0-9-]*"
# Discovers a declared-block region by name, wherever it appears — the name
# in BEGIN and END must match (backreference), so a truncated or mismatched
# pair is never silently treated as a region.
DECLARED_RE = re.compile(
    r"<!-- BEGIN MAGPIE BLOCK: (?P<name>" + _BLOCK_NAME + r") — generated from \S+ -->\n"
    r"(?P<body>.*?)"
    r"<!-- END MAGPIE BLOCK: (?P=name) -->\n",
    re.S,
)


def declared_block_source(name: str, blocks_dir: Path = BLOCKS_DIR) -> Path:
    return blocks_dir / f"{name}.md"


def declared_block_text(name: str, blocks_dir: Path = BLOCKS_DIR) -> str:
    """The generated region for a declared block. Raises `FileNotFoundError`
    when the named block has no source — callers turn that into a reported
    error rather than letting it propagate as a crash."""
    source = declared_block_source(name, blocks_dir)
    if not source.is_file():
        raise FileNotFoundError(source)
    raw = source.read_text()
    body = _strip_licence_header(raw)
    begin = f"<!-- BEGIN MAGPIE BLOCK: {name} — generated from {source.as_posix()} -->"
    end = f"<!-- END MAGPIE BLOCK: {name} -->"
    return f"{begin}\n\n{body.strip()}\n\n{end}\n"


def fill_declared(text: str, blocks_dir: Path = BLOCKS_DIR) -> tuple[str, list[str]]:
    """Fill every declared-block region found in `text` from `blocks_dir`.

    Returns `(new_text, errors)`. A region naming a block with no matching
    source file is left exactly as it was in `text` and reported as an
    error — never silently dropped, never silently left stale without
    comment.
    """
    errors: list[str] = []

    def _replace(match: re.Match[str]) -> str:
        name = match.group("name")
        try:
            return declared_block_text(name, blocks_dir)
        except FileNotFoundError as exc:
            errors.append(f"declares unknown block '{name}' — {exc.args[0]} does not exist")
            return match.group(0)

    new_text = DECLARED_RE.sub(_replace, text)
    return new_text, errors


def is_allowed_target(path: Path, roots: tuple[Path, ...] = ALLOWED_ROOTS) -> bool:
    """A declared-block region may only be honoured inside `roots` — the
    same tree `skill-surface-hash.py` walks. This is deliberately checked
    per-file (not just enforced by what `main()` happens to glob), so a
    future caller cannot accidentally propagate shared prose into arbitrary
    documentation."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def process_declared(
    path: Path,
    *,
    blocks_dir: Path = BLOCKS_DIR,
    roots: tuple[Path, ...] = ALLOWED_ROOTS,
    fix: bool = False,
) -> tuple[bool, list[str]]:
    """Process one candidate target file for declared-block regions.

    Returns `(changed, errors)`. `changed` reports drift regardless of
    `--fix` — only `--fix` actually writes. A file with no declared-block
    marker at all is a no-op: `(False, [])`.
    """
    text = path.read_text()
    if not DECLARED_RE.search(text):
        return False, []

    if not is_allowed_target(path, roots):
        return False, [
            f"{path}: carries a declared block region but is outside the allowed roots {tuple(str(r) for r in roots)}"
        ]

    new_text, fill_errors = fill_declared(text, blocks_dir)
    errors = [f"{path}: {message}" for message in fill_errors]
    if new_text == text:
        return False, errors

    if fix:
        path.write_text(new_text)
        return True, errors
    errors.append(f"{path}: declared block(s) differ from source")
    return True, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix",
        action="store_true",
        help="write every shared block into its targets instead of only reporting",
    )
    args = parser.parse_args()

    if not PREFLIGHT_SOURCE.is_file():
        print(f"{PREFLIGHT_SOURCE}: missing — it is the only source of the pre-flight block", file=sys.stderr)
        return 1

    skills = sorted(SKILLS.glob("*/SKILL.md"))
    if not skills:
        print(f"{SKILLS}: no SKILL.md files found", file=sys.stderr)
        return 1

    errors: list[str] = []
    changed: list[Path] = []
    exempt: list[Path] = []

    # --- the auto block ---
    block = preflight_block_text()
    for path in skills:
        text = path.read_text()
        if family_of(text) in EXEMPT_FAMILIES:
            exempt.append(path)
            # An exempt skill must not carry a stale block from before it
            # was exempted, so removing one is part of keeping the set in
            # sync.
            if PREFLIGHT_RE.search(text):
                if args.fix:
                    path.write_text(PREFLIGHT_RE.sub("", text))
                    changed.append(path)
                else:
                    errors.append(f"{path}: carries the pre-flight block but its family is exempt")
            continue
        if args.fix:
            did, err = apply_preflight(path, block)
            if err:
                errors.append(err)
            elif did:
                changed.append(path)
        else:
            found = PREFLIGHT_RE.search(text)
            if not found:
                errors.append(f"{path}: missing the shared pre-flight block")
            elif found.group(0).rstrip("\n") != block.rstrip("\n"):
                errors.append(f"{path}: pre-flight block differs from {PREFLIGHT_SOURCE}")

    # --- declared blocks: every *.md directly inside a skills/<name>/ dir ---
    declared_targets = sorted(SKILLS.glob("*/*.md"))
    declared_seen = 0
    declared_changed: list[Path] = []
    for path in declared_targets:
        did_change, target_errors = process_declared(path, fix=args.fix)
        if target_errors or did_change:
            declared_seen += 1
        errors.extend(target_errors)
        if did_change and args.fix:
            declared_changed.append(path)

    if errors:
        print("Shared blocks are out of sync:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        if not args.fix:
            print(
                f"\nRun `python3 {Path(__file__).name} --fix` — or edit the source: "
                f"{PREFLIGHT_SOURCE} for the pre-flight block, {BLOCKS_DIR}/<name>.md for a "
                "declared one. Those are the only places the wording should change.",
                file=sys.stderr,
            )
        return 1
    total_changed = changed + declared_changed
    if total_changed:
        print(f"Updated shared blocks in {len(total_changed)} file(s):")
        for path in total_changed:
            print(f"  - {path}")
        return 1
    print(
        f"Pre-flight block in sync across {len(skills) - len(exempt)} skills "
        f"({len(exempt)} exempt: {', '.join(sorted(p.parent.name for p in exempt))}); "
        f"{declared_seen} declared block region(s) in sync."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
