<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Fix N+1 query in serialized dag load

Body:
The serialized-dag loader issued one query per dag. This batches them into a
single IN query, cutting scheduler load time on large deployments.
Closes https://github.com/apache/airflow/issues/65934

Commits (opened by single account alice, authored by alice):
- 13:00 alice  "Batch serialized dag query to avoid N+1"
- 13:20 alice  "Add regression test for batched load"

Changed files:
- airflow/core/serde.py
- tests/core/test_serde.py

Labels: area:scheduler

CI status checks: Airflow CI / tests (success), Airflow CI / static-checks (success).
