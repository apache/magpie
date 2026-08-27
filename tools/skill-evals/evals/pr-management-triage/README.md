<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pr-management-triage evals

Behavioral evals for the `pr-management-triage` skill.

## Suites (39 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| pre-filter | Step 2 (pre-filters) | 10 | F1 (collaborator), F2 (bot), F3 (draft recent), F4 (already ready), F5a (active maintainer comment), F5b (maintainer ping unanswered), F6 (maintainer co-drafted), row-6 (viewer is author), row-7a (fresh PR); clean contributor continues |
| decision-table | Step 2 (decision table) | 18 | Rows 3/4 (already-triaged via body-fold block→skip), 7b (security signal), 9 (conflict→draft), 10 (all systemic→rerun), 11 (partial systemic→rerun), 12 (static-only→comment), 13 (flaky ≤2→rerun), 14a (author confirmed→mark-ready), 14b (pending confirmation→skip), 14c (threads addressed→request-author-confirmation), 15 (threads→ping), 16 (no CI→rebase), 18 (changes-requested+new-commits→ping), 19 (already ready→skip), 20 (passing→mark-ready), 21 (stale draft sweep→close), 22 (rollup anomaly→skip) |
| terminal-links | Golden rule 10 | 5 | Short, context-short, and full PR references use the canonical target; `NO_COLOR` and `TERM=dumb` select the plain-text fallback |
| pagination-dedup | Step 1 (full pagination) | 2 | A PR that moves to a later page is emitted once at its freshest occurrence; distinct PRs keep their fetched order |
| interaction-progress | Interaction loop | 4 | Per-PR drill-ins retain the original one-based group position at the first, middle, and last rows and show the active classify-to-propose transition for `[E]` and `[P]` entry |

The two body-fold cases (`case-17-fold-already-triaged`,
`case-18-fold-stale-after-push`) are the regression guard for the denoise
change: triage feedback folded into the PR body must be recognised as a
triage marker so a freshly-folded PR is skipped (not re-flagged every
sweep), while a fold whose `head=` no longer matches the current head
(the author pushed since) is treated as stale and the PR is re-classified.

## Run

```bash
# All cases
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/

# Single suite
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/pre-filter/fixtures/

# Single case
uv run --project tools/skill-evals skill-eval \
    tools/skill-evals/evals/pr-management-triage/decision-table/fixtures/case-16-rollup-anomaly
```
