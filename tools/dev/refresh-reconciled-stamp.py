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
"""
Restamp the framework checkout's ``reconciled:`` block for a dev bump.

The framework repository self-adopts Magpie (``method: local``), so its
committed ``.apache-magpie.lock`` carries a ``reconciled:`` stamp like any
adopter's. Left alone across a bump, the stamp names an older version and older
surface hashes, and every skill whose surface moved raises ``fingerprint-moved``
on each run. A dev bump therefore restamps it in the same commit.

What gets stamped: **every skill in ``plugins/*/skills/``**, at the
``surface_hash`` its ``SKILL.md`` declares, **except the skills listed in
``tools/dev/reconciled-stamp-excluded.txt``** — the ones this checkout declined
at reconcile time because it does not carry their configuration (the
security-tracker skills). The list is explicit so that a new or renamed skill
is stamped rather than silently treated as declined; a listed name that no
longer exists fails the run, so a rename has to update the list. Entries for
skills that no longer exist are dropped. ``version`` becomes
``project.version`` from ``pyproject.toml``, ``at`` today's UTC date.

Everything outside the ``reconciled:`` block is left byte-identical.

Usage:

    refresh-reconciled-stamp.py            # rewrite .apache-magpie.lock
    refresh-reconciled-stamp.py --check    # exit 1 if a rewrite would change it
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: ``version = "..."`` in the ``[project]`` table, as ``bump-dev-version.py`` reads it.
VERSION_RE = re.compile(r'^version = "(?P<version>.+?)"', re.MULTILINE)
#: One stamped skill line inside ``reconciled.skills``.
STAMP_LINE_RE = re.compile(r"^    (?P<name>[\w-]+):\s+(?P<hash>sha256:\w+)\s*$", re.MULTILINE)
#: Column the hash starts in; longer names get a single space instead.
NAME_WIDTH = 28
#: The committed list of declined skills, relative to the checkout root.
EXCLUDED_FILE = Path("tools/dev/reconciled-stamp-excluded.txt")


class StampError(RuntimeError):
    """Raised when the inputs cannot be read."""


@dataclass
class Skill:
    name: str
    surface_hash: str


@dataclass
class Result:
    text: str
    stamped: dict[str, str]
    excluded: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)


def _frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else ""


def read_skills(root: Path) -> dict[str, Skill]:
    """Every framework skill's name and surface hash."""
    skills: dict[str, Skill] = {}
    for path in sorted(root.glob("plugins/*/skills/*/SKILL.md")):
        fm = _frontmatter(path.read_text(encoding="utf-8"))
        name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
        surface = re.search(r"^surface_hash:\s*(\S+)", fm, re.MULTILINE)
        if not name or not surface:
            raise StampError(f"{path}: no `name:` or `surface_hash:` in the frontmatter")
        skills[name.group(1)] = Skill(name.group(1), surface.group(1))
    if not skills:
        raise StampError(f"no plugins/*/skills/*/SKILL.md under {root}")
    return skills


def read_excluded(text: str) -> list[str]:
    """Skill names from the exclusion list: one per line, ``#`` starts a comment."""
    names = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    return sorted({n for n in names if n})


def read_version(pyproject: str) -> str:
    match = VERSION_RE.search(pyproject)
    if not match:
        raise StampError('no `version = "..."` line found in pyproject.toml')
    return match.group("version")


def refresh(lock: str, skills: dict[str, Skill], excluded: list[str], version: str, date: str) -> Result:
    """Return *lock* with its ``reconciled:`` block rewritten, and what changed."""
    unknown = sorted(set(excluded) - set(skills))
    if unknown:
        raise StampError(
            f"{EXCLUDED_FILE} names skills that do not exist: {', '.join(unknown)}"
            " (renamed or removed? update the list)"
        )
    start = lock.find("reconciled:\n")
    if start == -1:
        raise StampError("no `reconciled:` block in the lock; run `/magpie-setup reconcile` once first")
    body = lock[start:]
    # The block runs to the first line that is neither blank nor indented.
    end_match = re.search(r"^(?=\S)", body[len("reconciled:\n") :], re.MULTILINE)
    end = start + len("reconciled:\n") + end_match.start() if end_match else len(lock)
    current = {m["name"]: m["hash"] for m in STAMP_LINE_RE.finditer(lock[start:end])}

    excluded = sorted(excluded)
    stamped = {n: s.surface_hash for n, s in sorted(skills.items()) if n not in excluded}
    block = ["reconciled:", f"  version: {version}", f"  at:      {date}", "  skills:"]
    block += [f"    {(n + ':').ljust(NAME_WIDTH - 1)} {h}" for n, h in stamped.items()]
    text = lock[:start] + "\n".join(block) + "\n" + lock[end:]
    return Result(
        text=text,
        stamped=stamped,
        excluded=excluded,
        dropped=sorted(set(current) - set(skills)),
        added=sorted(set(stamped) - set(current)),
        moved=sorted(n for n in stamped if n in current and current[n] != stamped[n]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="framework checkout root")
    parser.add_argument("--date", help="stamp date (YYYY-MM-DD); defaults to today in UTC")
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if the stamp is stale")
    args = parser.parse_args(argv)

    lock_path = args.root / ".apache-magpie.lock"
    lock = lock_path.read_text(encoding="utf-8")
    version = read_version((args.root / "pyproject.toml").read_text(encoding="utf-8"))
    date = args.date or dt.datetime.now(dt.UTC).date().isoformat()
    excluded_path = args.root / EXCLUDED_FILE
    if not excluded_path.is_file():
        raise StampError(f"no exclusion list at {excluded_path}")
    excluded = read_excluded(excluded_path.read_text(encoding="utf-8"))
    result = refresh(lock, read_skills(args.root), excluded, version, date)

    print(f"refresh-reconciled-stamp: {len(result.stamped)} stamped at {version}")
    for label, names in (
        ("excluded", result.excluded),
        ("added", result.added),
        ("dropped", result.dropped),
        ("moved", result.moved),
    ):
        if names:
            print(f"  {label} ({len(names)}): {', '.join(names)}")

    if args.check:
        # The date always moves, so compare everything but `at:`.
        def strip(t: str) -> str:
            return re.sub(r"^  at: .*$", "", t, flags=re.MULTILINE)

        return 0 if strip(result.text) == strip(lock) else 1
    if result.text != lock:
        lock_path.write_text(result.text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except StampError as exc:
        print(f"refresh-reconciled-stamp: {exc}", file=sys.stderr)
        sys.exit(1)
