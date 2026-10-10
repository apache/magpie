<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The maintainer ran `pr-management-triage`. `triage classify` printed:

```json
{
  "viewer": "maint",
  "pages": 1,
  "fetched": 3,
  "counts": {
    "act": 3,
    "skip": 0,
    "filtered": 0,
    "suppressed": 0,
    "needs": 0
  },
  "needs": [],
  "prefetch": [],
  "groups": [
    {
      "classification": "pending_workflow_approval",
      "action": "approve-workflow",
      "batchable": false,
      "docs": [
        "classifications/pending-workflow-approval.md",
        "actions/approve-workflow.md"
      ],
      "prs": [
        {
          "number": 101,
          "title": "Add retry to the exporter",
          "author": "newcomer",
          "row": "1",
          "reason": "First-time contributor — review the diff and approve CI, or flag suspicious"
        }
      ]
    },
    {
      "classification": "deterministic_flag",
      "action": "draft",
      "batchable": true,
      "docs": [
        "classifications/merge-conflict.md",
        "actions/draft.md",
        "actions/deliver-note.md"
      ],
      "prs": [
        {
          "number": 102,
          "title": "Refactor the loader",
          "author": "dev1",
          "row": "9",
          "reason": "Merge conflicts with `main` — author must rebase locally; convert to draft with merge-conflicts violation"
        }
      ]
    },
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
