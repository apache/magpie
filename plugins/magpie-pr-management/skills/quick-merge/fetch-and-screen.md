<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Step 1 — Fetch the ready queue

Build the search query (oldest-updated first so the longest-waiting easy wins
surface at the top):

```text
is:pr is:open repo:<repo> label:"ready for maintainer review" sort:updated-asc
```

Walk every page with the family's batched query from
[`pr-management-triage/fetch-and-batch.md`](../pr-triage/fetch-and-batch.md),
**extended with the per-PR file list and churn totals** the triviality screen
needs:

```graphql
        additions
        deletions
        mergeStateStatus      # CLEAN / UNSTABLE / BLOCKED / DIRTY / UNKNOWN / BEHIND
        files(first: 100) { nodes { path additions deletions } }
```

`files(first: 100)` caps at 100 changed files — any PR with more than 100 files
is by definition not a quick-merge candidate, so the cap never truncates a real
candidate (a PR that hits it fails the `max_files` screen immediately). Keep the
inner `first:` arguments modest (lower the outer `$batchSize` to 15 if the
complexity ceiling trips — the `files` connection adds nodes).

Fetch the repo-scoped `action_required` workflow-run index once per session
(same REST call as
[`pr-management-triage/fetch-and-batch.md#mandatory-action_required-run-index-per-page`](../pr-triage/fetch-and-batch.md#mandatory-action_required-run-index-per-page))
— a PR with a run awaiting approval is **not** gate-green even if its rollup
reads SUCCESS.

Do not read full diffs in this step. The diff is fetched lazily only when the
maintainer asks for `[V]iew diff` on a specific candidate.

---

## Step 2 — Three-stage screen

Run every fetched PR through [`candidate-rules.md`](candidate-rules.md):

1. **Quality-gate gate** (hard pass/fail, from the batch) — drop any PR not green
   on every Stage-1 gate: real CI green, no failed/pending checks, no workflow
   approval pending, no unresolved collaborator threads, no outstanding
   changes-requested. Mergeability is **not** gated here beyond an early-drop of
   the obviously batch-`CONFLICTING`. No partial credit.
2. **Triviality classification** (from the batch) — of the survivors, keep those
   whose footprint is within `max_churn` / `max_files` **and** whose every file
   matches the allow-list with none in the deny-list. Assign Tier A or Tier B.
3. **Live merge-readiness** — for each survivor (now a handful), make **one REST
   call** (`GET /repos/<repo>/pulls/<N>`) to resolve `mergeable` +
   `mergeable_state` live, because the batched value is unreliable for a large
   `ready` queue. Bucket each as **ready-to-merge** (`clean`/`unstable`/`behind`),
   **needs-approval** (`blocked` — branch merges cleanly but a committer approval
   is missing; the skill's primary case), or **drop** (`dirty`/conflict, or still
   `unknown` this run). See [Stage 3](candidate-rules.md#stage-3--live-merge-readiness).

Stages 1–2 are a pure function of the Step-1 batch (no mutations, no prompts);
Stage 3 adds the small per-candidate re-poll. The output is two ranked lists:
**ready-to-merge** and **needs-approval-then-merge**.
