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
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Print a human-readable index of the skills installed for this repository.

Discovery is **installation-aware**: what a person can invoke depends on how
Magpie was installed, so the script looks in every place an install can put a
skill, rather than assuming its own location is the whole story.

Three sources, unioned:

1. **Agent-target directories in the repository** — ``.agents/skills/`` (the
   canonical home) and the per-agent relays beside it. This is what a pinned
   snapshot install writes, and what the framework checkout commits for
   self-adoption.
2. **The framework's own ``skills/``** — present when the current repository is
   the framework checkout itself.
3. **Marketplace plugin installs** — when this script is running from an
   installed plugin, its sibling plugins under the same marketplace cache. A
   marketplace install puts nothing in the repository, so a repository-only
   walk would report an empty or partial index.

Two things this deliberately does *not* do, both of which were bugs:

- It does not derive the skills directory from the script's own location.
  Under a per-family plugin install that resolves to the one family that
  happens to ship this script, so ``list-skills`` reported 5 skills out of 74.
- It does not infer the family from the skill's name prefix. Family membership
  is read from the ``family:`` frontmatter key (AGENTS.md Golden rule 8) —
  families such as ``repo-health`` and ``contributor-growth`` span several name
  prefixes, and the prefix heuristic invented families like ``write/`` and
  ``optimize/`` for skills whose declared family is ``utilities``.

Frontmatter is parsed with the standard library only. ``skills/pyproject.toml``
declares this tree stdlib-only ("the helper scripts deliberately carry no
runtime dependencies so an adopter can run them without installing anything"),
and this script importing PyYAML was the sole violation — it crashed with
``ModuleNotFoundError: No module named 'yaml'`` on any interpreter that had not
had PyYAML installed into it, which includes the plugin-install case. The
inline script metadata above states the same contract in machine-readable form,
so ``uv run --script`` and a bare ``python3`` behave identically.

Usage::

    python3 <path-to>/list_skills.py
    python3 <path-to>/list_skills.py --verbose
    python3 <path-to>/list_skills.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Directories an install may wire skills into, relative to the repository root.
# The single source of truth for this registry is the table under
# "## The registry" in skills/setup/agents.md; the first entry is the canonical
# home every other target relays into. Mirrored here as a plain list because
# this script needs only the directory names, not the registry's semantics —
# keep it a faithful mirror when a vendor row is added there.
AGENT_SKILL_DIRS: tuple[str, ...] = (
    ".agents/skills",
    ".claude/skills",
    ".github/skills",
    ".windsurf/skills",
    ".goose/skills",
    ".kiro/skills",
)

# The framework's own skill tree, present when the repository is the framework
# checkout (self-adoption, `method:local`).
FRAMEWORK_SKILLS_DIR = "skills"

SKILL_MD = "SKILL.md"

# Frontmatter keys whose value may be a YAML block scalar (`key: |`).
_BLOCK_MARKERS = {"|", ">", "|-", ">-", "|+", ">+"}


def repo_root(explicit: str | None) -> Path:
    """The repository the listing is about: ``--root``, else the git toplevel,
    else the working directory."""
    if explicit:
        return Path(explicit).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return Path.cwd().resolve()


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the top-level scalar keys of a SKILL.md frontmatter block.

    Handles the two shapes the framework's frontmatter actually uses: a plain
    ``key: value`` and a block scalar ``key: |`` whose continuation lines are
    indented. Nested mappings and sequences are skipped — no consumer here
    needs them. Stdlib only, by design; see the module docstring.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    lines = text[3:end].splitlines()

    data: dict[str, str] = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1].isspace():  # a continuation or nested line, not a top-level key
            continue
        key, sep, value = raw.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if value in _BLOCK_MARKERS:
            folded: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not nxt[:1].isspace():
                    break
                folded.append(nxt.strip())
                i += 1
            data[key] = " ".join(part for part in folded if part)
        else:
            data[key] = value.strip("\"'")
    return data


def first_sentence(text: str) -> str:
    """Return the first sentence of a description, on one line."""
    collapsed = " ".join(text.split())
    match = re.match(r"(.+?[.!?])(?:\s|$)", collapsed)
    return match.group(1) if match else collapsed


def marketplace_context(script: Path) -> tuple[Path | None, str | None]:
    """Locate the marketplace cache this script is installed under.

    An installed plugin lives at
    ``…/plugins/cache/<marketplace>/<plugin>/<version>/skills/<skill>/scripts/``.
    Returns ``(marketplace_dir, our_version)``, or ``(None, None)`` when the
    script is not running from a plugin install.
    """
    parents = list(script.resolve().parents)
    for index, ancestor in enumerate(parents):
        parent = ancestor.parent
        if parent.name == "cache" and parent.parent.name == "plugins" and index >= 2:
            return ancestor, parents[index - 2].name
    return None, None


def _rows_from_dir(skills_dir: Path, source: str, *, plugin: str | None = None) -> list[dict[str, str]]:
    """Collect one row per ``<skills_dir>/*/SKILL.md``."""
    rows: list[dict[str, str]] = []
    if not skills_dir.is_dir():
        return rows
    for skill_md in sorted(skills_dir.glob(f"*/{SKILL_MD}")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        meta = parse_frontmatter(text)
        dir_name = skill_md.parent.name
        # A marketplace install namespaces the skill under its plugin
        # (`/magpie-utilities:list-skills`); every other install exposes the
        # flat frontmatter name (`/magpie-list-skills`). Print what the reader
        # can actually type.
        invocation = f"/{plugin}:{dir_name}" if plugin else f"/{meta.get('name') or dir_name}"
        rows.append(
            {
                "invocation": invocation,
                "family": meta.get("family") or "other",
                "description": first_sentence(meta.get("description", "")),
                "source": source,
            }
        )
    return rows


def collect_rows(root: Path, script: Path) -> list[dict[str, str]]:
    """Union the three discovery sources, de-duplicated by invocation.

    Relays point at the canonical ``.agents/skills`` entry, so the same skill is
    reached through several directories; they collapse to one row because they
    yield the same invocation. A skill installed *both* from the repository and
    from a marketplace stays as two rows on purpose — they are two different
    things to type.
    """
    rows: list[dict[str, str]] = []

    for rel in AGENT_SKILL_DIRS:
        rows.extend(_rows_from_dir(root / rel, f"repository ({rel})"))

    framework = root / FRAMEWORK_SKILLS_DIR
    if (framework / "list-skills" / SKILL_MD).is_file() or (framework / "setup" / SKILL_MD).is_file():
        rows.extend(_rows_from_dir(framework, f"framework checkout ({FRAMEWORK_SKILLS_DIR}/)"))

    marketplace, our_version = marketplace_context(script)
    if marketplace is not None:
        for plugin_dir in sorted(p for p in marketplace.iterdir() if p.is_dir()):
            versions = sorted(v for v in plugin_dir.iterdir() if v.is_dir())
            if not versions:
                continue
            # Prefer the version this script is running from; otherwise the
            # highest-sorting one, since a cache keeps older versions around.
            chosen = next((v for v in versions if v.name == our_version), versions[-1])
            rows.extend(
                _rows_from_dir(
                    chosen / "skills",
                    f"marketplace ({marketplace.name})",
                    plugin=plugin_dir.name,
                )
            )

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        if row["invocation"] in seen:
            continue
        seen.add(row["invocation"])
        unique.append(row)
    return unique


def render(rows: list[dict[str, str]], *, verbose: bool) -> str:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["family"]].append(row)

    width = max((len(r["invocation"]) for r in rows), default=0)
    lines: list[str] = [f"Skills installed for this repository ({len(rows)} total)", "=" * 50, ""]
    for family in sorted(grouped):
        entries = sorted(grouped[family], key=lambda r: r["invocation"])
        lines.append(f"{family}/  ({len(entries)})")
        for row in entries:
            if verbose:
                lines.append(f"  {row['invocation']}")
                lines.append(f"      {row['description']}")
            else:
                lines.append(f"  {row['invocation'].ljust(width)}  {row['description']}")
        lines.append("")

    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["source"]] += 1
    lines.append("Installed from:")
    for source in sorted(counts):
        lines.append(f"  {counts[source]:>3}  {source}")
    lines.append("")
    lines.append("Invoke a skill by typing the name shown above, or describe what you want to do.")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a human-readable index of the skills installed for this repository.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Place description on its own indented line per skill.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository to inspect (default: the enclosing git checkout, else the cwd).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = repo_root(args.root)
    rows = collect_rows(root, Path(__file__))
    if not rows:
        print(
            f"no skills found for {root}\n"
            "Looked in: "
            + ", ".join(AGENT_SKILL_DIRS)
            + f", {FRAMEWORK_SKILLS_DIR}/, and any marketplace plugin cache this script runs from.\n"
            "If Magpie is installed, run it from inside the repository that adopted it.",
            file=sys.stderr,
        )
        return 1
    print(render(rows, verbose=args.verbose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
