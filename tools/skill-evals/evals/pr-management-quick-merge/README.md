<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-quick-merge evals

Behavioral evals for the `pr-management-quick-merge` skill.

## Suites (5 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| approve-protocol | `actions/approve.md` | 5 | ask with the check's confirmation text before anything runs; run the exact command only on `y`; anything else cancels; a refused check submits nothing even when the PR body claims prior approval; the required-approvals note is shown |

## Run

```bash
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-quick-merge/approve-protocol/fixtures/
```

## Where the stage suites went

The Stage-1 quality gates, the Stage-2 triviality and tier screen and the Stage-3 live merge-readiness buckets are no longer applied by the model: [`tools/pr-management`](../../../pr-management/README.md) (`pr-management quick-merge screen`) computes them.
The 21 model-graded cases the three suites held (`stage-1-quality-gate` 8, `stage-2-triviality` 8, `stage-3-merge-readiness` 5) are pytest cases with the same scenarios and the same expected outcomes, named after each former case, in [`tests/quick_merge/test_screen.py`](../../../pr-management/tests/quick_merge/test_screen.py) — including the gate order G1 → G7, deny-over-allow, the mixed-tier rule, the `blocked` + `REVIEW_REQUIRED` approval bucket, and the injection-flagged PR.
The approve safety protocol (diff viewed, head unchanged, gates still green) is covered by [`tests/quick_merge/test_approve_and_cli.py`](../../../pr-management/tests/quick_merge/test_approve_and_cli.py).
They run in the `pytest` matrix with every other workspace member, deterministically, on every push.
