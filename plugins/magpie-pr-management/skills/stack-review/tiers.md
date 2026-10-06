<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reading by tier (Step 4)

The ledger decides how much of each layer is read; this file says how to read it and how to report what was not read.

## What each tier means

| Tier | Source | What is read | What it can establish |
|---|---|---|---|
| A | `overlap`, `seams` hits, detector hits, `dir_outliers`, and `outliers` of mechanical layers | every listed hunk, in every layer it appears in — never cut by the budget | misplaced hunks, hand edits in mechanical layers, broken seams |
| B | layers with `plan: full` | the whole layer diff | everything a per-PR reviewer would notice on a first pass |
| C | layers with `plan: exemplar` | the Tier A hunks of the layer, one exemplar per repeated hunk shape, and the outliers the plan ranked within the layer's share of the budget (`outliers_planned` of `outliers`) | that the repeated rewrite is the intended one and that the sampled hand-written hunks hold; nothing about the unread hunks |
| D | layers with `plan: skip` | nothing | that the layer is generated output; its source change lives in another layer |

The plan is a function of the ledger, the per-layer limit (1,500 hand-written lines) and the budget, so two runs on the same heads read the same hunks; `stack_ledger.py hunks` prints them with new-side line numbers, and every note anchors to those numbers.
Generated and binary lines never count: a layer that regenerates a 2,000-line lock file next to a 20-line manifest change is a 20-line layer.

## Reading checklist

For each hunk, in this order of priority:

1. **Does it belong here?** Match the hunk against the layer's title, body and commit messages. A `requires-python` bump inside a *ruff fixes* layer, or a README line inside a *compat shims* layer, is a `wrong-layer` candidate; confirm by reading the layer whose purpose it matches, and check the commit bodies first — a placement a commit explains is not misplaced.
2. **Is it a hand edit in a tool's layer?** In a mechanical layer every outlier is suspect by construction: a one-line fix slipped into a 150-file codemod is exactly what the per-layer reviewer skims past.
3. **Does the seam hold?** For a `seams` hit, is the quoted line a real reference (import, call, attribute) or inert text?
4. **Is it above the floor?** When `floors.json` shows the floor moving in a later layer, does this hunk use a construct the floor declared at this layer's own head does not provide? Quote the line and the floor; that is the inferred `ordering` finding.
5. **Small incoherencies.** A stale comment, a typo, an old version string left next to a new one, a docstring that describes the removed behaviour. Record them; do not go looking for more than the planned hunks contain.

Record a note for every hunk that has something to say — not one per hunk read — as `k:<file>:<line> — <one sentence>` with its tier tag: `[A]`, `[B]` or `[C sampled]`.
Load the adopter's review-criteria sources (`<project-config>/pr-management-code-review-criteria.md`, via [`../code-review/criteria.md`](../code-review/criteria.md)) once before the first hunk, so a rule violation is recognised when it is read.
A note is a *finding* only when it is a rule violation under the project's criteria ([`../code-review/criteria.md`](../code-review/criteria.md)); quote the rule.
Everything else is an *observation*.

## Budget

`read-budget` (default 4,000 hand-written changed lines) caps the Tier B total; the per-layer limit (default 1,500) caps any single layer.
The ledger spends the budget on hand-written layers first and mechanical layers last, so a demotion lands where an exemplar loses least; what the full reads leave over is shared equally among the demoted hand-written layers as each one's `outlier_share`, and their outliers are ranked (source > config > test > docs, smallest first) and planned while they fit that share — Tier A and exemplars never count against it, and an oversize hunk is skipped rather than stopping the ranking; `plan_reason` records why each layer was demoted and the coverage table says the share and how many hunks were not read.
A *demoted* layer is any layer planned `exemplar`, whether the per-layer limit or the budget demoted it; `[D]eepen` at the report gate doubles both numbers (`--read-budget`, `--full-read-max-lines`) and re-runs Step 4 for the demoted layers only; offer it only when there is one.
Tier A is never cut by the budget; when it alone exceeds it, say so and read it anyway — a hunk the scripts flagged is the one that matters.
Every `file:line` in a note is re-checked at the named head before the report is shown (`git -C <clone> show refs/magpie-stack/<S>/<k>:<path> | sed -n '<a>,<b>p'`); a line that does not show the described code is re-anchored or the note dropped.

## Background readers

When more than three layers are planned `full`, read them in parallel with background subagents, one per layer, following the contract of [`../code-review/review-flow.md`](../code-review/review-flow.md#background-analysis-subagents):

- the prompt inlines the layer's title, body, commit messages, class histogram, declared floor and the hunks to read; subagents never call `gh` or `git`;
- the output is the per-layer notes in the format above, nothing else;
- subagents are read-only: no `Write`, no `Edit`, no posting, no nested agents.

Without an Agent tool, read the layers sequentially and record *read sequentially (no background readers)* in the coverage lines.
The parent folds the notes into the report and keeps the verdict decision for itself.

## Coverage wording

The coverage table from `stack_ledger.py render` is pasted into every report and every summary comment, followed by one sentence per cut:

- *Layer 2 (mechanical) was read by exemplar: 3 exemplars for 3 repeated shapes and all 6 outlier hunks; the remaining 80 hunks share a read shape.*
- *Layer 4 (hand-written) was read by exemplar: 9 overlap-file hunks and 12 exemplars outside the share, plus 8 of 65 outliers within its 38-line share; 124 hunks (2,250 of 2,718 lines) were not read.*
- *Every layer was read in full; nothing was cut.*
- *Chain, seam and floor checks were skipped (`no-fetch`).*

Forbidden phrasings for a Tier C or D layer: *reviewed*, *approved*, *looks good*, *no issues found*.
Allowed: *noticed while reading <n> hunks*, *the read exemplars match the title and commits*, *not a full review of this layer*.
