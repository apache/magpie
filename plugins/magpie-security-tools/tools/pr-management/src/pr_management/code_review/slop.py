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
"""Step 2.5 — the structural slop scan.

Every signal is computed here from the PR record and the unified diff. Three
of them carry a judgement the code cannot make, so they come back as
*candidates* the agent confirms or rejects: H1 (is the new directory an
independent project?), H5 (do the touched areas share no purpose?) and S2 (is
the body template only?). `outcome` applies the threshold table, H3+H4
correlation included, to whichever signals end up fired.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from typing import Any

from ..config import Config
from . import diff as difflib
from .data import PR
from .selectors import real_ci

HARD = ("H1", "H2", "H3", "H4", "H5")
SOFT = ("S1", "S2", "S3", "S4", "S5")
JUDGEMENT = frozenset({"H1", "H5", "S2"})

PROJECT_ROOT_FILES = frozenset(
    {
        "README.md",
        "README.rst",
        "README",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "package.json",
        "go.mod",
        "pom.xml",
        "build.gradle",
        "Cargo.toml",
        "Makefile",
    }
)
_MERGE = re.compile(r"^Merge (?:pull request|branch) #?\d* ?from ([^/\s]+)/", re.IGNORECASE)
_TICKET_TITLE = (
    re.compile(r"\[Ticket #\d+\]", re.IGNORECASE),
    re.compile(r"\bts/ticket[- ]?\d+", re.IGNORECASE),
    re.compile(r"\bsprint[- ]\d+", re.IGNORECASE),
    re.compile(r"\btask[- ]\d+", re.IGNORECASE),
    re.compile(r"\bticket[- ]?#?\d+", re.IGNORECASE),
)
_TOOLING = (
    re.compile(r"\bsprint\b", re.IGNORECASE),
    re.compile(r"\bkanban\b", re.IGNORECASE),
    re.compile(r"\bjira\b", re.IGNORECASE),
    re.compile(r"\bticket #", re.IGNORECASE),
    re.compile(r"\bstory #", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,4} \d{3}[A-Z]?\b"),  # a course code, e.g. CSS 566A
)
_FORK_URL = re.compile(r"https://github\.com/([A-Za-z0-9-]+)/([A-Za-z0-9._-]+)/(?:issues|pull)/\d+")
_FILLER = frozenset(
    {
        "see",
        "for",
        "context",
        "resolves",
        "resolve",
        "closes",
        "close",
        "fixes",
        "fix",
        "related",
        "ref",
        "refs",
        "the",
        "a",
        "an",
        "to",
        "and",
        "of",
        "in",
        "this",
        "pr",
        "issue",
    }
)


def _area(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 else parts[0]


def h1(files: list[difflib.DiffFile]) -> list[str]:
    """New top-level directories made only of new files and holding a project-root file."""
    by_top: dict[str, list[difflib.DiffFile]] = {}
    for f in files:
        if "/" in f.path:
            by_top.setdefault(f.path.split("/", 1)[0], []).append(f)
    found = []
    for top, members in sorted(by_top.items()):
        if not all(m.is_new for m in members):
            continue
        if any(m.path.split("/", 1)[1] in PROJECT_ROOT_FILES for m in members):
            found.append(top)
    return found


def h2(pr: PR, upstream: str | None) -> list[str]:
    hits = []
    for owner, repo in _FORK_URL.findall(pr.body):
        if owner.lower() == pr.author.lower() and f"{owner}/{repo}".lower() != (upstream or "").lower():
            hits.append(f"{owner}/{repo}")
    return hits


def h3(pr: PR) -> list[str]:
    """3+ merge commits from one fork within an hour of each other."""
    groups: dict[str, list[dt.datetime | None]] = {}
    for commit in pr.commits:
        match = _MERGE.match(commit.message)
        if match:
            groups.setdefault(match.group(1).lower(), []).append(commit.authored)
    for fork, times in groups.items():
        if len(times) < 3:
            continue
        stamps = sorted(t for t in times if t is not None)
        if len(stamps) < len(times):
            return [fork]  # no timestamps to rule it out
        if any(stamps[i + 2] - stamps[i] < dt.timedelta(minutes=60) for i in range(len(stamps) - 2)):
            return [fork]
    return []


def h4(pr: PR) -> list[str]:
    authors: list[str] = []
    for commit in pr.commits:
        for author in commit.authors:
            if author.lower() not in (a.lower() for a in authors):
                authors.append(author)
    return authors if len(authors) >= 3 else []


def h5(pr: PR) -> list[str]:
    areas = sorted({_area(p) for p in pr.files})
    return areas if len(areas) >= 5 else []


def s1(pr: PR) -> bool:
    return any(p.search(pr.title) for p in _TICKET_TITLE)


def s2(pr: PR, template: str | None) -> bool:
    """Template-only body: nothing left once template lines, comments, URLs and filler words go."""
    body = re.sub(r"<!--.*?-->", "", pr.body, flags=re.DOTALL)
    template_lines = {line.strip() for line in (template or "").splitlines() if line.strip()}
    words: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped in template_lines or stripped.startswith(("#", "- [", "* [", "---")):
            continue
        stripped = _FORK_URL.sub("", re.sub(r"https?://\S+|#\d+", "", stripped))
        words += [w for w in re.findall(r"[A-Za-z]+", stripped.lower()) if w not in _FILLER]
    return len(words) < 4


def s3(pr: PR, cfg: Config) -> bool:
    """Only bot checks reported; an empty or pending rollup is inconclusive."""
    if not pr.contexts or pr.rollup_state in (None, "PENDING", "EXPECTED"):
        return False
    return not real_ci(pr, cfg)


def s4(pr: PR, cfg: Config) -> bool:
    prefix = cfg.area_label_prefix or "area:"
    return sum(1 for label in pr.labels if label.startswith(prefix)) >= 3


def s5(pr: PR) -> bool:
    return sum(1 for c in pr.commits if any(p.search(c.message) for p in _TOOLING)) >= 2


def outcome(fired: Iterable[str]) -> str:
    """`early-exit`, `note-only` or `silent`, by the threshold table."""
    fired = set(fired)
    hard = [h for h in HARD if h in fired]
    soft = [s for s in SOFT if s in fired]
    hard_count = len(hard)
    if set(hard) == {"H3", "H4"}:
        hard_count = 1  # one root cause: a team fork merged internally
    if hard_count >= 2 or (hard_count == 1 and len(soft) >= 3):
        return "early-exit"
    if hard_count == 1 or len(soft) >= 2:
        return "note-only"
    return "silent"


def scan(pr: PR, files: list[difflib.DiffFile], cfg: Config, template: str | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    candidates: dict[str, Any] = {
        "H1": h1(files),
        "H2": h2(pr, cfg.upstream_repo),
        "H3": h3(pr),
        "H4": h4(pr),
        "H5": h5(pr),
        "S1": s1(pr),
        "S2": s2(pr, template),
        "S3": s3(pr, cfg),
        "S4": s4(pr, cfg),
        "S5": s5(pr),
    }
    for key, value in candidates.items():
        if value:
            evidence[key] = value
    fired = sorted(evidence)
    readmes = {
        top: [
            f.added_text()[:400]
            for f in files
            if f.path.startswith(top + "/") and f.path.split("/")[-1].lower().startswith("readme")
        ]
        for top in candidates["H1"]
    }
    return {
        "fired": {"hard": [h for h in HARD if h in fired], "soft": [s for s in SOFT if s in fired]},
        "needs_judgement": [k for k in fired if k in JUDGEMENT],
        "evidence": evidence,
        "h1_readmes_untrusted": readmes,
        "outcome": outcome(fired),
        "outcome_without_judgement": outcome(k for k in fired if k not in JUDGEMENT),
    }
