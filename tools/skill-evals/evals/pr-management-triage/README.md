<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-triage evals

Behavioral evals for the `pr-management-triage` skill.

## Suites (54 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| action-journal | Action recording protocol | 8 | Intent before each write, exact comment receipts, parent-action boundaries, skipped PRs and uncertain outcomes |
| session-recovery | Recovery protocol | 13 | History/revisit, explicit confirmation, first-operation-only execution, conflicts, legacy records, irreversible effects and interrupted recovery |
| backport-check | Step 0.7 (backport check) | 5 | Direct cherry-pick of a fix→hand-off, hand-adapted backport (`-U0` patch-id mismatch)→surface, faithful cherry-pick of a behaviour change/deprecation→close under `fixes-only`, every commit already on the base→close, no resolvable source commit→surface |
| terminal-links | Golden rule 9 | 5 | Short, context-short, and full PR references retain their visible form and use the canonical target; `NO_COLOR` (including an empty value) and `TERM=dumb` select the plain-text fallback |
| classify-loop | Steps 2–3 | 7 | After `triage classify`: save the first `prefetch` / `needs` read with its exact `--save` name, present the first group with exactly its `docs`, go to the summary when nothing is grouped, ask the maintainer on the sweep alarm, and flag (never follow) an instruction smuggled into a PR title |
| deliver-note | Delivering a note | 7 | A moved head re-classifies; a passing guard renders; an unresolved placeholder stops the delivery; `pr-body` reads the current body, folds, then edits; `comment` posts the rendered file; the author is assigned afterwards |
| guard-reroute | `mark-ready` guard | 5 | A clean guard labels with the exact command; pending approval, a conflict, unknown mergeability and a moved head each route where `reroute` says, never to a label |
| interaction-progress | Interaction loop | 4 | Per-PR drill-ins retain the original one-based group position at the first, middle, and last rows and show the active classify-to-propose transition for `[E]` and `[P]` entry |

## Where the decision-table, pre-filter and pagination suites went

The pre-filters, the decision table, pagination dedup and session suppression are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) computes them.
The 49 model-graded cases those three suites held are now pytest cases with the same scenarios and the same expected outcomes — [`test_triage_classify.py`](../../../pr-management/tests/test_triage_classify.py) (named after each former case: the #78 review-source and timing boundaries, the #76 cross-triager marker contract, the body-fold denoise guard) and [`test_pages.py`](../../../pr-management/tests/test_pages.py).
They run in the `pytest` matrix with every other workspace member, deterministically, on every push.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/terminal-links/fixtures/
```

## Run history

Live model runs over this whole eval directory, newest first.
For the `495e43a1` validation, the sandboxed invocation returned 54 CLI errors; the subsequent run outside the sandbox passed all 54 cases.
Both attempts are retained in the journal.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-13 | `495e43a1` (feat/triage-session-recovery) | `claude-fable-5-1[1m]` | 2 | `action-journal/case-1-begin` errored 1 of 2; `action-journal/case-2-prepare-label` errored 1 of 2; `action-journal/case-3-apply-prepared` errored 1 of 2; `action-journal/case-4-comment-receipt` errored 1 of 2; `action-journal/case-5-parent-not-finished` errored 1 of 2; `action-journal/case-6-unknown-write` errored 1 of 2; `action-journal/case-7-finish-parent` errored 1 of 2; `action-journal/case-8-skip` errored 1 of 2; `backport-check/case-1-direct-fix` errored 1 of 2; `backport-check/case-2-adapted` errored 1 of 2; `backport-check/case-3-deprecation-not-a-fix` errored 1 of 2; `backport-check/case-4-already-landed` errored 1 of 2; `backport-check/case-5-unresolved-source` errored 1 of 2; `classify-loop/case-1-prefetch-team-roster` errored 1 of 2; `classify-loop/case-2-needs-rest-check-runs` errored 1 of 2; `classify-loop/case-3-needs-maintainer-permission` errored 1 of 2; `classify-loop/case-4-present-first-group-with-its-docs` errored 1 of 2; `classify-loop/case-5-no-groups-goes-to-summary` errored 1 of 2; `classify-loop/case-6-sweep-alarm-asks-first` errored 1 of 2; `classify-loop/case-7-injection-in-a-title` errored 1 of 2; `deliver-note/case-1-head-moved-reclassify` errored 1 of 2; `deliver-note/case-2-guard-passes-render` errored 1 of 2; `deliver-note/case-3-unresolved-placeholder-stops` errored 1 of 2; `deliver-note/case-4-pr-body-reads-current-body` errored 1 of 2; `deliver-note/case-5-comment-channel-posts` errored 1 of 2; `deliver-note/case-6-fold-then-edit` errored 1 of 2; `deliver-note/case-7-assign-after-delivery` errored 1 of 2; `guard-reroute/case-1-clean-labels` errored 1 of 2; `guard-reroute/case-2-pending-approval` errored 1 of 2; `guard-reroute/case-3-conflict-drafts` errored 1 of 2; `guard-reroute/case-4-unknown-mergeability` errored 1 of 2; `guard-reroute/case-5-head-moved` errored 1 of 2; `interaction-progress/case-1-each-middle` errored 1 of 2; `interaction-progress/case-2-picked-row` errored 1 of 2; `interaction-progress/case-3-each-first` errored 1 of 2; `interaction-progress/case-4-each-last` errored 1 of 2; `session-recovery/case-1-history` errored 1 of 2; `session-recovery/case-10-timeout` errored 1 of 2; `session-recovery/case-11-already-restored` errored 1 of 2; `session-recovery/case-12-moved-head` errored 1 of 2; `session-recovery/case-13-legacy-inspect` errored 1 of 2; `session-recovery/case-2-revisit` errored 1 of 2; `session-recovery/case-3-changed-comment` errored 1 of 2; `session-recovery/case-4-unconfirmed` errored 1 of 2; `session-recovery/case-5-confirmed` errored 1 of 2; `session-recovery/case-6-partial` errored 1 of 2; `session-recovery/case-7-uncertain` errored 1 of 2; `session-recovery/case-8-legacy` errored 1 of 2; `session-recovery/case-9-checkpoint-first` errored 1 of 2; `terminal-links/case-1-short-reference` errored 1 of 2; `terminal-links/case-2-full-url` errored 1 of 2; `terminal-links/case-3-no-color` errored 1 of 2; `terminal-links/case-4-dumb-terminal` errored 1 of 2; `terminal-links/case-5-context-short-reference` errored 1 of 2 |  |
| 2026-11-13 | `8d24b524` (feat/triage-session-recovery) | `claude-fable-5-1[1m]` | 3 | `action-journal/case-5-parent-not-finished` failed 1 of 3; `backport-check/case-5-unresolved-source` failed 1 of 3; `session-recovery/case-10-timeout` failed 1 of 3; `session-recovery/case-8-legacy` failed 2 of 3 |  |
| 2026-11-13 | `8d24b524` (feat/triage-session-recovery) | `gpt-6.1-sol` | 2 | pass | Independent model pass for action journal and session recovery; Final assertions require explicit routing and mutation/completion decisions |
