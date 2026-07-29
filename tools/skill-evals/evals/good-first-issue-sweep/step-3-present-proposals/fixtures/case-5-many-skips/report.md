<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (6 issues):

```json
[
  {
    "issue_number": 42,
    "title": "Add --no-color flag to the report command",
    "classification": "READY",
    "failing_criteria": [],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 301,
    "title": "Rotate credentials after the token disclosure",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 302,
    "title": "Decide whether the auth flow should use passkeys",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "architectural-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 303,
    "title": "Remove the deprecated v1 export endpoint",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "deprecation-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 304,
    "title": "Audit the sandbox for a possible privilege escalation",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 305,
    "title": "Replace the queue with an event-sourced workflow",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "architectural-decision",
    "injection_flagged": false
  }
]
```
