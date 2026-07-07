<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### gh issue view 225

```json
{
  "number": 225,
  "title": "Unauthenticated access to /health endpoint exposes DAG count",
  "body": "The /health REST endpoint returns aggregate DAG and task statistics\nwithout requiring authentication. An external attacker can enumerate\napproximate DAG counts.\n\n**PR with the fix:** (none)\n\n**Security mailing list thread:** threadId=AAMkAGQ2KkB",
  "labels": [
    {"name": "needs triage"},
    {"name": "airflow"}
  ],
  "closedByPullRequestsReferences": [],
  "comments": [
    {
      "author": {"login": "security-team-member"},
      "body": "The /health endpoint intentionally exposes aggregate status. This matches our prior NOT-CVE-WORTHY call on #198."
    }
  ]
}
```

### gh search prs cross-repo

No results.

### Gmail thread (threadId=AAMkAGQ2KkB, last 3 messages)

```json
[
  {
    "from": "reporter@example.com",
    "date": "2026-05-03T10:00:00Z",
    "snippet": "I disagree with the NOT-CVE-WORTHY assessment. The DAG count is sensitive metadata..."
  },
  {
    "from": "security@airflow.apache.org",
    "date": "2026-05-04T09:15:00Z",
    "snippet": "The /health endpoint is documented as public. We stand by the prior call."
  },
  {
    "from": "reporter@example.com",
    "date": "2026-05-10T16:45:00Z",
    "snippet": "I have now found that the response also includes the Airflow version string, which aids fingerprinting for CVE targeting. This is a new finding not previously discussed."
  }
]
```

Last message is from the reporter with a substantive new technical claim
(version fingerprinting) not covered in the prior team assessment.

### Canned-response scan

No match found.

### Cross-reference search

STRONG match: issue #198 (closed as NOT-CVE-WORTHY 2026-01-15).
Same code surface: /health endpoint. Same vulnerability class: information
disclosure via unauthenticated aggregate endpoint.
