<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Title: Batch serialized dag query to avoid N+1 in the scheduler

Body:
The serialized-dag loader issued one query per dag, which dominates scheduler
loop time on large deployments. This batches them into a single IN query and
adds a regression test. Our team developed it on our company fork and merged
the pieces internally for review before sending it upstream.
Closes https://github.com/apache/airflow/issues/65934

Commits (PR opened by single account acme-eng):
- 09:00 alice  "Merge pull request #5 from acme/serde-batch"
- 09:18 alice  "Merge pull request #6 from acme/serde-test"
- 09:34 alice  "Merge pull request #7 from acme/serde-docs"
- 09:36 bob    "Batch the serialized dag query into a single IN lookup"
- 09:38 carol  "Add regression test for batched serialized-dag load"

Changed files:
- airflow/core/serde.py
- tests/core/test_serde.py

Labels: area:scheduler

CI status checks: Airflow CI / tests (success), Airflow CI / static-checks (success).
