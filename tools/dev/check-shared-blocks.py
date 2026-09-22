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

The two marker shapes are a deliberate, documented asymmetry — not a gap to
close reflexively. Unifying them (moving `preflight-block.md` under
`tools/dev/blocks/` and reformatting its delimiter) is worth doing
opportunistically, the day a later task's own churn already touches all 65
propagated copies for an unrelated reason, rather than as a standalone
change whose entire diff would be that rewrite.
"""

from __future__ import annotations

import argparse
import os
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


DOCTOC_RE = re.compile(
    r"^<!-- START doctoc.*?<!-- END doctoc[^>]*-->\n+",
    re.S,
)


def _strip_licence_header(raw: str) -> str:
    """Drop a source file's own licence header, if it is the very first
    thing in the file — each target already carries one of its own, and a
    second would render inside the target's body.

    A leading doctoc region goes the same way, and for a sharper reason: it
    is a table of contents for the *source* file, which is not the file any
    target is. One rode into all 65 propagated copies until the source was
    added to the doctoc hook's exclude list; stripping it here means a
    future source that picks one up again cannot repeat that."""
    stripped = DOCTOC_RE.sub("", raw)
    return re.sub(r"^<!--\s*SPDX-License-Identifier.*?-->\n+", "", stripped, flags=re.S)


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
# pair is never silently treated as a region. `(?P<indent>[ \t]*)`, anchored
# with `^` (needs `re.M`), captures whatever leading whitespace the BEGIN
# line carries — a region nested inside a list item's continuation is
# indented to stay part of that item; a region at the top of a document is
# not. The same backreference-on-name trick applies to indent implicitly:
# both markers are captured from the *same* match, so BEGIN and END are
# never treated as a pair unless they share both name and column.
DECLARED_RE = re.compile(
    r"^(?P<indent>[ \t]*)<!-- BEGIN MAGPIE BLOCK: (?P<name>" + _BLOCK_NAME + r") — generated from \S+ -->\n"
    r"(?P<body>.*?)"
    r"^(?P=indent)<!-- END MAGPIE BLOCK: (?P=name) -->\n",
    re.M | re.S,
)


def declared_block_source(name: str, blocks_dir: Path = BLOCKS_DIR) -> Path:
    return blocks_dir / f"{name}.md"


def _indent_body(body: str, indent: str) -> str:
    """Apply `indent` to every non-blank line of `body`. Blank lines are
    left *exactly* blank — never `indent` alone — because the
    `trailing-whitespace` prek hook strips whitespace-only lines on every
    run. If this function indented a blank line, `--fix` would write it back
    with trailing whitespace, `trailing-whitespace` would strip it again on
    the next hook in the same chain, and the two would disagree forever:
    `process_declared`'s `new_text == text` comparison would never converge,
    so `--fix` would report a change on every single run."""
    if not indent:
        return body
    return "\n".join(f"{indent}{line}" if line.strip() else "" for line in body.split("\n"))


def declared_block_text(name: str, blocks_dir: Path = BLOCKS_DIR, indent: str = "") -> str:
    """The generated region for a declared block, indented by `indent` (the
    column the host's own BEGIN marker was found at — see `DECLARED_RE`'s
    `indent` group). Raises `FileNotFoundError` when the named block has no
    source — callers turn that into a reported error rather than letting it
    propagate as a crash.

    Block *sources* under `tools/dev/blocks/` are always written flush left
    (column 0) — indentation is never baked into the source file, because
    `body.strip()` below trims only the string's true start/end, not each
    line's own leading whitespace, so a source pre-indented to "look right"
    in one host would silently lose that indent on its very first line (and
    keep it on every other) the moment it landed anywhere else. Applying
    `indent` here, once, after `.strip()`, is what lets one flat source
    render correctly whether it lands flush left (`upgrade.md`'s top-level
    `Procedure:` list) or nested three spaces under a list item
    (`install.md`'s equivalent, nested under `2. **Propagate ...**`)."""
    source = declared_block_source(name, blocks_dir)
    if not source.is_file():
        raise FileNotFoundError(source)
    raw = source.read_text()
    body = _strip_licence_header(raw).strip()
    indented_body = _indent_body(body, indent)
    begin = f"{indent}<!-- BEGIN MAGPIE BLOCK: {name} — generated from {source.as_posix()} -->"
    end = f"{indent}<!-- END MAGPIE BLOCK: {name} -->"
    return f"{begin}\n\n{indented_body}\n\n{end}\n"


def strip_generated_regions(text: str) -> str:
    """Remove every generated region — the auto preflight block *and* any
    declared block — from `text`.

    This is the one place both marker shapes are combined for exclusion.
    `skill-surface-hash.py` loads this module and calls this exact
    function rather than keeping a second, driftable copy of what "a
    generated region" looks like: a `PREFLIGHT_RE`-only strip was correct
    only while zero declared blocks existed, and the moment one lands in a
    shared detail file, its headings must disappear from the fingerprint
    the same way the pre-flight block's always have — editing shared
    framework text is a framework change, not a project-specific
    reconciliation event. See `skill-surface-hash.py`'s module docstring
    for the stated consequence of that exclusion.
    """
    text = PREFLIGHT_RE.sub("", text)
    text = DECLARED_RE.sub("", text)
    return text


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
        indent = match.group("indent")
        try:
            return declared_block_text(name, blocks_dir, indent=indent)
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
    documentation.

    Deliberately `.absolute()` (normalised, not resolved), never
    `.resolve()`: this framework's own repo self-adopts itself, and every
    `skills/<name>/` entry there is a symlink into
    `plugins/<family>/skills/<name>/` (see `skills/setup/agents.md` → the
    canonical-plus-relay model). `.resolve()` follows that symlink to its
    real location outside `skills/`, which would reject every legitimate
    target in this repo's own tree. `.absolute()` only prepends the cwd to a
    relative path — it never follows symlinks — so containment is judged on
    the path `main()` actually globbed (always under `skills/` by
    construction), not on where a symlinked skill happens to physically
    live.

    `.absolute()` alone is not enough, though: it does not collapse `..` /
    `.` segments, so a path such as `skills/../docs/notes.md` would pass a
    naive `relative_to` check by literal string prefix even though it walks
    straight back out of `skills/`. `os.path.normpath` collapses those
    segments on the already-symlink-preserving absolute path, closing that
    gap without reintroducing the symlink-following `.resolve()` was
    rejected for. A path outside `roots` to begin with (the case this check
    exists to catch) is still rejected the same way."""
    try:
        resolved = Path(os.path.normpath(str(path.absolute())))
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(Path(os.path.normpath(str(root.absolute()))))
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
        # Counts *regions*, not files: a single detail file can (and does —
        # `install.md` carries three) hold more than one declared-block
        # marker, and the maintainer's only confirmation that propagation
        # actually happened is this count. `process_declared` returns
        # `(False, [])` both for "no marker at all" and for "marker(s)
        # present, nothing to do", so that return value alone cannot tell
        # the two apart — count independently via `finditer`.
        region_count = len(list(DECLARED_RE.finditer(path.read_text())))
        did_change, target_errors = process_declared(path, fix=args.fix)
        declared_seen += region_count
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
