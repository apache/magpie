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
"""Triage markers: the comment marker, the `pr-triage-fold` body block, confirmation requests.

A PR is *triaged* when a triager (association OWNER / MEMBER / COLLABORATOR)
left a comment carrying the quality-criteria link text after the head commit,
or when the PR body carries a `pr-triage-fold` block whose `head=` matches
the current head. The anchor time is the comment's `createdAt` or the fold's
`triaged=`; the sub-state is `responded` when the author commented or pushed
after it, `waiting` otherwise. `pr-management-stats` reads the same rules.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .config import CONFIRMATION_MARKER, FOLD_CLOSE, FOLD_OPEN
from .model import COLLABORATOR_ASSOCIATIONS, PR

FOLD_RE = re.compile(
    r"<!--\s*"
    + re.escape(FOLD_OPEN)
    + r":(?P<meta>[^>]*?)-->(?P<content>.*?)<!--\s*"
    + re.escape(FOLD_CLOSE)
    + r"\s*-->",
    flags=re.DOTALL,
)
CONFIRMATION_ACTION = "request-author-confirmation"

#: The legacy HTML-comment marker some older triage comments carry.
LEGACY_MARKER = "<!-- pr-triage -->"


@dataclass(frozen=True)
class Fold:
    triaged: dt.datetime | None
    head: str | None
    action: str | None
    by: str | None
    content: str


@dataclass(frozen=True)
class Marker:
    channel: str
    at: dt.datetime
    by: str | None
    action: str | None


_FOLD_OPENER = re.compile(r"<!--\s*" + re.escape(FOLD_OPEN) + r":(?P<meta>[^>]*?)-->")
_FOLD_CLOSER = re.compile(r"<!--\s*" + re.escape(FOLD_CLOSE) + r"\s*-->")


def _fold_time(value: str | None) -> dt.datetime | None:
    """A fold's `triaged=`: ISO-8601 with an explicit zone, else none.

    The fold lives in the PR body, which the author controls, so the value is
    untrusted: unparsable or zone-less means "no timestamp", never a guess.
    """
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def parse_fold(body: str) -> Fold | None:
    """The PR body's `pr-triage-fold` block, if any.

    Every opening marker is read; the last one carrying a valid `triaged=`
    wins, so a malformed marker planted above the real block cannot hide it.
    The block's content runs to the next closing marker (or the end of the body).
    """
    text = body or ""
    folds: list[Fold] = []
    for opener in _FOLD_OPENER.finditer(text):
        meta = dict(part.split("=", 1) for part in opener.group("meta").split() if "=" in part)
        closer = _FOLD_CLOSER.search(text, opener.end())
        folds.append(
            Fold(
                triaged=_fold_time(meta.get("triaged")),
                head=meta.get("head"),
                action=meta.get("action"),
                by=meta.get("by"),
                content=text[opener.end() : closer.start() if closer else len(text)],
            )
        )
    if not folds:
        return None
    valid = [f for f in folds if f.triaged is not None]
    return valid[-1] if valid else folds[-1]


def fold_is_current(fold: Fold, pr: PR) -> bool:
    return bool(fold.head) and pr.head_sha.startswith(fold.head or "\0")


def triage_marker(pr: PR, marker_text: str) -> Marker | None:
    """The newest triage marker posted after the head commit, in either channel."""
    found: list[Marker] = []
    fold = parse_fold(pr.body)
    # A folded confirmation request belongs to rows 14a/14b: counting it as a
    # triage marker would hold the author's reply behind rows 3-4 for a week.
    if (
        fold is not None
        and fold.triaged is not None
        and fold_is_current(fold, pr)
        and fold.action != CONFIRMATION_ACTION
    ):
        found.append(Marker("pr-body", fold.triaged, fold.by, fold.action))
    for comment in pr.comments:
        if comment.association not in COLLABORATOR_ASSOCIATIONS or comment.author == pr.author:
            continue
        if marker_text not in comment.body or comment.created is None:
            continue
        if pr.head_committed is not None and comment.created <= pr.head_committed:
            continue
        found.append(Marker("comment", comment.created, comment.author, None))
    return max(found, key=lambda m: m.at) if found else None


def any_triage_marker(pr: PR, marker_text: str) -> Marker | None:
    """The newest triage marker regardless of the head commit (row 0, the sweeps)."""
    found: list[Marker] = []
    fold = parse_fold(pr.body)
    if fold is not None and fold.triaged is not None:
        found.append(Marker("pr-body", fold.triaged, fold.by, fold.action))
    for comment in pr.comments:
        if (
            comment.association in COLLABORATOR_ASSOCIATIONS
            and comment.author != pr.author
            and marker_text in comment.body
            and comment.created is not None
        ):
            found.append(Marker("comment", comment.created, comment.author, None))
    return max(found, key=lambda m: m.at) if found else None


def author_activity_after(pr: PR, at: dt.datetime) -> bool:
    """The author commented (issue or thread) or pushed after `at`."""
    if pr.head_committed is not None and pr.head_committed > at:
        return True
    return any(c.author == pr.author and c.created is not None and c.created > at for c in pr.all_comments())


def sub_state(pr: PR, marker: Marker) -> str:
    return "responded" if author_activity_after(pr, marker.at) else "waiting"


def confirmation_request(pr: PR, viewer: str) -> dt.datetime | None:
    """When the viewer last asked the author to confirm readiness, after the head commit.

    Under the default `pr-body` channel the request is the fold block (action
    `request-author-confirmation`, carrying the confirmation marker); under
    `comment` it is the viewer's comment carrying the marker.
    """
    candidates: list[dt.datetime] = []
    fold = parse_fold(pr.body)
    if (
        fold is not None
        and fold.triaged is not None
        and fold_is_current(fold, pr)
        and (fold.action == CONFIRMATION_ACTION or CONFIRMATION_MARKER in fold.content)
    ):
        candidates.append(fold.triaged)
    for comment in pr.comments:
        if comment.author != viewer or comment.created is None or CONFIRMATION_MARKER not in comment.body:
            continue
        if pr.head_committed is None or comment.created > pr.head_committed:
            candidates.append(comment.created)
    return max(candidates) if candidates else None


def author_replied_after(pr: PR, at: dt.datetime) -> bool:
    return any(c.author == pr.author and c.created is not None and c.created > at for c in pr.all_comments())
