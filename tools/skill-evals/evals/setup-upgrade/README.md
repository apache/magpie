<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup-upgrade evals

Behavioral evals for the `setup-upgrade` skill.

## Suites (28 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-plan | ## Plan | 14 | mixed groups and bypass marking, hard lines to run-yourself, nothing to do, local-only script lines, linked worktree, non-Claude harness, isolated setup unknown vs absent, settings targets, stale shipped copy vs local edits, no history to compare, per-step install routing, shallow clone, personal layer not created yet |
| step-apply | ## Apply | 4 | drop applies the rest, changed-since-gathering skip, Check findings go to a second plan, one bypassed call per item |
| step-gather | ## Gather | 5 | which catalogues the gather summary calls for: isolated setup unchanged, fingerprint changed, update due, opted out, and a checker copy too old to print the summary |
| pointer-routing | # setup-upgrade | 5 | which sibling a situation sends the agent to: none on a routine run, `isolated-setup.md` when the isolated state is unknown, `script-copies.md` for a differing script copy, `gather-fallbacks.md` with no checker copy or no configuration |

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-upgrade/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/setup-upgrade/step-plan/fixtures/
```

## Notes

- Every finding in a `report.md` states its slug, and `expected.json` uses those slugs, so the expected result is unambiguous.
- The harness sends only the named `SKILL.md` section plus `output-spec.md`.
  `## Plan` delegates classification to `plan-format.md` and `hard-lines.md`; the cases that depend on them also state the relevant facts in the findings.
- `step-plan` also includes `gather-fallbacks.md`, `isolated-setup.md` and `script-copies.md`, and `step-apply` includes `script-copies.md`: the conditional text those cases test moved there.
  `pointer-routing` proves the pointers that lead to them.
  Its mutation check, run when the suite was added: with the seven pointer lines deleted from `SKILL.md`, cases 2–5 failed and case 1 still passed.
- `step-plan/case-5-linked-worktree` pins the main checkout's personal layer path.
- `step-plan/case-7-isolated-unknown` and `case-8-no-isolated` pin "not known" versus "confirmed absent" for the isolated-setup offer; they also pin the output shape (a `[bypass]` *Check* item and no offer, versus the offer with no items).
- `step-apply/case-1-drop` reflects that `drop 2,5` applies the rest immediately, with no second round.
- `step-gather` is a pointer-only step: no sibling file is pasted in, and the output spec names no file, so a case passes only when the `## Gather` text itself routes the read.
  Its mutation check, run when the suite was added: with the *Isolated setup* row and its attention rule deleted, cases 2, 3 and 5 failed; with the unconditional pre-change Gather, case 1 failed.

## Run history

Live model runs over this whole eval directory, newest first.
Generated from [`runs.jsonl`](runs.jsonl) by `skill-eval-journal render`;
do not edit the table by hand.
Columns and rules: [Recording runs](../../README.md#recording-runs).

| Date | Ref | Model | Runs | Result | Notes |
|---|---|---|---|---|---|
| 2026-11-28 | `703eee33` (opt/upgrade-split) | `opus[1m]` | 1 | pass |  |
| 2026-11-24 | `520d3a07` (fix/preflight-session-version) | `opus[1m]` | 2 | pass |  |
| 2026-11-15 | `1087814b` (perf/upgrade-gather-reads) | `opus[1m]` | 2 | pass |  |
| 2026-11-15 | `062c72ed` (perf/optimize-setup-upgrade) | `opus[1m]` | 1 | pass |  |
| 2026-11-09 | `51e73a33` (upgrade-skill) | `opus[1m]` | 1 | pass |  |
| 2026-11-05 | `7b6e5bbd` (fix/isolated-configured-user-settings) | `opus[1m]` | 1 | pass |  |
