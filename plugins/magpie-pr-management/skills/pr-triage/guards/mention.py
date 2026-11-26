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

Deterministically enforces author-only notification (Golden rule 12) on what
`pr-management-triage` posts, and on nothing else. A body is triage's when it
carries a triage marker: the `<!-- pr-triage-fold: … -->` block of a folded
note, or the `<!-- pr-triage -->` line every triage comment opens with. Reviews,
comments and API calls from any other skill carry neither and pass untouched:
those skills mention people on purpose.

On a triage body, the PR author is the only login it may @-mention. This applies
identically to the folded triage note (`gh pr edit --body` / `--body-file`) and
to author-directed comments (`gh pr/issue comment`) — in both, the author's
@-mention is permitted (it is the intended "your move" signal) and any other
@-mention (a maintainer: operator, reviewer, CODEOWNER, team) is blocked.
Text a non-GET `gh api` call sends that carries a triage marker may @-mention
nobody, not even the author.

Three exceptions lift the block: an explicit ``MAGPIE_ALLOW_MENTIONS=1`` override
(a deliberate one-off, requested by the operator); the operator commenting on
their **own** PR/issue — when the target's author is the authenticated ``gh``
user, mentioning maintainers is a legitimate self-directed nudge to one's own
reviewers, not the drive-by maintainer spam this guard exists to stop; and the
handles in `mention_allowlist` of `.apache-magpie-overrides/pr-management-config.md`
*as GitHub serves it from the target repository's default branch* — the same
key every `pr-management` renderer honours. Only a reviewed, merged change can
put a handle there; a local edit, commit or scratch repository cannot.
Otherwise maintainer handles must be backtick-quoted so they never notify.

A body the guard cannot read (stdin, an unreadable file) cannot be shown to be
triage's and is let through: triage always posts from a readable file.

Discovered by
the agent-guard PreToolUse dispatcher from a guards.d directory — see
tools/agent-guard for the engine and the GuardContext API. Import-free:
everything comes from ``ctx``.
"""

TRIGGERS = ["gh"]


UNREADABLE = "\x00UNREADABLE_BODY_FILE\x00"
# The markers triage's renderer writes, compared with all whitespace removed.
TRIAGE_MARKERS = ("<!--pr-triage-->", "<!--pr-triage-fold:")


def _is_triage(text):
    """Whether ``text`` is a body `pr-management-triage` rendered."""
    flat = "".join(text.split())
    return any(marker in flat for marker in TRIAGE_MARKERS)


def _nobody(what, mentions):
    return (
        f"agent-guard[mention]: {what} may not @-mention anyone; refusing to notify {mentions}. "
        "Reference them as backticked `login` (no @), or override with MAGPIE_ALLOW_MENTIONS=1 "
        "for a deliberate exception."
    )


def _mention_handle(login):
    """The handle that @-mentions ``login``, lowercased.

    ``gh pr/issue view --json author`` reports a GitHub App author as
    ``app/<slug>`` and the REST API as ``<slug>[bot]``; either way the App is
    @-mentioned as ``@<slug>`` (``@dependabot rebase``). User logins contain
    neither ``/`` nor ``[``, so they pass through unchanged.
    """
    handle = login.strip().lower()
    handle = handle.removeprefix("app/")
    return handle.removesuffix("[bot]")


def _allowlist(ctx):
    """Handles the project lets every surface keep live: the committed `mention_allowlist`."""
    values = ctx.committed_config_values("pr-management-config.md", "mention_allowlist")
    return {v.strip().lstrip("@").lower() for v in values if v.strip()}


def guard(ctx):
    # Anything a non-GET `gh api` call sends, whatever the endpoint, when it is
    # a triage body. No author exemption here.
    api = ctx.gh_api_posted_text()
    if api is not None:
        texts, readable = api
        triage = [text for text in texts if _is_triage(text)]
        if not readable or not triage or ctx.override("MAGPIE_ALLOW_MENTIONS"):
            return None
        mentions = sorted({m for text in triage for m in ctx.mentions(text)} - _allowlist(ctx))
        return _nobody("triage text sent by `gh api`", mentions) if mentions else None

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

    if ctx.opt("-F", "--body-file") == "-":
        return None
    body = ctx.gh_body(read_files=True)
    if UNREADABLE in body or not _is_triage(body):
        return None
    if ctx.override("MAGPIE_ALLOW_MENTIONS"):
        return None
    mentions = ctx.mentions(body)
    if not set(mentions) - _allowlist(ctx):
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
    surface = "folded triage note" if is_pr_body_edit else "triage comment"
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
    author_handle = _mention_handle(author)
    offenders = sorted({m for m in mentions if m != author_handle} - _allowlist(ctx))
    if offenders:
        return (
            f"agent-guard[mention]: a {surface} may only @-mention the PR author "
            f"(`{author}`); refusing to notify maintainer(s) {offenders}. Reference "
            "them as backticked `login` (no @) so they are not pinged, or override with "
            "MAGPIE_ALLOW_MENTIONS=1 for a deliberate exception."
        )
    return None
