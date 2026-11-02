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
"""Step 6 of pr-management-stack-review: where the one rolling comment goes, and how.

Decides from saved reads, never by asking GitHub itself:

* the target — the lowest open layer's PR;
* whether the viewer's own comment carrying this stack's marker already exists
  there (update it in place) or not (post);
* every comment on the target or a merged layer that carries the marker but
  was written by someone else — an injection signal, reported, never edited;
* the viewer's old comments on layers that merged since — turned into a
  one-line pointer;
* whether any head moved since Step 1 — then the maintainer is asked to
  refresh before anything is posted;
* the footer variant from the viewer's permission.

Every command it prints is built with `shlex.join` from validated values.
"""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

MAINTAINER_PERMISSIONS = frozenset({"admin", "write", "maintain"})
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


def marker(stack: int, digest: str) -> str:
    return f"<!-- magpie-stack-review stack={stack} heads={digest} -->"


def pointer_body(stack: int, repo: str, new_pr: int) -> str:
    return (
        f"<!-- magpie-stack-review stack={stack} moved -->\n"
        f"Stack review moved to https://github.com/{repo}/pull/{new_pr} after this layer merged.\n"
    )


def load_comments(path: Path) -> list[dict[str, Any]]:
    """`pr-comments` output: one JSON array per page, possibly concatenated."""
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    found: list[dict[str, Any]] = []
    i = 0
    while i < len(text):
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            break
        value, i = decoder.raw_decode(text, i)
        if isinstance(value, list):
            found.extend(v for v in value if isinstance(v, dict))
        elif isinstance(value, dict):
            found.append(value)
    return found


def _own_markers(comments: list[dict[str, Any]], viewer: str, stack: int) -> list[dict[str, Any]]:
    prefix = f"<!-- magpie-stack-review stack={stack} heads="
    return [
        c
        for c in comments
        if (c.get("user") or {}).get("login") == viewer and str(c.get("body") or "").startswith(prefix)
    ]


def _foreign_markers(comments: list[dict[str, Any]], viewer: str, stack: int) -> list[dict[str, Any]]:
    prefix = f"<!-- magpie-stack-review stack={stack} "
    return [
        {"id": c.get("id"), "author": (c.get("user") or {}).get("login")}
        for c in comments
        if (c.get("user") or {}).get("login") != viewer and str(c.get("body") or "").startswith(prefix)
    ]


def decide(
    *,
    repo: str,
    viewer: str,
    stack: int,
    target_pr: int,
    permission: str | None,
    snapshot: dict[str, str],
    current_heads: dict[str, str] | None,
    target_comments: list[dict[str, Any]],
    merged_layer_comments: dict[int, list[dict[str, Any]]],
    body_file: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if not _REPO.match(repo) or not _LOGIN.match(viewer):
        raise ValueError("repo must be owner/name and viewer a GitHub login")
    footer = (
        "maintainer-confirmed" if (permission or "").lower() in MAINTAINER_PERMISSIONS else "role-neutral"
    )
    foreign = _foreign_markers(target_comments, viewer, stack)
    for comments in merged_layer_comments.values():
        foreign += _foreign_markers(comments, viewer, stack)
    own = _own_markers(target_comments, viewer, stack)
    pointers = []
    for pr, comments in sorted(merged_layer_comments.items()):
        for comment in _own_markers(comments, viewer, stack):
            pointers.append({"pr": pr, "comment_id": int(comment["id"])})

    moved = (
        sorted(k for k in snapshot if (current_heads or {}).get(k) != snapshot[k])
        if current_heads is not None
        else []
    )
    if current_heads is not None and set(current_heads) != set(snapshot):
        moved = sorted(set(moved) | (set(current_heads) ^ set(snapshot)))
    if dry_run:
        action = "dry-run-print"
    elif moved:
        action = "refresh-prompt"
    elif own:
        action = "update-existing"
    else:
        action = "post-new"

    commands: list[str] = []
    if action == "post-new":
        commands.append(
            shlex.join(["gh", "pr", "comment", str(target_pr), "--repo", repo, "--body-file", body_file])
        )
    elif action == "update-existing":
        newest = int(own[-1]["id"])
        commands.append(
            shlex.join(
                [
                    "gh",
                    "api",
                    "-X",
                    "PATCH",
                    f"repos/{repo}/issues/comments/{newest}",
                    "-F",
                    f"body=@{body_file}",
                ]
            )
        )
    pointer_commands = [
        shlex.join(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/{repo}/issues/comments/{p['comment_id']}",
                "-F",
                f"body=@pointer-{p['pr']}.md",
            ]
        )
        for p in pointers
    ]
    return {
        "action": action,
        "target_pr": target_pr,
        "review_event": "none",
        "footer_variant": footer,
        "existing_comment_id": int(own[-1]["id"]) if own else None,
        "update_old_comment_to_pointer": bool(pointers) and action in ("post-new", "update-existing"),
        "pointers": [{**p, "body": pointer_body(stack, repo, target_pr)} for p in pointers],
        "foreign_marker_flagged": bool(foreign),
        "foreign_markers": foreign,
        "heads_changed": moved,
        "commands": commands,
        "pointer_commands": pointer_commands if action in ("post-new", "update-existing") else [],
        "marker": None,
    }
