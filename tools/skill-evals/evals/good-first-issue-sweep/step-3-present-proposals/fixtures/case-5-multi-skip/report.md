<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (7 issues):

```json
[
  {
    "issue_number": 55,
    "title": "Add --no-color flag to the report command",
    "classification": "READY",
    "failing_criteria": [],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 150,
    "title": "Credentials written to plaintext debug logs",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 162,
    "title": "Auth token validation can be bypassed via header casing",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 175,
    "title": "Redesign plugin backend interface for the scheduler",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "architectural-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 189,
    "title": "Decide on event bus design for cross-module notifications",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "architectural-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 203,
    "title": "Remove deprecated v1 REST endpoints",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "deprecation-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 211,
    "title": "Rename legacy config key across the next major release",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "deprecation-decision",
    "injection_flagged": false
  }
]
```
