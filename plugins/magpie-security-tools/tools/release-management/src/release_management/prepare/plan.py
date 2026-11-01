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
"""release-prepare Step 0 (the verdict) and Step 1 (the planning issue).

Pure functions over what `release-config preflight --skill prepare` printed,
the facts the agent read (the planning issue, `gh` access) and the merged-PR
list `gh pr list --json` printed. Nothing here runs `gh` or opens an issue:
every output is a proposal the release manager confirms (Golden rule 1).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from release_management.prepare import prev_tag
from release_management.shell import dq, w

SCRATCH_PATH = re.compile(r"^<[a-z-]+>/[A-Za-z0-9_.+-]+$")

PLANNING_LABEL = {"prep": "release-planning", "post": "announced"}
EMPTY_HANDOFF = "No PRs merged since {tag}. RM must decide whether to skip or proceed."
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?$")
NO_LABEL = "(no label)"

STEPS = """\
## Steps

- [ ] Step 1: Planning issue open ← this issue
- [ ] Step 2: Prep PR open (`release-prepare prep {v}`)
- [ ] Step 3: KEYS reconciliation (`release-keys-sync`)
- [ ] Step 4\u20135: RC cut + stage (`release-rc-cut {v} rc1`)
- [ ] Step 6: Pre-flight verify (`release-verify-rc {v}-rc1`)
- [ ] Step 7: `[VOTE]` thread (`release-vote-draft {v}-rc1`)
- [ ] Step 8: Voting window
- [ ] Step 9: Tally (`release-vote-tally {v}-rc1`)
- [ ] Step 10: Promote (`release-promote {v}-rc1`)
- [ ] Step 11: Announce + site bump (`release-announce-draft {v}`)
- [ ] Step 12: Archive sweep (`release-archive-sweep`)
- [ ] Step 13: Audit log (`release-audit-report {v}`)
- [ ] Step 14: Post-release bump (`release-prepare post {v}`)"""

TAIL = """\
## Artefacts

<!-- release-rc-cut fills this in after Step 4\u20135 -->
- Staging URL: (TBD)
- Tag URL: (TBD)
- RC artefact list: (TBD)

## Timestamps

<!-- Skills fill these in as the lifecycle progresses -->
- Planning issue opened: {opened}
- Prep PR opened: (TBD)
- RC staged: (TBD)
- Vote opened: (TBD)
- Vote closed: (TBD)
- Promote commit: (TBD)
- [ANNOUNCE] sent: (TBD)"""


class RenderError(ValueError):
    """The draft cannot be rendered from these inputs; the skill surfaces this and stops."""


# --------------------------------------------------------------------------- Step 0


def inert_title(title: object) -> str:
    """A PR title as inert markdown text.

    PR titles are external content written by contributors. `<` / `>` / `&`
    are escaped so an HTML comment or tag in a title shows as text instead of
    being hidden by GitHub's renderer (where a later agent reading the issue
    would still see it), and line breaks are folded so a title cannot start
    new lines of the body.
    """
    text = " ".join(str(title or "").split())
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def train_coverage(lines: list[str], version: str | None) -> bool | None:
    """True when a release line covers `version`, False when the lines name only other trains, None when undecidable."""
    if version is None:
        return True
    results = [prev_tag.covers(line, version) for line in lines]
    if any(r is True for r in results):
        return True
    if any(r is False for r in results) or not lines:
        return False
    return None


def _major_train(version: str) -> str:
    return f"{version.split('.')[0]}.x"


def verdict(
    preflight: dict[str, Any],
    *,
    planning_issue: str | None = None,
    planning_labels: list[str] | None = None,
    gh_access: bool = False,
    previous_tag: str | None = None,
    train_confirmed: bool = False,
) -> dict[str, Any]:
    """Step 0: the preflight blockers plus the checks it cannot see, fail-closed.

    No `--gh-access` means `gh pr list --repo <upstream>` was not seen to
    succeed; no `--planning-issue` for `prep` / `post` means none was found.
    """
    values = preflight.get("values") or {}
    sub = values.get("sub_command") or "plan"
    version = values.get("version")
    blockers = [str(b) for b in preflight.get("blockers") or []]
    lines = [str(line) for line in values.get("release_lines") or []]
    covered: bool | None = True
    if sub != "automated-signing" and version:
        covered = train_coverage(lines, version)
        if covered is False and not train_confirmed:
            blockers.append(
                f"release-trains.md has no entry for version {version} or a {_major_train(version)} train"
            )
        elif covered is None and not train_confirmed:
            blockers.append(
                f"release-trains.md names no train pattern (e.g. `{_major_train(version)}`) or version that covers {version}: "
                "read values.release_lines and pass --train-confirmed if one of them is the train record"
            )
    label = PLANNING_LABEL.get(sub)
    if label and version:
        if not planning_issue:
            blockers.append(
                f"No open issue labelled {label} found for version {version}; "
                + (
                    "run Step 1 first or supply --planning-issue <url>"
                    if sub == "prep"
                    else "supply --planning-issue <url>"
                )
            )
        elif label not in (planning_labels or []):
            blockers.append(f"planning issue {planning_issue} is not labelled {label}")
    if not gh_access:
        blockers.append(
            "`gh pr list --repo <upstream>` did not succeed: check read access to the upstream repo"
        )
    read = []
    if any(b.startswith("automated release signing is not offered") for b in blockers):
        read.append("automated-signing-ineligible.md")
    return {
        "verdict": "blocked" if blockers else "proceed",
        "sub_command": sub,
        "version": version,
        "blockers": blockers,
        "release_branch_base": values.get("release_branch_base"),
        "previous_tag": values.get("previous_tag") or previous_tag,
        "train_covered": covered,
        "read": read,
    }


# --------------------------------------------------------------------------- Step 1a


def query(
    *, upstream: str, base: str, previous_tag: str | None, tag_date: str | None = None, limit: int = 500
) -> dict[str, Any]:
    """1a: the read that dates the previous tag, then the merged-PR query with that date."""
    if tag_date is not None and not ISO_DATE.match(tag_date.strip()):
        raise RenderError(f"--tag-date {tag_date!r} is not an ISO-8601 date or time")
    date = tag_date.strip() if tag_date else "<previous-tag-date>"
    date_command = (
        f"gh api repos/{w(upstream)}/commits/{w(previous_tag)} --jq .commit.committer.date"
        if previous_tag
        else None
    )
    pr_list = "\n".join(
        [
            f"gh pr list --repo {w(upstream)} \\",
            "  --state merged \\",
            f"  --base {w(base)} \\",
            f"  --search {dq('merged:>=' + date)} \\",
            "  --json number,title,url,labels,mergedAt \\",
            f"  --limit {limit}",
        ]
    )
    return {
        "previous_tag": previous_tag,
        "previous_tag_date": tag_date.strip() if tag_date else None,
        "date_command": date_command,
        "pr_list_command": pr_list,
        "ready": tag_date is not None,
    }


# --------------------------------------------------------------------------- Step 1b


def label_names(pr: dict[str, Any]) -> list[str]:
    names = []
    for label in pr.get("labels") or []:
        name = label.get("name") if isinstance(label, dict) else label
        if name:
            names.append(str(name))
    return names


def group_by_label(prs: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """PRs grouped by their first label, groups sorted by name, unlabelled last; PR order kept within a group."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for pr in prs:
        names = label_names(pr)
        groups.setdefault(names[0] if names else NO_LABEL, []).append(pr)
    order = sorted((g for g in groups if g != NO_LABEL), key=str.lower)
    if NO_LABEL in groups:
        order.append(NO_LABEL)
    return [(g, groups[g]) for g in order]


def pr_list(prs: list[dict[str, Any]]) -> str:
    out: list[str] = []
    n = 0
    for label, members in group_by_label(prs):
        if out:
            out.append("")
        out.append(f"### {label}")
        out.append("")
        for pr in members:
            n += 1
            out.append(f"{n}. #{pr.get('number')} {inert_title(pr.get('title'))} ({pr.get('url')})")
    return "\n".join(out)


def _default_body(fields: dict[str, str], prs: list[dict[str, Any]], version: str, opened: str) -> str:
    return "\n".join(
        [
            f"## Release: {fields['product']} {version}",
            "",
            f"**Release Manager:** {fields['rm']}",
            f"**Release train:** {fields['train']}",
            f"**Base branch:** {fields['base']}",
            f"**Previous release:** {fields['previous']}",
            "",
            "## In scope",
            "",
            pr_list(prs) if prs else "(no PRs merged since the previous release)",
            "",
            STEPS.format(v=version),
            "",
            TAIL.format(opened=opened),
        ]
    )


def _fill_template(
    text: str, fields: dict[str, str], prs: list[dict[str, Any]], version: str, opened: str
) -> str:
    subs = {
        "<Product Name>": fields["product"],
        "<product-name>": fields["product"],
        "<version>": version,
        "<previous-tag>": fields["previous"],
        "<release-branch-base>": fields["base"],
        "<train name>": fields["train"],
        "<release-manager>": fields["rm"],
        "<pr-list>": pr_list(prs),
        "<ISO-8601>": opened,
    }
    for key, value in subs.items():
        text = text.replace(key, value)
    return text


def render(
    prs: list[dict[str, Any]],
    *,
    version: str,
    product_name: str,
    previous_tag: str | None,
    base: str,
    upstream: str = "<upstream>",
    train: str | None = None,
    rm: str | None = None,
    template: str | None = None,
    skip_empty_check: str | None = None,
    opened_at: str | None = None,
    body_file: str | None = None,
) -> dict[str, Any]:
    """1a hand-off or 1b draft: the empty-set hand-off, else the issue title, body and `gh issue create` line."""
    tag = previous_tag or "<previous-tag>"
    if not prs and skip_empty_check is None:
        return {
            "empty_pr_set": True,
            "previous_tag": previous_tag,
            "handoff_reason": EMPTY_HANDOFF.format(tag=tag),
            "read": ["classifications/empty-pr-set.md"],
        }
    opened = opened_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    fields = {
        "product": product_name,
        "rm": rm or "<from release-trains.md or user.md>",
        "train": train or "<train name>",
        "base": base,
        "previous": previous_tag or "(none — first release)",
    }
    body = (
        _fill_template(template, fields, prs, version, opened)
        if template
        else _default_body(fields, prs, version, opened)
    )
    if skip_empty_check is not None:
        body += f"\n\n> `--skip-empty-check`: {skip_empty_check or 'no reason given'}"
    title = f"Release {product_name} {version}"
    path = body_file or f"<scratch>/planning-issue-body-{version}.md"
    command = "\n".join(
        [
            "gh issue create \\",
            f"  --repo {w(upstream)} \\",
            f"  --title {dq(title)} \\",
            f"  --body-file {path if SCRATCH_PATH.match(path) else w(path)} \\",
            '  --label "release-planning"',
        ]
    )
    unfilled = sorted(set(re.findall(r"<[A-Za-z][A-Za-z0-9 ._-]*>", body)))
    return {
        "issue_title": title,
        "issue_body": body,
        "pr_set_size": len(prs),
        "previous_tag": previous_tag,
        "empty_pr_set": False,
        "proposed": True,
        "body_file": path,
        "create_command": command,
        "unfilled_placeholders": unfilled,
    }
