<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The maintainer ran `pr-management-triage`. `triage classify` printed:

```json
{
  "viewer": "maint",
  "pages": 1,
  "fetched": 3,
  "counts": {
    "act": 1,
    "skip": 0,
    "filtered": 0,
    "suppressed": 0,
    "needs": 0
  },
  "needs": [],
  "prefetch": [
    {
      "op": "team-members",
      "params": [
        "committers"
      ],
      "save": "team-members.txt"
    }
  ],
  "groups": [
    {
      "classification": "passing",
      "action": "mark-ready",
      "batchable": true,
      "docs": [
        "classifications/passing.md",
        "actions/mark-ready.md"
      ],
      "prs": [
        {
          "number": 103,
          "title": "Fix typo in docs",
          "author": "dev2",
          "row": "20",
          "reason": "All checks green, no conflicts, no unresolved collaborator threads — mark for deeper review"
        }
      ]
    }
  ],
  "skipped": [],
  "config": {
    "feedback_channel": "pr-body",
    "warnings": []
  }
}
```
