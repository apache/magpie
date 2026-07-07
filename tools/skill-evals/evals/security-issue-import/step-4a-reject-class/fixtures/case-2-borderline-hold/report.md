<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Reject-pattern taxonomy (from canned-responses.md)

| Pattern (heading verbatim) | When it applies |
|---|---|
| When someone claims Dag author-provided "user input" is dangerous | Report frames "user input" as untrusted, but the role controlling the input is the Dag author. Dag authors already have arbitrary code execution on the worker, so a Dag author reaching a code/SQL sink is not a privilege-boundary crossing. |
| DoS issues triggered by Authenticated users | Resource-exhaustion / hang triggered by an already-authenticated user. Out of scope unless the impact escapes the documented authenticated-user trust boundary. |
| Image scan results | Third-party dependency CVE reported against the Docker image, with no Airflow-specific reachability or amplification. Out of scope per the Security Model. |

### Candidate report (extracted body)

Subject: SQL injection reaching PostgresOperator from a REST API trigger field

This looks similar to the usual "DAG author controls the SQL" cases, but the
sink is reached differently. The DAG template renders `{{ dag_run.conf['q'] }}`
straight into the `sql` argument, and `dag_run.conf` is populated from the
**REST API trigger endpoint**, which a user holding only the *can_create
DagRun* permission (a non-author role in our deployment) can call. So a user
who cannot author DAGs can still inject SQL by triggering an existing DAG with
a crafted conf payload.

I have not fully confirmed which roles can hit the trigger endpoint in a
default install, but in ours a low-privilege operator role can.
