<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr eval suite

13 cases across 4 steps.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step 2 — detect scope from changed files | `step-2-scope-detection/` | 5 | Single provider, chart, airflow-core, mixed-scope blocker, multi-provider |
| Step 3 — propose milestone | `step-3-milestone/` | 3 | Airflow scope with PR milestone, providers scope ignoring PR milestone, no milestone ask |
| Step 6 — confirmation | `step-6-confirm/` | 3 | `go`, title override, `cancel`/`hold off` |
| Step 8 — recap and hand-off | `step-8-recap/` | 2 | Merged PR, open PR |

## Hard rules exercised

- **Step 2** — Test files (`*/tests/**`) are stripped before scope mapping. A PR that only touches test files alongside production files in one scope must not be miscounted.
- **Step 2** — Mixed-scope PRs (production files in more than one scope) are a **hard stop** (`stop: true`). The skill must surface the blocker message and not create a tracker.
- **Step 2** — Multiple providers in one PR (e.g. `providers/amazon/` and `providers/google/`) remain a **single** `providers` scope but the `affected_providers` list carries both names. This is not a mixed-scope error.
- **Step 3** — For `providers` scope, the PR's own milestone is **always wrong** and must be ignored. The correct signal is the next `Providers YYYY-MM-DD` wave from `release-trains.md`.
- **Step 3** — For `airflow`/`chart` scope with no PR milestone, the skill must **ask the user** rather than inventing a milestone.
- **Step 6** — `hold off` is treated as `cancel` (synonymous with `none`). No tracker is created.
- **Step 6** — A `title: <text>` reply must apply only the title override; all other proposal fields remain as-is.
- **Step 8** — All tracker and rollup references must be full URLs; bare `#NNN` is a formatting violation.

## Steps not covered

Steps 0–1 (pre-flight, PR fetch), 4 (duplicate guard), 5 (body construction), and 7 (apply) are procedural steps with shell commands and API calls that are better covered by integration tests. Step 4 closely mirrors the duplicate guard in `security-issue-import-from-md` already evaluated there.
