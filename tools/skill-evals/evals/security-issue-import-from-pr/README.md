<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-pr eval suite

8 cases across 3 steps.

## Steps covered

| Step | Directory | Cases | Notes |
|---|---|---|---|
| Step 3 — propose milestone | `step-3-milestone/` | 3 | Airflow scope with PR milestone, providers scope ignoring PR milestone, no milestone ask |
| Step 6 — confirmation | `step-6-confirm/` | 3 | `go`, title override, `cancel`/`hold off` |
| Step 8 — recap and hand-off | `step-8-recap/` | 2 | Merged PR, open PR |

## Where the scripted cases went

Step 2 (scope detection) is decided by [`tools/security-management`](../../../security-management/README.md)
(`security-management issue-import-from-pr scope`), not by the model.
The model-graded suite that covered it — `step-2-scope-detection`, five cases — is pytest cases with the same changed files and expected output,
named after each former case, in [`tests/test_issue_import_from_pr.py`](../../../security-management/tests/test_issue_import_from_pr.py):
test files are stripped before scope mapping, a mixed-scope PR is a hard stop (`stop: true`),
and several providers in one PR stay a single `providers` scope with each name in `affected_providers`.
The `step-8-recap` scenario is pinned there too, against `render-recap`; that suite stays a model eval.

## Hard rules exercised

- **Step 3** — For `providers` scope, the PR's own milestone is **always wrong** and must be ignored. The correct signal is the next `Providers YYYY-MM-DD` wave from `release-trains.md`.
- **Step 3** — For `airflow`/`chart` scope with no PR milestone, the skill must **ask the user** rather than inventing a milestone.
- **Step 6** — `hold off` is treated as `cancel` (synonymous with `none`). No tracker is created.
- **Step 6** — A `title: <text>` reply must apply only the title override; all other proposal fields remain as-is.
- **Step 8** — All tracker and rollup references must be full URLs; bare `#NNN` is a formatting violation.

## Steps not covered

Steps 0–1 (pre-flight, PR fetch), 4 (duplicate guard), 5 (body construction), and 7 (apply) are procedural steps with shell commands and API calls; the reference parsing, duplicate query, title, body, labels and rollup they rely on are pytest-tested in `tools/security-management`.
