<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (7 issues):

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
    "issue_number": 88,
    "title": "Add link to CONTRIBUTING.md from the project README",
    "classification": "READY",
    "failing_criteria": [],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 77,
    "title": "Improve error messages in the auth module",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G2", "G3"],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 101,
    "title": "Auth token is logged in plaintext on failed login",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 102,
    "title": "Session cookie missing Secure flag in dev config",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "security-sensitive",
    "injection_flagged": false
  },
  {
    "issue_number": 103,
    "title": "Redesign plugin loading to support async initializers",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "architectural-decision",
    "injection_flagged": false
  },
  {
    "issue_number": 104,
    "title": "Remove deprecated v1 export format",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "deprecation-decision",
    "injection_flagged": false
  }
]
```
