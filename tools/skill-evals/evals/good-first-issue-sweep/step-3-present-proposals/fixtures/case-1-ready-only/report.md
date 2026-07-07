<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (3 issues):

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
    "issue_number": 57,
    "title": "Fix missing null check in UserRepository.findById",
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
  }
]
```
