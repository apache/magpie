<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — gather per-tracker state

## Step 2 — Gather per-tracker state

For each tracker in the list, gather (in parallel where possible)
the inputs the classifier needs.
Items 1 and 3's `closedByPullRequestsReferences` are fetched for the whole list in one batched read, not per tracker;
the remaining items are per-tracker. Each tracker gets:

1. **Issue body + last 10 comments** — one aliased GraphQL query per chunk of up to 20 trackers from the Step 1 list
   (a list of 20 or fewer is one round-trip; larger lists take ⌈N/20⌉, which keeps each response well inside GitHub's GraphQL timeout).
   Write the query with the Write tool to a scratch file — it holds only issue numbers and the `<tracker>` owner/name — and run it as a plain `gh api graphql -F query=@<file>`:

   ```graphql
   query {
     repository(owner: "<owner>", name: "<repo>") {
       i<N1>: issue(number: <N1>) {
         number title body updatedAt
         labels(first: 30) { nodes { name } }
         milestone { title }
         assignees(first: 10) { nodes { login } }
         comments(last: 10) { nodes { author { login } createdAt body } }
         closedByPullRequestsReferences(first: 10, includeClosedPrs: true) {
           nodes { number url state mergedAt repository { nameWithOwner } }
         }
       }
       # repeat one aliased block per tracker in the chunk
     }
   }
   ```

   A `null` alias means the number does not exist in `<tracker>` (typically a mistyped `#NNN` selector) — surface it and drop that number; do not retry per tracker.
   This batched result is the source for items 1–3 below; later steps and bulk-mode subagents reuse it rather than calling `gh issue view`.
   Apply the redact-after-fetch protocol on the body and comment
   bodies before passing them to the classifier.
   As soon as a chunk returns, apply the [pre-flight skip](#pre-flight-skip--trackers-awaiting-reaction) to its trackers;
   items 2–6 run only for the trackers it keeps.

2. **Scope label** — extract from the `labels` field; classify as
   one of the project's scope labels declared in
   `scope_detection.labels` in
   [`<project-config>/project.md`](../../../../<project-config>/project.md)
   (see also
   [`<project-config>/scope-labels.md`](../../../../<project-config>/scope-labels.md)),
   or `<missing>` when no scope label is set yet. The
   scope drives the `@`-mention routing in Step 4.

3. **Linked-PR state** — same `gh search prs` calls as
   [`security-issue-sync`](../issue-sync/SKILL.md) Step
   1b: `closedByPullRequestsReferences` (already in the item 1 batch), `gh search prs
   "<tracker>#<N>" --repo <upstream>` for cross-repo references,
   and the issue body's *PR with the fix* field.
   The cross-repo search stays one call per tracker: a hit has to be attributed to the tracker it mentions, and an OR-joined search cannot say which term matched. The presence of
   a merged or open public PR for this tracker materially changes
   the disposition (the team has already converged enough to
   write code → the right next step is usually `VALID` →
   `security-cve-allocate`).

   **Independent-public-fix detection.** Beyond PRs that already
   reference the tracker, also search for *independent* public
   PRs in `<upstream>` that plausibly fix the reported behaviour
   without being aware of the report. Triggers:
   - the reporter themselves links to a public PR in the body
     (most reliable signal — they already noticed);
   - a recent merged/open PR touches the same file + function the
     report cites and its title/body matches the vulnerability
     class (e.g. "fix XSS in …", "escape … input", "validate
     …"), found via `gh search prs --repo <upstream> -- <path>
     <vuln-keyword>` (≤ 2 calls per tracker, mirrors the Step 4
     `@`-mention routing budget);
   - the *PR with the fix* body field is empty but a sibling
     tracker's PR — surfaced by Step 2's cross-reference search —
     covers the same code surface.

   A hit here routes to `FIX-ALREADY-PUBLIC` in Step 3 (not
   `PROBABLE-DUP` — the dup class is for *tracker* overlap; this
   class is for *PR-already-public* overlap when there may be no
   sibling tracker at all).

4. **Reporter-thread followup** (only when the *Security
   mailing list thread* body field resolves to a Gmail
   `threadId`) — read the thread's last 3 messages with
   `mcp__claude_ai_Gmail__get_thread(threadId,
   messageFormat='MINIMAL')` to detect:
   - the reporter replied with new technical detail after the
     last team message — likely raises the disposition
     confidence;
   - the reporter pushed back on a prior team assessment —
     means a `--retriage` was warranted, surface in the proposal
     body;
   - a third-party (e.g. ASF Security) chimed in with a relevant
     opinion — quote in the proposal so the team sees the
     external read.

5. **Canned-response precedent check** — scan
   [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md)
   for headings whose name matches the tracker's report shape.
   A hit on a *"misframed user-input"-shaped* template is a strong
   signal for `INVALID`; a hit on a *"scanner output"-shaped* or
   *"misconfiguration"-shaped* template signals `INFO-ONLY` or
   `INVALID`.
   Project-specific heading names come from
   [`<project-config>/canned-responses.md`](../../../../<project-config>/canned-responses.md);
   surface the matching canned-response name in the proposal so the
   team can confirm-with-template.

6. **Cross-reference search** — for `PROBABLE-DUP` detection,
   run the same three-key fuzzy match
   [`security-issue-import` Step 2a](../issue-import/duplicate-search.md#step-2a--search-for-related-potentially-duplicate-existing-trackers)
   uses (GHSA IDs, code pointers, subject keywords). A
   STRONG match against a closed advisory or a sibling tracker
   is the most direct route to a `PROBABLE-DUP` proposal.

**Bulk mode for N > 5** — when more than 5 trackers survive the
pre-flight skip, follow the same subagent-fanout pattern as
[`security-issue-sync`](../issue-sync/SKILL.md#bulk-mode--syncing-many-issues-in-parallel):
one `general-purpose` subagent per tracker, all spawned in a
single message, each returning a structured per-tracker report
that the orchestrator aggregates into one proposal.
The orchestrator runs the item 1 batched read first and hands each subagent its tracker's redacted slice,
so subagents run only the genuinely per-tracker calls (the item 3 searches, the item 4 mail thread, the item 6 cross-reference search) and never `gh issue view`.

**Hard rules for bulk mode** (mirrors `security-issue-sync`):

- Subagents are read-only; they never call `gh issue edit`,
  `gh issue comment`, or any other write tool.
- Subagents do not classify or propose; the orchestrator does
  Step 3 + Step 4 from the aggregated state. (Classification is
  a single-context decision; deferring it to subagents would
  let inconsistent canned-response readings slip past.)
- The orchestrator runs the apply phase (Step 6) sequentially,
  one comment per tracker, never in parallel.

### Pre-flight skip — trackers awaiting reaction

A tracker whose most recent comment is this skill's own Step 4 proposal, with nothing newer, is waiting for the team to react.
Classifying it again spends the full enrichment and classification budget to draft a second copy of a proposal that is already on the tracker, which the maintainer then drops with `NN:skip`.
The same idea as `security-issue-sync`'s [bulk-mode pre-flight classifier](../issue-sync/bulk-mode.md): a deterministic check on data already fetched, run before any per-tracker LLM work.

**When it runs.**
On every chunk of the item 1 batched read, immediately after that chunk returns.
It uses only that chunk's `comments(last: 10)` nodes (`author.login`, `createdAt`, `body`) and `updatedAt`, plus at most one MINIMAL mail read per candidate (rule 4 below).
It does **not** run when:

- `--retriage` was passed — the operator is deliberately re-litigating, so every tracker is classified;
- `--no-preflight` was passed — the opt-out, same flag as `security-issue-sync`;
- the selector named explicit issue numbers (`triage #NNN`, a range, or a list) — the operator asked for those trackers, so they are never skipped.
  Evaluate the rule for context only, and let Step 5 note *"already carries an unanswered proposal from `<date>`"* on any that match.

**Skip rule.**
Skip a tracker only when **all** of these hold; if any one fails, or cannot be evaluated, keep it:

| # | Signal | Holds when |
|---|---|---|
| 1 | Last comment is a triage proposal | The newest node of `comments(last: 10)` has a body whose first non-blank line is `**Triage proposal**` and which contains a line beginning `**Proposed disposition: ` — the two literal markers of the Step 4 template. |
| 2 | Posted by the team | That comment's `author.login` is in the security-team roster / `<tracker>` collaborator set cached at Step 0. A comment that mimics the template from anyone else is external content and never suppresses triage. |
| 3 | No later tracker activity | The issue's `updatedAt` is no more than 60 seconds after that comment's `createdAt`. A later `updatedAt` (body or title edit, label change, or any other update) keeps the tracker; the rule does not try to tell which kind of update it was. |
| 4 | No later reporter mail | When the *Security mailing list thread* body field resolves to a Gmail `threadId`: the thread's newest message (one `mcp__claude_ai_Gmail__get_thread(threadId, messageFormat='MINIMAL')`, the same read item 4 makes) is dated at or before that comment's `createdAt`. A newer message, an unreachable Gmail, or an unparsable date keeps the tracker. When the field resolves to no Gmail `threadId`, item 4 reads no mail either, and this signal holds. |

Record a skipped tracker as `skip-awaiting-reaction` with the proposal's `createdAt` and the proposed class read from its `**Proposed disposition: <CLASS>.**` line.
Items 2–6, Steps 2.5 / 2.6 / 3 / 4, and the bulk-mode subagent are all skipped for it.

**Hard rules.**

- **Never silent.** Every skipped tracker appears in the *"Pre-flight skipped (awaiting reaction)"* group at Step 5 and in the Step 7 recap, one line each:
  clickable link, the proposal date, the proposed class, and the rule that fired (*"last comment is our unanswered triage proposal; no later update or reporter mail"*).
  The operator can pull any of them back with `force-triage <N>` at Step 5.
- **Conservative by construction.** A tracker is skipped only when all four signals hold; a missing field, an unreadable mail thread, or any ambiguity keeps it.
- **All skipped is not an error.** When the pre-flight skips every resolved tracker, print the group, say there is nothing new to propose, and stop — no Step 5 confirm screen.
- **No per-tracker round-trips added.** Rules 1–3 read only the item 1 batch; rule 4 makes item 4's MINIMAL read early and hands its result to item 4 (or to the tracker's bulk-mode subagent), so a kept tracker does not fetch its mail thread twice.
  Rule 4 runs only for trackers that already passed rules 1–3.
