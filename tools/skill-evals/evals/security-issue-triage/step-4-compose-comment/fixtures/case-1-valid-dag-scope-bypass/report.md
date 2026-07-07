<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Tracker

Issue: [example-s/example-s#212](https://github.com/example-s/example-s/issues/212)
Title: "HTTP provider leaks Basic-Auth credentials into task logs"
Scope label: providers

### Step 3 classification result

```json
{
  "disposition": "VALID",
  "rationale": "The Authorization header value is written to task logs that are accessible to any user with DAG read permissions — not just the operator who configured the connection. This crosses the boundary documented in the Security Model: authenticated users with scoped permissions must not be able to read credentials belonging to a different DAG or connection scope."
}
```

### Security Model verbatim quote

Section: "Airflow Security Model — Authenticated users"
URL: https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html#authenticated-users

Quote to include verbatim (2-3 sentences):
"Authenticated users can see the logs of all task instances they have
access to. Logs may contain sensitive information depending on the tasks
being run, but credentials configured in Connections are not expected to
appear in plain text in task logs."

### @-mention routing

PR-author match: @alice (most recent fix: apache/airflow#39100 "Fix: redact
  secrets from HTTP operator logs", merged 2025-11-20)
Reviewer match: @bob (last reviewed apache/airflow PRs touching providers/http/,
  2026-03-15)
Triager (exclude): @carol
