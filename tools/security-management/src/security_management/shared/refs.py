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
is one click away (AGENTS.md § *Linking tracker issues and PRs*). Code spans
(any matching backtick run), fenced blocks, HTML comments, existing markdown
links, autolinks and bare URLs are left alone: a `#12` there is code or is
already a link.

`tracker_link` renders a tracker reference on any backend: GitHub builds its
issue URL, Jira and local-files trackers use the `url` the backend returned
(or the bare ID when there is none).
"""

from __future__ import annotations

import re

from github_body_field.parser import fence_roles

# Ported from tools/pr-management (pr_management/triage/render.py `_BARE_REF`):
# a `#NNN` not already inside a link, a path, an anchor, an entity or a code span.
# Keep the two in step.
_BARE_REF = re.compile(r"(?<![\w\[/#&`])#(\d{1,7})\b(?!\]\()")
# `owner/repo#NNN` not already the text of a markdown link.
_REPO_REF = re.compile(r"(?<![\w\[/.-])([A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9._-]+)#(\d{1,7})\b(?!\]\()")
# Pieces no reference inside may be linked: a code span (a backtick run closed by
# a run of the same length), a markdown link or image `[text](target)`, an
# autolink `<scheme:…>`, a bare URL.
_PROTECTED = re.compile(
    r"((?<!`)(`+)(?!`).*?(?<!`)\2(?!`)"
    r"|!?\[[^\]\n]*\]\([^)\n]*\)"
    r"|<[A-Za-z][A-Za-z0-9+.-]*:[^>\s]*>"
    r"|https?://[^\s)\]>]+)"
)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_URL_SAFE = re.compile(r"(?:https?://|/|\.\.?/|[A-Za-z0-9_-]+/)[^\s()<>\[\]]*")


def _segments(text: str) -> list[tuple[bool, str]]:
    """`(linkable, piece)` pairs covering `text`, line structure preserved."""
    out: list[tuple[bool, str]] = []
    lines = text.split("\n")
    # Fences pair the CommonMark way (github-body-field), so a ```` block holding ``` stays code.
    roles = fence_roles(lines)
    for index, (line, role) in enumerate(zip(lines, roles, strict=True)):
        if index:
            out.append((False, "\n"))
        stripped = line.lstrip()
        if role != "text" or stripped.startswith("<!--"):
            out.append((False, line))
            continue
        last = 0
        for match in _PROTECTED.finditer(line):
            out.append((True, line[last : match.start()]))
            out.append((False, match.group(0)))
            last = match.end()
        out.append((True, line[last:]))
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


def tracker_link(tracker: str, ref: object, url: object = None, platform: str = "github") -> str:
    """A tracker reference as a link: `owner/repo#N` on GitHub, the backend's ID elsewhere.

    `ref` is an issue number, an `owner/repo#N` or a backend ID (`FOOSEC-12`,
    `SEC-0012`); `url` is what the backend returned, used as given. Without a
    `url`, only a GitHub reference can be linked; any other ID is returned bare.
    """
    text = re.sub(r"\s+", " ", "" if ref is None else str(ref)).strip()
    link = re.sub(r"\s+", "", "" if url is None else str(url))
    full = _REPO_REF.fullmatch(text)
    if platform == "github" and (full or text.lstrip("#").isdigit()):
        repo, number = (full.group(1), full.group(2)) if full else (tracker, text.lstrip("#"))
        return f"[{repo}#{number}]({link or f'https://github.com/{repo}/issues/{number}'})"
    if not _ID.fullmatch(text):
        raise ValueError(f"tracker reference {text!r} is not an issue number or a backend ID")
    if not link:
        return text
    if not _URL_SAFE.fullmatch(link):
        raise ValueError(f"tracker url {link!r} for {text} is not a plain URL or path")
    return f"[{text}]({link})"
