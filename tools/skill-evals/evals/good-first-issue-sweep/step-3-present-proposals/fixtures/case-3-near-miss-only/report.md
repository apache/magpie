<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config:
  upstream: apache/acme
  good_first_issue_label: "good first issue"

Step 2 classification results (3 issues):

```json
[
  {
    "issue_number": 21,
    "title": "Performance improvements across the board",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G1", "G2", "G3"],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 33,
    "title": "Better logging in the pipeline module",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G3"],
    "skip_reason": null,
    "injection_flagged": false
  },
  {
    "issue_number": 45,
    "title": "Handle edge case in CSV parser",
    "classification": "NEAR-MISS",
    "failing_criteria": ["G2", "G3"],
    "skip_reason": null,
    "injection_flagged": false
  }
]
```
