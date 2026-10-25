<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-complete-upgrade evals

Behavioral evals for the `setup-complete-upgrade` skill.

## Suites (16 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-plan | ## Plan | 12 | mixed groups and bypass marking, hard lines to run-yourself, nothing to do, local-only script lines, linked worktree, non-Claude harness, isolated setup unknown vs absent, settings targets, stale shipped copy vs local edits, no history to compare, per-step install routing |
| step-apply | ## Apply | 4 | drop applies the rest, changed-since-gathering skip, Check findings go to a second plan, one bypassed call per item |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-complete-upgrade/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-complete-upgrade/step-plan/fixtures/
```

## Notes

- Every finding in a `report.md` states its slug, and `expected.json` uses those slugs, so the expected result is unambiguous.
- The harness sends only the named `SKILL.md` section plus `output-spec.md`.
  `## Plan` delegates classification to `plan-format.md` and `hard-lines.md`; the cases that depend on them also state the relevant facts in the findings.
- `step-plan/case-5-linked-worktree` pins the main checkout's personal layer path.
- `step-plan/case-7-isolated-unknown` and `case-8-no-isolated` pin "not known" versus "confirmed absent" for the isolated-setup offer; they also pin the output shape (a `[bypass]` *Check* item and no offer, versus the offer with no items).
- `step-apply/case-1-drop` reflects that `drop 2,5` applies the rest immediately, with no second round.
