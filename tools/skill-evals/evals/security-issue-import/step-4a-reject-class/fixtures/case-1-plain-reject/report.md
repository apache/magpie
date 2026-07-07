<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Reject-pattern taxonomy (from canned-responses.md)

| Pattern (heading verbatim) | When it applies |
|---|---|
| When someone claims Dag author-provided "user input" is dangerous | Report frames "user input" as untrusted, but the role controlling the input is the Dag author. Dag authors already have arbitrary code execution on the worker, so a Dag author reaching a code/SQL sink is not a privilege-boundary crossing. |
| DoS issues triggered by Authenticated users | Resource-exhaustion / hang triggered by an already-authenticated user. Out of scope unless the impact escapes the documented authenticated-user trust boundary. |
| Image scan results | Third-party dependency CVE reported against the Docker image, with no Airflow-specific reachability or amplification. Out of scope per the Security Model. |

### Candidate report (extracted body)

Subject: SQL injection in PostgresOperator via DAG-defined variable

I found that a DAG author can pass an unsanitised string into
`PostgresOperator(sql=...)` by building it from a `Variable.get()` call, and
the value is interpolated straight into the SQL sent to the database. A
malicious DAG author could run arbitrary SQL. Reproduction: write a DAG that
reads a Variable and concatenates it into the `sql` argument.

Reporter's claimed impact: arbitrary SQL execution by whoever authors the DAG.
No mention of any non-DAG-author role reaching the `sql` argument.
