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
Discovered by
the agent-guard PreToolUse dispatcher from a guards.d directory — see
tools/agent-guard for the engine and the GuardContext API. Import-free:
everything comes from ``ctx``.
"""

TRIGGERS = ["gh"]


def guard(ctx):
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

    mentions = ctx.mentions(ctx.gh_body(read_files=True))
    if not mentions:
        return None
    if ctx.override("MAGPIE_ALLOW_MENTIONS"):
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
    if offenders:
        return (
            f"agent-guard[mention]: a {surface} may only @-mention the PR author "
            f"(`{author}`); refusing to notify maintainer(s) {offenders}. Reference "
            "them as backticked `login` (no @) so they are not pinged, or override with "
            "MAGPIE_ALLOW_MENTIONS=1 for a deliberate exception."
        )
    return None
