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
"""Clickable references: find bare `#NNN` / `owner/repo#NNN` and link them.

Every `<tracker>` / `<upstream>` reference a skill emits on a markdown surface
is one click away (AGENTS.md § *Linking tracker issues and PRs*). Code spans,
fenced blocks and HTML comments are left alone: a `#12` there is code.
"""

from __future__ import annotations

import re

# Ported from tools/pr-management (pr_management/triage/render.py `_BARE_REF`):
# a `#NNN` not already inside a link, a path, an anchor, an entity or a code span.
# Keep the two in step.
_BARE_REF = re.compile(r"(?<![\w\[/#&`])#(\d{1,7})\b(?!\]\()")
# `owner/repo#NNN` not already the text of a markdown link.
_REPO_REF = re.compile(r"(?<![\w\[/.-])([A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+)#(\d{1,7})\b(?!\]\()")
_CODE_SPAN = re.compile(r"(`[^`]*`)")


def _segments(text: str) -> list[tuple[bool, str]]:
    """`(linkable, piece)` pairs covering `text`, line structure preserved."""
    out: list[tuple[bool, str]] = []
    inside_fence = False
    for index, line in enumerate(text.split("\n")):
        if index:
            out.append((False, "\n"))
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            inside_fence = not inside_fence
            out.append((False, line))
            continue
        if inside_fence or stripped.startswith("<!--"):
            out.append((False, line))
            continue
        for piece in _CODE_SPAN.split(line):
            out.append((not (piece.startswith("`") and piece.endswith("`") and len(piece) > 1), piece))
    return out


def bare_refs(text: str) -> list[str]:
    """Every unlinked reference in `text`, as written (`#12`, `owner/repo#12`)."""
    found: list[str] = []
    for linkable, piece in _segments(text):
        if not linkable:
            continue
        found.extend(f"{m.group(1)}#{m.group(2)}" for m in _REPO_REF.finditer(piece))
        found.extend(f"#{m.group(1)}" for m in _BARE_REF.finditer(_REPO_REF.sub("", piece)))
    return found


def linkify(text: str, repo: str, kind: str = "issues") -> str:
    """`text` with every bare `#NNN` linked into `repo` and every `owner/repo#NNN` into its own repo.

    `kind` is the URL segment for bare numbers (`issues` for `<tracker>`,
    `pull` for `<upstream>` PRs); GitHub redirects either way, so a
    reference of the other kind still resolves.
    """
    parts: list[str] = []
    for linkable, piece in _segments(text):
        if linkable:
            piece = _REPO_REF.sub(
                lambda m: f"[{m.group(1)}#{m.group(2)}](https://github.com/{m.group(1)}/issues/{m.group(2)})",
                piece,
            )
            piece = _BARE_REF.sub(
                lambda m: f"[#{m.group(1)}](https://github.com/{repo}/{kind}/{m.group(1)})", piece
            )
        parts.append(piece)
    return "".join(parts)
