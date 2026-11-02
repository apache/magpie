# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""The backend seam: change-request activity from the code host, issue activity from the tracker.

The code host answers PRs authored, reviews given and PR threads (`contract:change-request`);
the tracker answers issues filed, issues triaged and issue threads (`contract:tracker`).
They may be different systems — a project can review on GitHub and file issues in Jira.

With no separate tracker, GitHub answers both sides in one pass, exactly as this tool always
has: same searches, same items, same output.  Comment bodies never leave a backend.
"""

from __future__ import annotations

import time  # re-exported: callers and tests patch time.sleep through this module
from collections.abc import Iterable, Sequence
from typing import Protocol

from contributor_metrics.backends.common import CODE_HOST, TRACKER, BackendError
from contributor_metrics.backends.github import (
    LOGIN_RE,
    REPO_RE,
    SUBSTANTIVE_BODY_CHARS,
    SUBSTANTIVE_LINE_COMMENTS,
    GhError,
    InvalidLogin,
    InvalidRepo,
)
from contributor_metrics.backends.github import fetch_items as github_fetch_items
from contributor_metrics.model import Item

__all__ = [
    "SUBSTANTIVE_BODY_CHARS",
    "SUBSTANTIVE_LINE_COMMENTS",
    "BackendError",
    "GhError",
    "InvalidLogin",
    "InvalidRepo",
    "TrackerBackend",
    "fetch_items",
    "time",
]


class TrackerBackend(Protocol):
    """A tracker that is not the code host: answers issues filed, triaged and commented."""

    def fetch(
        self,
        login: str,
        *,
        since: str,
        end: str,
        phrases: Iterable[str],
        maintainers: Iterable[str],
    ) -> tuple[list[Item], list[str], list[str]]: ...


def fetch_items(
    repo: str | Sequence[str],
    login: str,
    *,
    since: str,
    end: str,
    phrases: Iterable[str],
    maintainers: Iterable[str],
    substantive_body_chars: int = SUBSTANTIVE_BODY_CHARS,
    substantive_line_comments: int = SUBSTANTIVE_LINE_COMMENTS,
    tracker: TrackerBackend | None = None,
    tracker_login: str | None = None,
    tracker_maintainers: Iterable[str] | None = None,
) -> tuple[list[Item], list[str], list[str]]:
    """Fetch every activity stream inside [since, end].

    `repo` and `login` address the code host (GitHub).  `tracker`, when given, answers the
    tracker side instead, for `tracker_login` (default: `login`) with `tracker_maintainers`
    (default: `maintainers`) as its roster.

    `repo` may be a list of repositories of the same project: each is searched on the code host
    (and, without a separate tracker, for issues too), and the items are merged. With more than
    one repository every code-host item id is prefixed `<owner/name>:` so numbers cannot collide,
    a stream capped in any repository is reported as capped, and each note names its repository.

    Returns the items, the names of streams that hit their cap, and notes for the brief.
    """
    phrases, maintainers = tuple(phrases), tuple(maintainers)
    repos = [repo] if isinstance(repo, str) else list(dict.fromkeys(repo))
    if not repos:
        raise InvalidRepo("")
    if len(repos) > 1:
        return _fetch_many(
            repos,
            login,
            since=since,
            end=end,
            phrases=phrases,
            maintainers=maintainers,
            substantive_body_chars=substantive_body_chars,
            substantive_line_comments=substantive_line_comments,
            tracker=tracker,
            tracker_login=tracker_login,
            tracker_maintainers=tracker_maintainers,
        )
    repo = repos[0]
    if tracker is None:
        return github_fetch_items(
            repo,
            login,
            since=since,
            end=end,
            phrases=phrases,
            maintainers=maintainers,
            substantive_body_chars=substantive_body_chars,
            substantive_line_comments=substantive_line_comments,
        )
    if not REPO_RE.match(repo):
        raise InvalidRepo(repo)
    if not LOGIN_RE.match(login):
        raise InvalidLogin(login)
    items, caps, notes = github_fetch_items(
        repo,
        login,
        since=since,
        end=end,
        phrases=phrases,
        maintainers=maintainers,
        substantive_body_chars=substantive_body_chars,
        substantive_line_comments=substantive_line_comments,
        streams=frozenset({CODE_HOST}),
    )
    t_items, t_caps, t_notes = tracker.fetch(
        tracker_login or login,
        since=since,
        end=end,
        phrases=phrases,
        maintainers=tuple(tracker_maintainers) if tracker_maintainers is not None else maintainers,
    )
    merged_caps = list(dict.fromkeys([*caps, *t_caps]))
    return [*items, *t_items], merged_caps, [*notes, *t_notes]


def _fetch_many(
    repos: list[str],
    login: str,
    *,
    since: str,
    end: str,
    phrases: tuple[str, ...],
    maintainers: tuple[str, ...],
    substantive_body_chars: int,
    substantive_line_comments: int,
    tracker: TrackerBackend | None,
    tracker_login: str | None,
    tracker_maintainers: Iterable[str] | None,
) -> tuple[list[Item], list[str], list[str]]:
    for r in repos:
        if not REPO_RE.match(r):
            raise InvalidRepo(r)
    if not LOGIN_RE.match(login):
        raise InvalidLogin(login)
    streams = frozenset({CODE_HOST}) if tracker is not None else frozenset({CODE_HOST, TRACKER})
    items: list[Item] = []
    caps: list[str] = []
    notes: list[str] = []
    for r in repos:
        r_items, r_caps, r_notes = github_fetch_items(
            r,
            login,
            since=since,
            end=end,
            phrases=phrases,
            maintainers=maintainers,
            substantive_body_chars=substantive_body_chars,
            substantive_line_comments=substantive_line_comments,
            streams=streams,
        )
        items += [Item.from_json({**i.to_json(), "id": f"{r}:{i.id}"}) for i in r_items]
        caps += r_caps
        notes += [f"{r}: {n}" for n in r_notes]
    if tracker is not None:
        t_items, t_caps, t_notes = tracker.fetch(
            tracker_login or login,
            since=since,
            end=end,
            phrases=phrases,
            maintainers=tuple(tracker_maintainers) if tracker_maintainers is not None else maintainers,
        )
        items += t_items
        caps += t_caps
        notes += t_notes
    return items, list(dict.fromkeys(caps)), notes
