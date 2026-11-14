<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Tracker

Issue: [example-s/example-s#250](https://github.com/example-s/example-s/issues/250)
Title: "HTTP provider writes connection credentials to task logs"
Scope label: providers

### Step 3 classification result

```json
{
  "disposition": "PROBABLE-DUP",
  "rationale": "The same Authorization-header logging statement in providers/http/ is already tracked in issue 212. The reports share the same root cause and fix.",
  "kept_tracker": 212
}
```

Candidate kept tracker: [example-s/example-s#212](https://github.com/example-s/example-s/issues/212).
Both trackers are open and neither has a CVE.

### Security Model verbatim quote

Section: "Airflow Security Model — About Sensitive information"
URL: https://airflow.apache.org/docs/apache-airflow/stable/security/security_model.html#about-sensitive-information

Mock quote to include verbatim (2-3 sentences):
"Authenticated users can see the logs of all task instances they have
access to. Logs may contain sensitive information depending on the tasks
being run, but credentials configured in Connections are not expected to
appear in plain text in task logs."

### @-mention routing

PR-author match: @alice (most recent fix in providers/http/).
Reviewer match: @bob (last reviewed changes to the same logging statement).
Triager (exclude): @carol.
