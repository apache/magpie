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

"""Estimate the always-on token cost of each marketplace plugin.

**What "always-on" means.** An installed skill advertises its frontmatter
``name`` and ``description`` to the model on *every* turn, whether or not the
skill is invoked. The body of ``SKILL.md`` is read only when the skill runs, so
it costs nothing until then. The advertised surface is therefore what an
adopter is really paying for a family they installed and may never use, and it
is the number the install docs quote.

**Method.** ``len(name) + len(description) + 2`` characters per skill, summed
per ``family:``, divided by 4 to approximate tokens. The 4-chars-per-token
ratio is the standard rough figure for English prose; this is an estimate for
choosing between plugins, not an accounting of a specific tokenizer's output.
It is deliberately not a live tokenizer call: the number must be reproducible
offline, in CI, with no model dependency and no network.

Published figures live in the plugin tables of ``docs/setup/marketplaces.md``
and ``docs/quick-start.md``. ``--check`` compares those tables against the live
frontmatter and fails on drift, which is how ``check-doc-sync.py`` gates them.

Run from the repo root:

    python3 tools/dev/estimate-skill-tokens.py
    python3 tools/dev/estimate-skill-tokens.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKILLS_DIR = Path("skills")

# Tables that publish the estimate, as `| `magpie-security` | 15 | ~2.0k |`
# and a bolded all-in-one row. Same files the count checks in check-doc-sync.py
# already read.
PUBLISHED_IN = (Path("docs/setup/marketplaces.md"), Path("docs/quick-start.md"))

CHARS_PER_TOKEN = 4

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)
# `| `magpie-security` | 15 | ~2.0k |` — plugin, count, then the token cell.
_PUBLISHED_ROW = re.compile(r"^\|\s*`magpie-(?P<family>[a-z-]+)`\s*\|\s*\d+\s*\|\s*~(?P<tokens>[\d.]+)k\s*\|")
# `| **`magpie`** (all) | **74** | **~8.6k** |`
_PUBLISHED_ALL = re.compile(
    r"^\|\s*\*?\*?`magpie`\*?\*?\s*\(all\)\s*\|\s*\*?\*?\d+\*?\*?\s*\|\s*\*?\*?~(?P<tokens>[\d.]+)k"
)


def _scalar(frontmatter: str, key: str) -> str:
    """Read one frontmatter value, plain or block (``key: |``).

    A hand-rolled reader rather than a YAML dependency: these scripts are
    standard-library-only so they run in any checkout without a sync step.
    """
    m = re.search(rf"^{key}:[ \t]*(\|[-+]?|>[-+]?)?[ \t]*(.*)$", frontmatter, re.M)
    if not m:
        return ""
    if not m.group(1):
        return m.group(2).strip()
    lines = frontmatter[m.end() :].split("\n")[1:]
    body: list[str] = []
    for line in lines:
        if line.strip() and not line[:1].isspace():
            break  # dedented back to a sibling key
        body.append(line)
    return "\n".join(body).strip()


def measure() -> dict[str, tuple[int, float]]:
    """Return ``{family: (skill count, estimated always-on tokens)}``."""
    out: dict[str, tuple[int, float]] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        m = _FRONTMATTER.match(skill_md.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = m.group(1)
        family = _scalar(fm, "family")
        if not family:
            continue
        chars = len(_scalar(fm, "name")) + len(_scalar(fm, "description")) + 2
        count, tokens = out.get(family, (0, 0.0))
        out[family] = (count + 1, tokens + chars / CHARS_PER_TOKEN)
    return out


def _round_k(tokens: float) -> float:
    """The published form: one decimal place, in thousands."""
    return round(tokens / 1000, 1)


def check(errors: list[str]) -> None:
    """Compare every published figure against the live frontmatter."""
    live = measure()
    total_k = _round_k(sum(t for _, t in live.values()))
    for path in PUBLISHED_IN:
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = _PUBLISHED_ROW.match(line)
            if m:
                family = m.group("family")
                if family not in live:
                    continue  # the plugin-name check in check-doc-sync.py owns this
                want = _round_k(live[family][1])
                if abs(float(m.group("tokens")) - want) > 0.05:
                    errors.append(
                        f"{path}:{lineno}: 'magpie-{family}' publishes ~{m.group('tokens')}k "
                        f"always-on tokens; measured ~{want}k"
                    )
                continue
            m = _PUBLISHED_ALL.match(line)
            if m and abs(float(m.group("tokens")) - total_k) > 0.05:
                errors.append(
                    f"{path}:{lineno}: the all-in-one row publishes ~{m.group('tokens')}k "
                    f"always-on tokens; measured ~{total_k}k"
                )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="compare the published tables against the live frontmatter and fail on drift",
    )
    args = ap.parse_args()

    if not SKILLS_DIR.is_dir():
        print("estimate-skill-tokens: run from the repository root", file=sys.stderr)
        return 2

    live = measure()
    if args.check:
        errors: list[str] = []
        check(errors)
        if errors:
            print("estimate-skill-tokens: published token figures are out of date.\n", file=sys.stderr)
            for err in errors:
                print(f"  {err}", file=sys.stderr)
            print(
                f"\n{len(errors)} problem(s). Regenerate with "
                "'python3 tools/dev/estimate-skill-tokens.py' and update the tables.",
                file=sys.stderr,
            )
            return 1
        print("estimate-skill-tokens: OK (published figures match the live frontmatter).")
        return 0

    total_skills = sum(c for c, _ in live.values())
    total_tokens = sum(t for _, t in live.values())
    print(f"{'plugin':<32}{'skills':>7}{'always-on':>12}")
    for family, (count, tokens) in sorted(live.items(), key=lambda kv: -kv[1][1]):
        print(f"{'magpie-' + family:<32}{count:>7}{'~' + str(_round_k(tokens)) + 'k':>12}")
    print(f"{'magpie (all)':<32}{total_skills:>7}{'~' + str(_round_k(total_tokens)) + 'k':>12}")
    print(
        f"\nname + description only, at {CHARS_PER_TOKEN} chars/token. "
        "The SKILL.md body costs nothing until the skill is invoked."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
