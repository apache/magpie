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
"""Everything release-vote-tally decides or renders around the tally itself.

Pure functions over `release-config` output, the tally, and the reply lines
the agent extracted. Nothing here fetches a thread, sends mail or applies a
label. Reply text is only ever matched against a strict vote grammar: a line
that is anything but a bare vote is left to the agent's judgement, and no
reply text reaches the `[RESULT] [VOTE]` body.
"""

from __future__ import annotations

import re
from typing import Any

from release_management.vote_tally.tally import is_weakening

DEFAULT_RESULT_SUBJECT = "[RESULT] [VOTE] Release <Product Name> <version> from <version>-rcN"
AMBIGUOUS_NOTE = re.compile(r"\bAMBIGUOUS\b")
# A bare vote: the value, optionally "(binding)" / "(non-binding)", optional final punctuation.
CLEAR_VOTE = re.compile(
    r"^\s*(?P<value>[+-]1|[+-]?0|[+-]?0?\.\d+)\s*(?:\(?\s*(?:non[- ]?)?binding\s*\)?)?\s*[.!]?\s*$",
    re.IGNORECASE,
)
FRACTIONAL = re.compile(r"^[+-]?0?\.\d+$")


class RenderError(ValueError):
    """The inputs ask for something the skill must not draft."""


def verdict(
    preflight: dict[str, Any],
    *,
    planning_issue: str | None,
    comments: str | None = None,
    ambiguous_note_acknowledged: bool = False,
) -> dict[str, Any]:
    """Step 0: the tool's blockers plus the planning-issue and previous-AMBIGUOUS checks."""
    values = preflight.get("values") or {}
    blockers = [str(b) for b in preflight.get("blockers") or []]
    # Fail closed: a preflight for another skill, one that did not report ok, or one
    # without the mechanism and roster can never let the tally proceed.
    if preflight.get("skill") != "vote-tally":
        blockers.append(
            f"the preflight output is for skill {preflight.get('skill')!r}, not 'vote-tally': "
            "run release-config preflight --skill vote-tally <version>-rcN"
        )
    if preflight.get("ok") is not True and not blockers:
        blockers.append("release-config preflight did not report ok: true; re-run it and fix what it reports")
    missing = [key for key in ("mechanism", "roster_path") if not values.get(key)]
    if missing:
        blockers.append(
            f"the preflight values carry no {' / '.join(missing)}: set release_approval_mechanism and the roster "
            "in release-management-config.md and re-run release-config preflight --skill vote-tally"
        )
    if not planning_issue:
        blockers.append(
            "no planning issue found: pass --planning-issue <url>, or label the open planning issue on <upstream> "
            "vote-open with the version in its title"
        )
    note = bool(comments and AMBIGUOUS_NOTE.search(comments))
    if note and not ambiguous_note_acknowledged:
        blockers.append(
            "the planning issue already has an AMBIGUOUS note from a previous release-vote-tally run: ask the RM "
            "whether to re-run from scratch or resolve it inline"
        )
    return {
        "verdict": "blocked" if blockers else "proceed",
        "blockers": blockers,
        "force_close": bool(values.get("force_close")),
        "mechanism": values.get("mechanism"),
        "roster_path": values.get("roster_path"),
        "previous_ambiguous_note": note,
        "warnings": [str(w) for w in preflight.get("warnings") or []],
    }


def _ids(loaded: dict[str, Any]) -> tuple[str, str]:
    meta = loaded.get("metadata") or {}
    version, rc = meta.get("version"), meta.get("rc") or meta.get("rc_number")
    if not version or not rc:
        raise RenderError(
            "release-config load output has no version / rc: run it with --skill vote-tally <version>-rcN"
        )
    return str(version), str(rc)


def _render(text: str, version: str, rc: str, product_name: str | None = None) -> str:
    out = (
        text.replace("<version>-<rcN>", f"{version}-{rc}")
        .replace("<version>-rcN", f"{version}-{rc}")
        .replace("<version>", version)
        .replace("<rcN>", rc)
    )
    if product_name:
        out = out.replace("<Product Name>", product_name)
    return out


def archive_url(loaded: dict[str, Any]) -> dict[str, Any]:
    """Step 1 (`dev-list-vote`): `mail_archive_url_template` rendered for the vote list."""
    config = loaded.get("config") or {}
    version, rc = _ids(loaded)
    template = config.get("mail_archive_url_template")
    vote_list = config.get("vote_dev_list")
    if not template:
        raise RenderError("mail_archive_url_template is unset in release-management-config.md")
    url = _render(str(template), version, rc)
    if vote_list:
        for key in ("<dev-list>", "<vote-list>", "<vote_dev_list>"):
            url = url.replace(key, str(vote_list))
    if re.search(r"<[^>]+>", url):
        raise RenderError(f"mail_archive_url_template still has a placeholder after rendering: {url}")
    return {"mail_archive": config.get("mail_archive"), "vote_list": vote_list, "url": url}


def classify_line(line: str) -> str | None:
    """The vote value of a bare vote line, or None when the line needs the agent's reading."""
    match = CLEAR_VOTE.match(line or "")
    if not match:
        return None
    value = match.group("value")
    if FRACTIONAL.match(value):
        return "fractional"
    if value in {"+1"}:
        return "+1"
    if value == "-1":
        return "-1"
    return "0"


def preclassify(replies: list[dict[str, Any]]) -> dict[str, Any]:
    """Step 1: pre-classify the bare vote lines; everything else is left for the agent to read."""
    out = []
    for index, reply in enumerate(replies):
        if not isinstance(reply, dict) or "from" not in reply:
            raise RenderError(f"reply #{index} needs 'from' and 'raw_vote_line'")
        value = classify_line(str(reply.get("raw_vote_line") or ""))
        out.append(
            {
                "from": reply["from"],
                "date": reply.get("date"),
                "raw_vote_line": reply.get("raw_vote_line"),
                "parsed_value": value,
                "needs_judgement": value is None,
            }
        )
    return {"replies": out, "needs_judgement": sum(1 for r in out if r["needs_judgement"])}


def result_draft(
    loaded: dict[str, Any],
    tally: dict[str, Any],
    *,
    product_name: str | None,
    result: str | None = None,
    rule: str | None = None,
    rm_name: str = "<RM name>",
) -> dict[str, Any]:
    """Step 3: the `[RESULT] [VOTE]` subject and body from the tally; nothing is recounted."""
    if "error" in tally:
        raise RenderError(f"the tally reported an error: {tally['error']}")
    if tally.get("halted_on_ambiguous"):
        raise RenderError(
            "the tally halted on AMBIGUOUS votes: resolve them on the thread and re-run, or pass --force-close <reason>"
        )
    weakening = [str(e) for e in tally.get("override_errors") or [] if is_weakening(str(e))]
    if weakening:
        raise RenderError(
            "vote_pass_rule_overrides tries to weaken the pass rule (Golden rule 5, a hard blocker): "
            + "; ".join(weakening)
            + " — fix release-management-config.md and re-run the tally"
        )
    outcome = tally.get("result")
    rule_text = tally.get("pass_rule_applied")
    if outcome is None and tally.get("mechanism") == "pr-approval":
        raise RenderError(
            "pr-approval has no rule without approval_pr_min_approvals: ask the RM to set it and re-run the tally "
            "with --min-approvals <N>; --result cannot stand in for it"
        )
    if outcome is None:
        if result not in ("PASSED", "FAILED") or not rule:
            raise RenderError(
                f"the tally has no result for mechanism {tally.get('mechanism')!r}: apply the configured rule to its "
                "counts and pass --result PASSED|FAILED with --rule '<the rule applied>'"
            )
        outcome, rule_text = result, rule
    config = loaded.get("config") or {}
    version, rc = _ids(loaded)
    subject = _render(
        str(config.get("result_subject_template") or DEFAULT_RESULT_SUBJECT), version, rc, product_name
    )
    if "<Product Name>" in subject:
        raise RenderError("result_subject_template uses <Product Name>: pass --product-name (project.md)")
    vote_list = config.get("vote_dev_list") or "<vote-list>"
    rows = [
        f"  {v['from']}  {v['value']}  {'binding' if v.get('binding') else 'non-binding'}"
        for v in tally.get("voters") or []
    ]
    rows += [f"  {a['from']}  AMBIGUOUS  excluded (--force-close)" for a in tally.get("ambiguous") or []]
    if outcome == "PASSED":
        next_lines = [
            "The release will proceed to Step 10 (promotion).",
            "Proposed next planning-issue label: `vote-passed`",
        ]
    else:
        next_lines = [
            f"The release candidate {version}-{rc} will be rolled back.",
            "Proposed next planning-issue label: `rc-rolled`",
        ]
    body = "\n\n".join(
        [
            f"To: {vote_list}\nSubject: {subject}",
            f"The vote has {outcome}.",
            "Binding votes:\n"
            f"  +1: {tally.get('binding_plus1', 0)}  (binding committer / PMC member votes)\n"
            f"  -1: {tally.get('binding_minus1', 0)}",
            f"Non-binding votes:\n  +1: {tally.get('nonbinding_plus1', 0)}\n  -1: {tally.get('nonbinding_minus1', 0)}",
            "\n".join(next_lines),
            "Vote details:\n" + ("\n".join(rows) if rows else "  (no votes)"),
            f"Thanks,\n{rm_name}",
        ]
    )
    counts = {
        key: int(tally.get(key) or 0)
        for key in (
            "binding_plus1",
            "binding_minus1",
            "binding_zero",
            "nonbinding_plus1",
            "nonbinding_minus1",
            "nonbinding_zero",
            "fractional_count",
            "excluded_ambiguous_count",
        )
    }
    return counts | {
        "result": outcome,
        "pass_rule_applied": rule_text,
        "subject": subject,
        "body": body,
        "proposed_label": "vote-passed" if outcome == "PASSED" else "rc-rolled",
        "force_close_logged": bool(tally.get("force_close")),
        "warnings": [f"configuration error: {e}" for e in tally.get("override_errors") or []],
        "text": f"Subject: {subject}\n\n{body}",
    }
