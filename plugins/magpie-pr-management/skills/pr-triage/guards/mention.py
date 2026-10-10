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

"""pr-management-triage mention guard (skill-contributed).

Deterministically enforces author-only notification (Golden rule 12): the PR
author is the only login the skill may @-mention. This applies identically to
the folded maintainer-triage note (`gh pr edit --body` / `--body-file`) and to
author-directed comments (`gh pr/issue comment`) — in both, the author's
@-mention is permitted (it is the intended "your move" signal) and any other
@-mention (a maintainer: operator, reviewer, CODEOWNER, team) is blocked.
Two exceptions lift the block: an explicit ``MAGPIE_ALLOW_MENTIONS=1`` override
(a deliberate one-off, requested by the operator), and the operator commenting
on their **own** PR/issue — when the target's author is the authenticated ``gh``
user, mentioning maintainers is a legitimate self-directed nudge to one's own
reviewers, not the drive-by maintainer spam this guard exists to stop.
Otherwise maintainer handles must be backtick-quoted so they never notify.

Two further surfaces:

* **Review and API posting** (`gh pr review --body/--body-file`, and every
  value a non-GET `gh api` call sends — every field, in every spelling `gh`
  accepts, and every `--input` string — whatever the endpoint): such text
  may @-mention nobody, not even the author, whose "your move" signal is
  the triage note.
* **Uninspectable text** (a body on stdin, an unreadable body or field
  file) is refused: the guard cannot confirm it is clean.
* **The mentoring hand-off**: `pr-management-mentor` hands a thread to the
  maintainers with a body that opens "@<team> — handing this off:". That one
  mention is allowed when <team> is the `maintainer_team_handle` of the
  *committed* `.apache-magpie-overrides/mentoring-config.md` (tracked and
  identical to `HEAD`), belongs to the organisation that owns the target
  repository, and is the only non-author mention in the body.

Discovered by
the agent-guard PreToolUse dispatcher from a guards.d directory — see
tools/agent-guard for the engine and the GuardContext API. Import-free:
everything comes from ``ctx``.
"""

TRIGGERS = ["gh"]


HANDOFF_OPENING = " — handing this off:"
UNREADABLE = "\x00UNREADABLE_BODY_FILE\x00"


def _uninspectable(what):
    return (
        f"agent-guard[mention]: the text of this {what} cannot be inspected (read from stdin, or an "
        "unreadable file), so the guard cannot confirm it @-mentions no maintainer. Pass the text in a "
        "readable file, or override with MAGPIE_ALLOW_MENTIONS=1 for a deliberate exception."
    )


def _nobody(what, mentions):
    return (
        f"agent-guard[mention]: {what} may not @-mention anyone; refusing to notify {mentions}. "
        "Reference them as backticked `login` (no @), or override with MAGPIE_ALLOW_MENTIONS=1 "
        "for a deliberate exception."
    )


def guard(ctx):
    # Anything a non-GET `gh api` call sends, whatever the endpoint. No author
    # exemption here.
    api = ctx.gh_api_posted_text()
    if api is not None:
        if ctx.override("MAGPIE_ALLOW_MENTIONS"):
            return None
        texts, readable = api
        if not readable:
            return _uninspectable("API call")
        mentions = sorted({m for text in texts for m in ctx.mentions(text)})
        return _nobody("text sent by `gh api`", mentions) if mentions else None

    sub = ctx.gh_subcommand()
    if sub == ("pr", "review") and (
        ctx.opt("-b", "--body") is not None or ctx.opt("-F", "--body-file") is not None
    ):
        if ctx.override("MAGPIE_ALLOW_MENTIONS"):
            return None
        body = ctx.gh_body(read_files=True)
        if ctx.opt("-F", "--body-file") == "-" or UNREADABLE in body:
            return _uninspectable("review")
        mentions = sorted(set(ctx.mentions(body)))
        return _nobody("a review body", mentions) if mentions else None

    sub = ctx.gh_subcommand()
    if sub is None:
        return None
    group, name = sub
    is_pr_body_edit = (
        group == "pr"
        and name == "edit"
        and (ctx.opt("-b", "--body") is not None or ctx.opt("-F", "--body-file") is not None)
    )
    is_comment = (group == "pr" and name == "comment") or (group == "issue" and name == "comment")
    if not (is_pr_body_edit or is_comment):
        return None

    if ctx.override("MAGPIE_ALLOW_MENTIONS"):
        return None
    body = ctx.gh_body(read_files=True)
    if ctx.opt("-F", "--body-file") == "-" or UNREADABLE in body:
        return _uninspectable("folded triage note" if is_pr_body_edit else "comment")
    mentions = ctx.mentions(body)
    if not mentions:
        return None

    # Both channels share one rule: only the PR/issue author may be @-mentioned.
    # Resolve the author from the target PR/issue number.
    target = ctx.positional_after("edit" if is_pr_body_edit else name)
    view = "pr" if group == "pr" else "issue"
    author = None
    if target:
        author = ctx.run(
            ["gh", view, "view", target, *ctx.repo_flag(), "--json", "author", "--jq", ".author.login"]
        )
    surface = "folded triage note" if is_pr_body_edit else "author-directed comment"
    if not author:
        return (
            f"agent-guard[mention]: this {surface} @-mentions "
            f"{sorted(set(mentions))} but the PR/issue author could not be verified, "
            "so the guard cannot confirm they are not a maintainer. Re-run once the "
            "author is known, drop the @-mentions (use backticked `login`), or override "
            "with MAGPIE_ALLOW_MENTIONS=1 if the mention is intentional."
        )
    # Operator's own PR/issue: when the target's author is the authenticated gh
    # user, mentioning maintainers is a self-directed nudge to one's own reviewers
    # (legitimate), not the drive-by maintainer spam this guard blocks. Resolution
    # failing falls through to the normal author-only rule (safe default).
    operator = ctx.run(["gh", "api", "user", "--jq", ".login"])
    if operator and operator.lower() == author.lower():
        return None
    offenders = sorted({m for m in mentions if m != author.lower()})
    if offenders and is_comment and _is_mentoring_handoff(ctx, offenders):
        return None
    if offenders:
        return (
            f"agent-guard[mention]: a {surface} may only @-mention the PR author "
            f"(`{author}`); refusing to notify maintainer(s) {offenders}. Reference "
            "them as backticked `login` (no @) so they are not pinged, or override with "
            "MAGPIE_ALLOW_MENTIONS=1 for a deliberate exception."
        )
    return None


def _is_mentoring_handoff(ctx, offenders):
    """The one mention the mentoring hand-off exists to make, and nothing else."""
    team = (
        (ctx.committed_config_value("mentoring-config.md", "maintainer_team_handle") or "")
        .lstrip("@")
        .lower()
    )
    if not team or "/" not in team or offenders != [team]:
        return False
    # The team must belong to the organisation that owns the repository the
    # comment goes to: a hand-off never reaches outside the project.
    if team.split("/", 1)[0] != (ctx.target_repo_owner() or ""):
        return False
    body = (ctx.gh_body(read_files=True) or "").lstrip().lower()
    return body.startswith(f"@{team}{HANDOFF_OPENING}")
