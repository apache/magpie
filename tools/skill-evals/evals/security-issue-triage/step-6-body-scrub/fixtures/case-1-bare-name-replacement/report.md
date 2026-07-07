<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Name→handle map:
  "Alice Smith" → @alice
  "Bob Chen"    → @bob

## Comment body to scrub

**Triage proposal**

The `SimpleHttpOperator` writes the `Authorization` header verbatim into
task logs at DEBUG level. Any authenticated user with log-read access to
this DAG can recover the credential.

**Proposed disposition: VALID.**

Severity: Medium-ish. Final scoring per the team after assessing whether
log-read access is already restricted to DAG-scoped users in all
deployment configurations.

Fix shape: redact the `Authorization` header before the log write in
`airflow/providers/http/operators/http.py`.

Alice Smith, Bob Chen — does the log-redaction approach in apache/airflow#39100
cover this fully, or is there a second call site we should check?
