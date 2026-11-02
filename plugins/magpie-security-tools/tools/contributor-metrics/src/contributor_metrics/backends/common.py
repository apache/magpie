# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""What every fetch backend shares: the two sides of the seam, the error base, pushback phrases.

A project's activity comes from two places that need not be the same system:

* the **code host** answers `contract:change-request` — PRs authored, reviews given, and the
  conversation threads on those PRs;
* the **tracker** answers `contract:tracker` — issues filed, issues triaged, and the
  conversation threads on issues.

A backend implements one side or both.  Whatever it reads, only links, dates and flags leave
it: comment bodies are inspected inside the backend for pushback phrases and dropped.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

CODE_HOST = "code_host"
TRACKER = "tracker"

GENERIC_PHRASES = (
    "ai-generated",
    "ai generated",
    "llm",
    "chatgpt",
    "copilot",
    "slop",
    "did you review",
    "review your own",
    "did you run",
    "unreviewed",
    "hallucinat",
    "does not exist",
    "stop posting",
)


class BackendError(RuntimeError):
    """A backend could not answer: a network, auth, or API error that retries did not clear."""


def first_pushback(
    comments: Iterable[Mapping[str, Any]], login: str, phrases: Iterable[str], maintainers: Iterable[str]
) -> str:
    """URL of the first rostered maintainer comment containing a pushback phrase, or "".

    For backends with no author-association signal: each comment is
    `{"url", "author", "body"}` and only `maintainers` count.  A candidate, not a verdict.
    """
    wanted = tuple(p.lower() for p in (*GENERIC_PHRASES, *phrases) if p.strip())
    maint = {m.lower() for m in maintainers}
    for c in comments:
        who = str(c.get("author") or "").lower()
        if not who or who == login.lower() or who not in maint:
            continue
        body = str(c.get("body") or "").lower()
        if any(p in body for p in wanted):
            return str(c["url"])
    return ""
