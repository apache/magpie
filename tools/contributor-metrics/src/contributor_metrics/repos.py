# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Which of a project's repositories had activity in a window.

The candidate names come from the caller (for ASF projects, the people directory's repository
list), because a keyword search there also returns other projects' repositories. Only names
that are the project's slug or start with `<slug>-` are kept; the others are reported as
excluded by name, never silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from contributor_metrics.backends.github import search_count

NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def belongs_to(name: str, project: str) -> bool:
    """True when `name` is the project's slug or starts with `<slug>-`, case-insensitively."""
    n, p = name.lower(), project.lower()
    return n == p or n.startswith(p + "-")


def active_repos(
    owner: str,
    project: str,
    names: Iterable[str],
    *,
    since: str,
    end: str,
    count: Callable[[str], int] | None = None,
) -> dict[str, Any]:
    """Sort candidate repositories into active, inactive, or excluded by name.

    A repository is active when at least one PR was merged, or one issue or PR opened, in
    [since, end]. A name with no repository on the code host searches as empty, so it is
    inactive. Every list is sorted by name. `count` defaults to the code-host search count.
    """
    count = count or search_count
    seen: dict[str, None] = {}
    invalid: list[str] = []
    excluded: list[str] = []
    for raw in names:
        name = raw.strip().removesuffix(".git").rsplit("/", 1)[-1]
        if not name:
            continue
        if not NAME_RE.match(name):
            invalid.append(name)
        elif not belongs_to(name, project):
            excluded.append(name)
        else:
            seen.setdefault(name.lower(), None)
    active: list[dict[str, Any]] = []
    inactive: list[dict[str, Any]] = []
    for name in sorted(seen):
        repo = f"{owner}/{name}"
        merged = count(f"repo:{repo} is:pr is:merged merged:{since}..{end}")
        opened = count(f"repo:{repo} created:{since}..{end}")
        row = {"repo": repo, "merged_prs": merged, "opened": opened}
        (active if merged or opened else inactive).append(row)
    return {
        "owner": owner,
        "project": project,
        "since": since,
        "end": end,
        "active": active,
        "inactive": inactive,
        "excluded_by_name": sorted(set(excluded), key=str.lower),
        "invalid_names": sorted(set(invalid)),
    }
