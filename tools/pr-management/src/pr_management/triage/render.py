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
"""Render the contributor-facing body of a triage action.

Under the default `triage_feedback_channel: pr-body` every contributor-facing
action renders the one folded maintainer-triage note (comment-templates.md,
"The folded maintainer-triage note — the single contributor channel", which
supersedes the per-template bodies), wrapped in the `pr-triage-fold` markers
for `triage fold` to splice into the PR description. Under `comment` the
legacy per-template comment body is rendered, ending with the long
AI-attribution footer.

Three rules are enforced on every body, whatever the template says:

* The PR author is the only `@`-mention; any other handle is backtick-quoted.
* No bare `#NNN`: each becomes a link to the upstream PR.
* No placeholder survives silently: an unresolved `<placeholder>` is a warning.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from .. import ci, markers, mdconfig, mentions
from ..config import CONFIRMATION_MARKER, FOLD_CLOSE, FOLD_OPEN, Config
from ..model import PR
from . import signals

#: Actions that produce no contributor-facing body.
NO_BODY = frozenset({"rerun", "rebase", "approve-workflow", "promote-bot-draft", "skip"})

#: Folded-note framing and next-step lines, per template stem (the per-action table).
FOLDED: dict[str, tuple[str, str]] = {
    "draft": (
        "Helpful heads-up from the maintainers — please address before this PR can be reviewed:",
        "Fix the above, then mark it **Ready for review**.",
    ),
    "comment": (
        "Helpful heads-up from the maintainers — please address before this PR can be reviewed:",
        "Fix the above, then mark it **Ready for review**.",
    ),
    "close": (
        "This PR is being closed — it has multiple violations of our quality criteria:",
        "Open a fresh PR once the above is addressed — no rush.",
    ),
    "security-language": (
        "This PR's title, body, or commit messages contain language that may indicate a security fix:",
        "Neutralise the language (title, body, commit messages), or reply with a link to the published "
        "advisory if the CVE is already announced.",
    ),
    "review-nudge": (
        "Some review feedback from <reviewer_logins> is waiting on you:",
        "Reply or push a fix in each thread, then mark them resolved.",
    ),
    "reviewer-ping": (
        "Some review feedback from <reviewer_logins> is waiting on you:",
        "Reply or push a fix in each thread, then mark them resolved.",
    ),
    "request-author-confirmation": (
        "Your review threads look addressed — please confirm this PR is **ready for maintainer review "
        "confirmation**:",
        "Mark the thread(s) as resolved and ping the reviewer (<reviewer_logins>) for a final look.",
    ),
    "request-author-confirmation-maintainer-sweep": (
        "Your review threads look addressed — please confirm this PR is **ready for maintainer review "
        "confirmation**:",
        "Reply `yes / ready` and a maintainer will pick it up from the queue.",
    ),
    "stale-draft-close": (
        "This PR is being closed to keep the queue clean:",
        "Reopen or open a fresh PR once addressed — no rush.",
    ),
    "stale-draft-close-untriaged": (
        "This PR is being closed to keep the queue clean:",
        "Reopen or open a fresh PR once addressed — no rush.",
    ),
    "stale-ready-label-close": (
        "This PR is being closed to keep the queue clean:",
        "Reopen or open a fresh PR once addressed — no rush.",
    ),
    "inactive-to-draft": (
        "Paused pending your next update:",
        "Rebase, address new failures, and mark **Ready for review** again.",
    ),
    "stale-workflow-approval": (
        "Paused pending your next update:",
        "Rebase, address new failures, and mark **Ready for review** again.",
    ),
    "stale-ready-label-strip": (
        "The `<ready_label>` label was removed because the next step here is yours:",
        "<next_move> — it goes back into the maintainer queue automatically once that's done.",
    ),
}

PLACEHOLDER = re.compile(
    r"<(?!(?:sub|br|details|summary|b|i|code|kbd)>)(?:[a-z][a-z0-9_]*|PROJECT|N|security-list)>"
)
_HANDLE = re.compile(r"(?<![\w`/\[])@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9_.-]+)?)(?![\w`])")
_BARE_REF = re.compile(r"(?<![\w\[/#&`])#(\d{1,7})\b(?!\]\()")


@dataclass
class Rendered:
    pr: int
    action: str
    channel: str
    template: str | None
    body: str | None
    mentions: list[str] = field(default_factory=list)
    assign_author: bool = False
    unassign_author: bool = False
    warnings: list[str] = field(default_factory=list)


def load_template(stem: str) -> str:
    text = resources.files("pr_management").joinpath("templates", f"{stem}.tmpl").read_text(encoding="utf-8")
    text = re.sub(r"\A<!--.*?-->\n*", "", text, flags=re.DOTALL)
    return text


def template_overrides(resolver: mdconfig.Resolver) -> dict[str, str]:
    """`### <template-name>` bodies under § Template body overrides (the first fence, else the text)."""
    text = resolver.read("pr-management-triage-comment-templates.md")
    section = mdconfig.section(text, "Template body overrides")
    if not section:
        return {}
    found: dict[str, str] = {}
    parts = re.split(r"^###\s+(.+?)\s*$", section, flags=re.MULTILINE)
    for name, body in zip(parts[1::2], parts[2::2], strict=False):
        stem = name.strip().strip("`").strip()
        content = mdconfig.first_fence(body)
        if content is None:
            content = "\n".join(line for line in body.strip().splitlines() if not line.startswith(">"))
        if content.strip():
            found[stem] = content.strip("\n") + "\n"
    return found


def security_list(resolver: mdconfig.Resolver) -> str | None:
    value = mdconfig.key_values(resolver.read("project.md")).get("security_list")
    return value if value and "<" not in value else None


def pick_template(action: str, classification: str | None, cfg: Config, *, has_fold: bool) -> str | None:
    if action in NO_BODY:
        return None
    if action in ("mark-ready", "ready"):
        return "ready-flip" if (has_fold or action == "ready") else None
    if action == "flag-suspicious":
        return "suspicious-changes"
    if action == "strip-ready-label":
        return "stale-ready-label-strip"
    if action == "request-author-confirmation":
        if cfg.handback_mode == "maintainer-sweep":
            return "request-author-confirmation-maintainer-sweep"
        return "request-author-confirmation"
    if action == "ping":
        return "review-nudge" if classification == "stale_review" else "reviewer-ping"
    if action == "comment":
        return "security-language" if classification == "security_language_signal" else "comment"
    if action == "close":
        if classification == "stale_draft":
            return "stale-draft-close"
        if classification == "stale_draft_untriaged":
            return "stale-draft-close-untriaged"
        if classification == "stale_ready_label_unhealthy":
            return "stale-ready-label-close"
        return "close"
    if action == "draft":
        if classification == "inactive_open":
            return "inactive-to-draft"
        if classification == "stale_workflow_approval":
            return "stale-workflow-approval"
        return "draft"
    raise ValueError(f"no template for action {action!r}")


def _backticked(logins: list[str]) -> str:
    return ", ".join(f"`{login}`" for login in logins)


def _violations(pr: PR, cfg: Config, details: dict[str, Any], *, flagged: int | None) -> list[str]:
    """One bullet per category — never one per failing check."""
    line = load_template("violations").strip("\n")
    criteria = cfg.urls.get("<quality_criteria_url>", "<quality_criteria_url>")
    bullets: list[tuple[str, str, str, str]] = []
    if details.get("conflict", pr.mergeable == "CONFLICTING"):
        bullets.append(
            (":x:", "Merge conflicts", "", cfg.conflicts_url or cfg.contributing_docs_url or criteria)
        )
    failed = details.get("failed_checks")
    if failed is None:
        failed = ci.failed_checks(pr)
    seen: list[str] = []
    for name in failed:
        category = cfg.category_for(name)
        if category.category in seen:
            continue
        seen.append(category.category)
        bullets.append((":x:", category.category, "", category.url or cfg.contributing_docs_url or criteria))
    if not failed and pr.rollup_state == "FAILURE":
        bullets.append((":x:", "Failing CI checks", "", cfg.contributing_docs_url or criteria))
    copilot = details.get("copilot_thread")
    if copilot:
        bullets.append((":x:", "Unaddressed Copilot review", f": [thread]({copilot})", criteria))
    threads = details.get("unresolved_threads")
    if threads is None:
        threads = len(signals.collaborator_threads(pr))
    if threads:
        bullets.append((":x:", "Unresolved review comments", f": {threads} thread(s)", criteria))
    if flagged is not None and flagged > signals.FLAGGED_AUTHOR_THRESHOLD:
        bullets.append(
            (
                ":x:",
                "Multiple flagged PRs",
                f": {flagged} of your PRs are currently flagged for quality issues. Please focus on those "
                "before opening new ones",
                criteria,
            )
        )
    rendered = []
    for icon, name, payload, link in bullets:
        rendered.append(
            line.replace("<icon>", icon)
            .replace("<category>", name)
            .replace("<payload>", payload)
            .replace("<doc_link>", link)
        )
    return rendered


def _flagged_count(pr: PR, prs: list[PR], cfg: Config, now: dt.datetime) -> int:
    return sum(
        1 for other in prs if other.author == pr.author and signals.compute(other, cfg, now).deterministic
    )


def _weeks(delta: dt.timedelta) -> int:
    return max(1, delta.days // 7)


def _values(
    pr: PR,
    cfg: Config,
    details: dict[str, Any],
    *,
    viewer: str,
    now: dt.datetime,
    flagged: int | None,
    sec_list: str | None,
) -> dict[str, str]:
    reviewers = details.get("reviewers")
    if reviewers is None:
        reviewers = signals.reviewers(signals.collaborator_threads(pr))
    stale = [r.author for r in pr.reviews if r.state == "CHANGES_REQUESTED"]
    if not reviewers and stale:
        reviewers = stale
    threads = details.get("unresolved_threads")
    if threads is None:
        threads = len(signals.collaborator_threads(pr))
    matches = details.get("security_matches")
    if matches is None:
        matches = signals.security_matches(pr)
    behind = pr.commits_behind if pr.commits_behind is not None else details.get("commits_behind")
    rebase = ""
    if isinstance(behind, int) and behind > signals.MAX_COMMITS_BEHIND:
        rebase = (
            load_template("rebase-note")
            .strip("\n")
            .replace("<commits_behind>", str(behind))
            .replace("<base>", pr.base or cfg.default_branch)
        )
    marker = markers.any_triage_marker(pr, cfg.marker)
    values: dict[str, str] = {
        "<author>": pr.author,
        "<operator>": viewer,
        "<base>": pr.base or cfg.default_branch,
        "<ready_label>": cfg.ready_label,
        "<N>": str(threads),
        "<reviewer_logins>": _backticked(reviewers) if reviewers else "the reviewers",
        "<violations>": "\n".join(_violations(pr, cfg, details, flagged=flagged)),
        "<rebase_note_if_needed>": rebase,
        "<security_matches>": "\n".join(f'- {_where(m["where"])}: "{m["match"]}"' for m in matches),
        "<weeks_since_activity>": str(_weeks(now - pr.updated)) if pr.updated else "",
        "<days_since_triage>": str((now - marker.at).days) if marker else "",
        "<bitrot_signal>": _bitrot(pr),
    }
    for key in (
        "days_since_maintainer",
        "strip_reason",
        "next_move",
        "days_since_triage",
        "weeks_since_activity",
    ):
        if details.get(key) not in (None, ""):
            values[f"<{key}>"] = str(details[key])
    display = cfg.urls.get("<project_display_name>") or cfg.project_name
    if display:
        values["<PROJECT>"] = display
    if sec_list:
        values["<security-list>"] = sec_list
    for key, value in cfg.urls.items():
        values.setdefault(key, value)
    return {k: v for k, v in values.items() if v != "" or k in ("<rebase_note_if_needed>",)}


def _where(where: str) -> str:
    if where == "title":
        return "PR title"
    if where == "body":
        return "PR body"
    return where.split(":", 1)[0]


def _bitrot(pr: PR) -> str:
    red = pr.rollup_state == "FAILURE"
    conflict = pr.mergeable == "CONFLICTING"
    if red and conflict:
        return f"failing CI and merge conflicts with {pr.base}"
    if conflict:
        return f"merge conflicts with {pr.base}"
    if red:
        return "failing CI"
    return ""


def _substitute(text: str, values: dict[str, str]) -> str:
    for key in sorted(values, key=len, reverse=True):
        text = text.replace(key, values[key])
    return text


def enforce(
    text: str, author: str, upstream: str | None, allowed: frozenset[str] = frozenset()
) -> tuple[str, list[str]]:
    """Author-only `@`-mentions — plus any `allowed` handle — and no bare `#NNN`, outside code and comments."""
    out_lines = []
    mentioned: list[str] = []
    inside_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            inside_fence = not inside_fence
            out_lines.append(line)
            continue
        if inside_fence or line.lstrip().startswith("<!--"):
            out_lines.append(line)
            continue
        pieces = re.split(r"(`[^`]*`)", line)
        for i, piece in enumerate(pieces):
            if piece.startswith("`") and piece.endswith("`") and len(piece) > 1:
                continue

            def handle(match: re.Match[str]) -> str:
                login = match.group(1)
                if login.lower() == author.lower() or login.lower() in allowed:
                    if login not in mentioned:
                        mentioned.append(login)
                    return match.group(0)
                return f"`@{login}`"

            piece = _HANDLE.sub(handle, piece)
            if upstream:
                piece = _BARE_REF.sub(
                    lambda m: f"[#{m.group(1)}](https://github.com/{upstream}/pull/{m.group(1)})", piece
                )
            pieces[i] = piece
        out_lines.append("".join(pieces))
    return "\n".join(out_lines), mentioned


def _tidy(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip("\n") + "\n"


def _quoted(lines: list[str]) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in lines)


def _note_body(stem: str, values: dict[str, str], override: str | None, cfg: Config) -> list[str]:
    criteria_link = f"[{cfg.marker}]({values.get('<quality_criteria_url>', '<quality_criteria_url>')})"
    if override is not None:
        text = re.sub(r"^@<author>\s*", "", override.strip())
        text = text.replace("<ai_attribution_footer>", "").replace("<ai_attribution_footer_body>", "")
        custom = _substitute(text, values).strip().splitlines()
        if cfg.marker not in "\n".join(custom):
            custom += ["", f"See our {criteria_link}."]
        return custom
    lines: list[str] = []
    if stem in ("draft", "comment", "close"):
        lines += values.get("<violations>", "").splitlines()
        if values.get("<rebase_note_if_needed>"):
            lines += ["", values["<rebase_note_if_needed>"].removeprefix("> ")]
    elif stem == "security-language":
        lines += values.get("<security_matches>", "").splitlines()
        lines += [
            "",
            "References to the security nature of a fix must not appear in public-facing content until the "
            "CVE is formally announced. If you have not reported this privately, please do so via "
            f"`{values.get('<security-list>', '<security-list>')}` before continuing.",
        ]
    elif stem in ("review-nudge",):
        lines.append(
            f"- New commits since the last review requesting changes from {values['<reviewer_logins>']}."
        )
    elif stem in ("reviewer-ping",):
        lines.append(f"- {values['<N>']} unresolved review thread(s) from {values['<reviewer_logins>']}.")
    elif stem.startswith("request-author-confirmation"):
        lines.append(
            f"- {values['<N>']} unresolved review thread(s) from {values['<reviewer_logins>']}, and you have "
            "engaged with each one."
        )
    elif stem == "stale-draft-close":
        lines.append(
            f"- No author response for {values.get('<days_since_triage>', '?')} days since the last triage note."
        )
    elif stem in ("stale-draft-close-untriaged", "inactive-to-draft"):
        lines.append(f"- No activity for {values.get('<weeks_since_activity>', '?')} weeks.")
    elif stem == "stale-workflow-approval":
        lines.append(
            f"- Awaiting workflow approval with no activity for {values.get('<weeks_since_activity>', '?')} weeks."
        )
    elif stem == "stale-ready-label-close":
        lines.append(
            f"- No author response for {values.get('<days_since_maintainer>', '<days_since_maintainer>')} days, "
            f"and the branch now has {values.get('<bitrot_signal>', '<bitrot_signal>')}."
        )
    elif stem == "stale-ready-label-strip":
        lines.append(f"- {values.get('<strip_reason>', '<strip_reason>')}")
    lines += ["", f"See our {criteria_link}."]
    return lines


def render(
    pr: PR,
    cfg: Config,
    *,
    action: str,
    classification: str | None,
    viewer: str,
    now: dt.datetime,
    details: dict[str, Any] | None = None,
    prs: list[PR] | None = None,
    overrides: dict[str, str] | None = None,
    sec_list: str | None = None,
    template: str | None = None,
) -> Rendered:
    details = dict(details or {})
    overrides = overrides or {}
    fold = markers.parse_fold(pr.body)
    stem = template or pick_template(action, classification, cfg, has_fold=fold is not None)
    channel = cfg.feedback_channel
    if stem is None:
        return Rendered(pr.number, action, channel, None, None)
    flagged = details.get("flagged_count")
    if flagged is None and stem == "close" and prs is not None:
        flagged = _flagged_count(pr, prs, cfg, now)
    values = _values(pr, cfg, details, viewer=viewer, now=now, flagged=flagged, sec_list=sec_list)
    stamp = now.astimezone(dt.UTC)
    values["<stamp>"] = stamp.strftime("%Y-%m-%d %H:%M UTC")
    result = Rendered(pr.number, action, channel, stem, None)

    # suspicious-changes is a close notice posted on every PR by the author,
    # deliberately terse and without the footer; it never folds.
    folded = channel == "pr-body" and stem != "suspicious-changes"
    if stem == "suspicious-changes":
        result.channel = "comment"
    if folded:
        if stem == "ready-flip":
            body = overrides.get("ready-flip") or load_template("ready-flip")
            body = _substitute(body, values)
            fold_action = "ready"
            result.unassign_author = True
        else:
            skeleton = overrides.get("folded-note") or load_template("folded-note")
            framing, next_step = FOLDED[stem]
            note = _note_body(stem, values, overrides.get(stem), cfg)
            body = skeleton.replace("<framing>", framing).replace("<next_step>", next_step)
            body = body.replace("<note_body>", _quoted(note))
            body = _substitute(body, values)
            fold_action = action
            result.assign_author = True
        triaged = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        opening = (
            f"<!-- {FOLD_OPEN}: triaged={triaged} head={pr.short_sha} action={fold_action} by={viewer} -->"
        )
        body = f"{opening}\n\n{_tidy(body)}\n<!-- {FOLD_CLOSE} -->\n"
    else:
        body = overrides.get(stem) or load_template(stem)
        footer = cfg.footer or load_template("ai-attribution-footer").strip("\n")
        values["<ai_attribution_footer>"] = _substitute(footer, values)
        body = _tidy(_substitute(body, values))
        if stem == "ready-flip":
            result.unassign_author = True

    body, mentioned = enforce(body, pr.author, cfg.upstream_repo, mentions.allowed(cfg))
    result.body = body
    result.mentions = [f"@{m}" for m in mentioned]
    leftover = sorted(set(PLACEHOLDER.findall(re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL))))
    for name in leftover:
        result.warnings.append(f"unresolved placeholder {name} — set it in <project-config> before posting")
    if stem.startswith("request-author-confirmation") and CONFIRMATION_MARKER not in body:
        result.warnings.append(f"the confirmation marker {CONFIRMATION_MARKER!r} is missing from the body")
    if (
        stem not in ("suspicious-changes", "ready-flip")
        and cfg.marker not in body
        and stem in ("draft", "comment", "close", "security-language")
    ):
        result.warnings.append(f"the triage marker {cfg.marker!r} is missing from the body")
    return result


def load_details(path: Path | None) -> dict[str, Any]:
    """A classify group entry (or its `details`) saved to a file."""
    if path is None:
        return {}
    import json

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "details" in data and isinstance(data["details"], dict):
        merged = dict(data["details"])
        merged.setdefault("classification", data.get("classification"))
        return merged
    return data if isinstance(data, dict) else {}
