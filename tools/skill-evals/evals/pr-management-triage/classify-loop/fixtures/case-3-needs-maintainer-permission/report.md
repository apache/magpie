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
    "needs": 1
  },
  "needs": [
    {
      "op": "upstream-permission",
      "params": [
        "kaxil"
      ],
      "save": "permission-kaxil",
      "why": "maintainer status decided conservatively; resolve and classify again"
    }
  ],
  "prefetch": [],
  "groups": [
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
    }
  ],
  "skipped": [],
  "config": {
    "feedback_channel": "pr-body",
    "warnings": []
  }
}
```
