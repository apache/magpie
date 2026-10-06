# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Jira backend: the tracker side (issues filed, triaged, commented) over Jira REST API v2.

The HTTP client is tools/jira's `jira_bridge.rest` — the tracker adapter owns the network
surface and its conventions (Data Center REST v2; `JIRA_API_TOKEN` / `JIRA_AUTH_SCHEME`, or a
token under `$HOME`; anonymous reads without one).  The tracker URL and project key come
from `<project-config>/issue-tracker-config.md`, flags, or `ISSUE_TRACKER_URL` /
`ISSUE_TRACKER_PROJECT`, resolved by the CLI.

Jira has no pull requests, so this backend never answers the code-host side.
Comment bodies are read here to find pushback candidates and never leave this module.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from jira_bridge.rest import JiraRest, JiraRestConfigError, JiraRestError

from contributor_metrics.backends.common import BackendError, first_pushback
from contributor_metrics.model import Item

USER_RE = re.compile(r"^[A-Za-z0-9._@+-]{1,255}$")
PROJECT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
FILED_PAGES = 3
SCAN_PAGES = 10
AUTHORED_BUDGET, THREAD_BUDGET = 50, 100
# Fields whose change by someone other than the reporter counts as triage.
TRIAGE_FIELDS = {"status", "labels", "component", "priority", "assignee", "resolution", "fix version"}
FIELDS = "created,updated,labels,resolution,reporter,comment"


class InvalidJiraUser(ValueError):
    pass


class InvalidJiraConfig(ValueError):
    pass


class JiraError(BackendError):
    pass


@dataclass
class JiraTracker:
    """Answers the tracker side of the seam from one Jira project."""

    url: str
    project: str
    token: str | None = None
    auth_scheme: str | None = None
    opener: Callable[[Any], Any] | None = field(default=None, repr=False)
    sleep: Callable[[float], None] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not PROJECT_RE.match(self.project):
            raise InvalidJiraConfig(f"invalid Jira project key {self.project!r}")
        try:
            self.rest = JiraRest(
                self.url, token=self.token, auth_scheme=self.auth_scheme, opener=self.opener, sleep=self.sleep
            )
        except JiraRestConfigError as exc:
            raise InvalidJiraConfig(str(exc)) from exc
        self.url = self.rest.url

    def _search(self, jql: str, pages: int, expand: str = "") -> tuple[list[dict[str, Any]], int]:
        try:
            return self.rest.search(jql, fields=FIELDS, pages=pages, expand=expand)
        except JiraRestError as exc:
            raise JiraError(str(exc)) from exc

    # -- shaping ------------------------------------------------------------

    def _browse(self, key: str) -> str:
        return f"{self.url}/browse/{key}"

    def _comments(self, issue: dict[str, Any]) -> list[dict[str, Any]]:
        key = issue["key"]
        out = []
        for c in ((issue.get("fields") or {}).get("comment") or {}).get("comments") or []:
            cid = c.get("id", "")
            out.append(
                {
                    "url": f"{self._browse(key)}?focusedCommentId={cid}#comment-{cid}",
                    "author": (c.get("author") or {}).get("name", ""),
                    "body": c.get("body") or "",
                    "created": c.get("created") or "",
                }
            )
        return out

    @staticmethod
    def _labels(issue: dict[str, Any]) -> tuple[str, ...]:
        return tuple((issue.get("fields") or {}).get("labels") or ())

    # -- the tracker side -----------------------------------------------------

    def fetch(
        self,
        login: str,
        *,
        since: str,
        end: str,
        phrases: Iterable[str],
        maintainers: Iterable[str],
    ) -> tuple[list[Item], list[str], list[str]]:
        """Issues filed, issues triaged and issue threads commented by `login` inside [since, end]."""
        if not USER_RE.match(login):
            raise InvalidJiraUser(login)
        phrases, maintainers = tuple(phrases), tuple(maintainers)
        who = login.lower()
        caps: list[str] = []
        notes: list[str] = []
        if not maintainers:
            notes.append(
                "jira: no maintainer roster given, so no pushback candidates were flagged on Jira issues"
            )
        proj = f'project = "{self.project}"'
        end_ts = f"{end} 23:59"

        def in_window(ts: str) -> bool:
            return since <= ts[:10] <= end

        # Issues filed.
        filed, total = self._search(
            f'{proj} AND reporter = "{login}" AND created >= "{since}" AND created <= "{end_ts}" ORDER BY created DESC',
            FILED_PAGES,
        )
        if total > len(filed):
            caps.append("issues_filed")
        items: list[Item] = []
        for rank, issue in enumerate(filed):
            f = issue.get("fields") or {}
            items.append(
                Item(
                    id=f"issue-{issue['key']}",
                    kind="issue",
                    url=self._browse(issue["key"]),
                    thread=self._browse(issue["key"]),
                    created_at=(f.get("created") or "")[:10],
                    closed_unmerged=f.get("resolution") is not None,
                    areas=self._labels(issue),
                    pushback_candidate=first_pushback(self._comments(issue), login, phrases, maintainers)
                    if rank < AUTHORED_BUDGET
                    else "",
                )
            )

        # Threads and triage: every issue touched in the window, plus the issues whose
        # tracked fields the user changed (found even when the broad scan is capped).
        changed = " OR ".join(
            f'{fld} CHANGED BY "{login}" DURING ("{since}", "{end_ts}")'
            for fld in ("status", "assignee", "priority", "resolution", "fixVersion")
        )
        scanned, scan_total = self._search(
            f'{proj} AND updated >= "{since}" AND created <= "{end_ts}" ORDER BY updated DESC',
            SCAN_PAGES,
            expand="changelog",
        )
        try:
            targeted, _ = self._search(
                f"{proj} AND ({changed}) ORDER BY updated DESC", FILED_PAGES, "changelog"
            )
        except JiraError as exc:  # e.g. a Jira that rejects CHANGED BY for this user
            targeted = []
            notes.append(f"jira: the field-change search failed ({exc}); triage relies on the scan alone")
        if scan_total > len(scanned):
            caps += ["issues_triaged", "threads_commented"]
            notes.append(
                f"jira: {scan_total - len(scanned)} issues updated in the window beyond the {len(scanned)} "
                "most recent were not scanned for comments; field changes were still searched directly"
            )
        candidates: dict[str, dict[str, Any]] = {}
        for issue in [*scanned, *targeted]:
            candidates.setdefault(issue["key"], issue)

        ranked = sorted(
            candidates.values(), key=lambda i: (i.get("fields") or {}).get("updated") or "", reverse=True
        )
        for rank, issue in enumerate(ranked):
            f = issue.get("fields") or {}
            key = issue["key"]
            comments = self._comments(issue)
            own = [
                c["created"][:10] for c in comments if c["author"].lower() == who and in_window(c["created"])
            ]
            edits = [
                h.get("created", "")[:10]
                for h in (issue.get("changelog") or {}).get("histories") or []
                if ((h.get("author") or {}).get("name") or "").lower() == who
                and in_window(h.get("created") or "")
                and any(str(i.get("field", "")).lower() in TRIAGE_FIELDS for i in h.get("items") or [])
            ]
            pushback = first_pushback(comments, login, phrases, maintainers) if rank < THREAD_BUDGET else ""
            url, areas = self._browse(key), self._labels(issue)
            if own:
                items.append(
                    Item(
                        id=f"thread-{key}",
                        kind="thread",
                        url=url,
                        thread=url,
                        created_at=min(own),
                        areas=areas,
                        pushback_candidate=pushback,
                    )
                )
            reporter = ((f.get("reporter") or {}).get("name") or "").lower()
            if reporter != who and (own or edits):
                items.append(
                    Item(
                        id=f"triage-{key}",
                        kind="triage",
                        url=url,
                        thread=url,
                        created_at=min(own + edits),
                        areas=areas,
                        pushback_candidate=pushback,
                    )
                )
        return items, caps, notes
