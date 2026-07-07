<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (5 issues):

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
    "issue_number": 77,
    "title": "Improve error messages in the auth module",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G2", "G3"],
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
    "issue_number": 99,
    "title": "Refactor the scheduler to support pluggable backends",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G1", "G4"],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 120,
    "title": "Remove deprecated API endpoints from v1",
    "classification": "SKIP",
    "failing_criteria": [],
    "skip_reason": "deprecation-decision",
    "injection_flagged": false
  }
]
```
