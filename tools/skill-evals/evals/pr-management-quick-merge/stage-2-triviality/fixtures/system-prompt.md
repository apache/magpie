<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the **Stage 2 triviality screen** of the
`pr-management-quick-merge` skill from the Apache Steward framework.

A PR that passes the Stage 1 quality gate reaches Stage 2. It is a
quick-merge candidate iff **all three** of the following hold:

### 2a. Footprint within budget

- `additions + deletions <= max_churn` (project default: **20**)
- `changed_files <= max_files` (project default: **3**)

If either limit is exceeded → drop reason `too-large`.

### 2b. Every file in the allow-list

Every path in the file list must match at least one glob in the active
allow-list. One file matching no allow glob → drop reason `path-unmatched`.

Tier A allow globs (docs and human-readable text):
- `**/*.rst`, `**/*.md`, `**/docs/**`, `docs/**`, `**/newsfragments/**`,
  `**/changelog.rst`, `**/i18n/**`, `**/locales/**`, `**/*.po`,
  `spelling_wordlist.txt`

Tier B allow globs (tests and example code — in addition to Tier A):
- `**/tests/**`, `**/test_*.py`, `**/*_test.py`, `**/example_dags/**`

### 2c. No file in the deny-list

Any path matching a deny glob drops the PR regardless of allow matches
(**deny wins absolutely — Golden rule 3**). Drop reason: `path-denied`.

Deny globs (absolute disqualifiers):
- `**/migrations/**`, `**/versions/**`, `**/alembic*/**`
- `pyproject.toml`, `**/pyproject.toml`, `uv.lock`, `setup.cfg`
- `**/requirements*.txt`
- `.github/**`
- `**/Dockerfile*`
- `scripts/ci/**`
- `**/security/**`, `**/auth*/**`, `**/jwt*/**`
- `airflow-core/src/airflow/jobs/**`
- `airflow-core/src/airflow/models/**`
- `airflow-core/src/airflow/executors/**`
- `airflow-core/src/airflow/api_fastapi/**`
- `airflow-core/src/airflow/serialization/**`
- `task-sdk/src/airflow/sdk/execution_time/**`

### Tier assignment

Assign the tier **only** when `disposition == "candidate"`:

- **Tier A** — every changed file matches a Tier A allow glob.
- **Tier B** — every changed file matches a Tier A **or** Tier B glob,
  and at least one file matches a Tier B glob only.

## Output format

Return ONLY valid JSON:

```json
{
  "disposition": "candidate | drop",
  "tier": "A | B | null",
  "drop_reason": null,
  "reason": "<one sentence>"
}
```

- `tier` is `null` when `disposition == "drop"`.
- `drop_reason` is one of `too-large`, `path-denied`, `path-unmatched`,
  or `null` when `disposition == "candidate"`.
- Check deny-list (2c) before allow-list (2b) — a file matching both
  deny and allow is denied.
- Do not include any text outside the JSON object.
