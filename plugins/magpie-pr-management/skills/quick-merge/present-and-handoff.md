<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Step 3 — Rank and present

Order within each bucket: **Tier A before Tier B; within a tier, smallest churn
first; ties broken by oldest-updated.** Present **two** read-only buckets — the
*ready-to-merge* set first, then the *needs-your-approval-then-merge* set:

```text
─────────────────────────────────────────────────────
Quick-merge candidates · all gates green · review & act yourself
─────────────────────────────────────────────────────

READY TO MERGE — M PRs (clean / mergeable now)
 [A] #67452  @nailo2c       +12/-1   1 file   Tier A (docs)   mergeable_state: clean
       airflow-core/docs/core-concepts/dags.rst
       gates: CI ✓ (Tests, Static checks, Docs)  threads 0  approvals: 1
       merge:  gh pr merge 67452 --squash --repo <repo>
       [V] view full diff

NEEDS YOUR APPROVAL, THEN MERGE — K PRs (clean branch, blocked on a missing committer approval)
 [A] #64724  @auyua9        +2/-2    1 file   Tier A (docs)   mergeable_state: blocked (REVIEW_REQUIRED)
       INSTALLING.md
       gates: CI ✓  threads 0  approvals: 0
       action:  [A]pprove 64724  →  then  gh pr merge 64724 --squash --repo <repo>
       [V] view full diff
 ...
```

For each candidate print: PR number (clickable), author, `+adds/-dels`, file
count, tier + one-word reason, the live `mergeable_state`, the **full file
list**, an explicit per-gate attestation (which real-CI checks are green,
unresolved-thread count, current approval count), and a `[V]iew diff` affordance.
For the *ready* bucket print the **merge command**; for the *needs-approval*
bucket print the `[A]pprove NN` → merge sequence.

The maintainer's options on the group:

- `[V]NN` — fetch and show the full diff for PR `NN` (lazy `gh pr diff`). **Read-only.**
- `[A]pprove NN` — submit an APPROVE review on PR `NN` as the maintainer (see
  [Step 3b](#step-3b--optional-approve-action)). **The only mutation; per-PR, confirmed.**
- `[O]pen NN` — print the PR URL to open in a browser. **Read-only.**
- `[D]one` / `[Q]uit` — finish; print the session summary.

There is **no** `[A]ll`, no `[M]erge`, no per-PR merge key, and approve is never
batched. The skill stops short of merging; the maintainer copies the printed
merge command (or opens the PR) and merges in their own session, having read the
diff. That is the line Golden rule 1 draws.

### Approval reminder

For each candidate, print its current approval count and whether `<repo>`'s
branch protection requires an approving review. If a candidate has zero
approvals and the repo requires one, note inline: *"no approval yet — `[A]pprove
NN` to add yours, then run the merge command"* so the maintainer sees both the
prerequisite and the in-skill way to clear it.

---

## Step 4 — Session summary

On exit, print:

- count of candidates surfaced, split by tier
- count of ready-queue PRs screened and the drop reasons (gate-red, too large,
  consequential-path, path-unmatched) so the maintainer can see *why* the
  non-candidates were excluded — the screen is auditable, not a black box
- the ready-queue total and what fraction was fast-track-eligible (a useful
  queue-health signal: a high trivial fraction means the deep-review queue is
  smaller than the raw count suggests)
- count of APPROVE reviews submitted this session (Step 3b), with PR numbers —
  the one mutation the skill makes, so it is always reported explicitly
- total wall-clock time

Approvals aside, the skill makes no mutations. (If a future Mode-D merge step is
ever added, *that* step — not this one — owns merge logging and any
session-history gist.)

---

## Step 5 — Hand the remainder to code-review

The PRs this skill *drops* are not noise — they are the deep-review queue. A
ready-for-review PR that failed the triviality screen — `too-large`, or a
`path-denied`/`path-unmatched` change in a consequential area — is exactly the
kind of substantive change that wants a real, line-level read. After the
candidate group, surface the handoff:

- Report the count of ready-queue PRs that are **not** quick-merge candidates,
  split by [drop reason](candidate-rules.md#drop-reason-taxonomy), and name the
  `too-large` / `path-*` ones (the "so-close" and substantive PRs) with
  clickable links.
- Recommend the family's review skill for them, with the exact invocation:
  *"N ready PRs need a full read — run
  [`pr-management-code-review`](../code-review/SKILL.md), or
  `pr-management-code-review pr:<N>` for a single one."*

This is a **pointer, not an auto-invocation** — the same maintainer-fires
principle as everywhere else; the skill does not launch another skill. The two
compose cleanly: quick-merge skims the trivial top of the `ready` queue,
[`pr-management-code-review`](../code-review/SKILL.md) does the
line-level read of the substantive remainder, and
[`pr-management-triage`](../pr-triage/SKILL.md) is what fills the
queue in the first place. Together they drain it from both ends.
