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

"""The rules prose, shipped with the tool and emitted only when it applies.

Every finding names a section; this module hands back that section's text
so the verdict carries both what is true and what to do about it. The
agent makes one call and reads nothing else.

The prose used to be a `preflight-detail.md` generated beside all 65
skills — 2,516 tokens copied 65 times so that a run needing one 150-token
section could find it. Emitting per finding costs the sections actually
triggered and nothing in the ordinary case, and leaves one copy in the
repository rather than sixty-five.

These are plain Markdown files under `sections/`, reviewed as Markdown.
Living inside a Python package is a packaging detail, not a statement
that the rules are code: they are the half of the pre-flight that is
still judgement, and the tool's own logic is deliberately the other half.
"""

from __future__ import annotations

import re
from pathlib import Path

SECTIONS_DIR = Path(__file__).parent / "sections"


#: The repository stamps an SPDX header into every Markdown file for the
#: licence audit. It is correct in the file and pure noise in the verdict,
#: where the agent pays for it on every emitted section, so it is stripped
#: on the way out rather than omitted from the file.
_LICENCE_RE = re.compile(r"\A<!--\s*SPDX-License-Identifier.*?-->\s*", re.S)
#: A table of contents for a single-section file says nothing, and the
#: doctoc hook is excluded from this directory so one should never appear.
#: Stripped anyway: a section is emitted into someone's context, and a
#: generator that starts including boilerplate there should fail visibly
#: in review rather than quietly cost every run.
_DOCTOC_RE = re.compile(r"<!-- START doctoc.*?<!-- END doctoc[^>]*-->\s*", re.S)


class UnknownSection(KeyError):
    """A finding named a section that does not ship. Always a bug here."""


def available() -> list[str]:
    return sorted(p.stem for p in SECTIONS_DIR.glob("*.md"))


def load(section: str) -> str:
    """The Markdown for `section`, or raise `UnknownSection`.

    Deliberately strict. A finding whose section is missing would
    otherwise reach the agent as a rule-less instruction to act, which is
    the one outcome this tool exists to prevent.
    """
    path = SECTIONS_DIR / f"{section}.md"
    if not path.is_file():
        raise UnknownSection(f"no rules shipped for section {section!r}; have {available()}")
    raw = _LICENCE_RE.sub("", path.read_text(encoding="utf-8"))
    return _DOCTOC_RE.sub("", raw).strip()


def for_findings(sections: list[str]) -> dict[str, str]:
    """Each distinct section's text, in the order first requested."""
    seen: dict[str, str] = {}
    for section in sections:
        if section not in seen:
            seen[section] = load(section)
    return seen
