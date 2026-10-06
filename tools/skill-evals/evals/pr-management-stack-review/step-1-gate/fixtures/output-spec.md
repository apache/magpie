<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "review | stop",
  "stop_reason": "not-a-stack | cross-fork | nothing-open | api-unavailable | null",
  "lowest_open_layer": 1,
  "merged_layers": [],
  "draft_layers": [],
  "self_authored": false,
  "unverified_ci_layers": [],
  "handoff": "<the command to point the maintainer at, or an empty string>",
  "trunk_gated_by_pr": null
}
```

Rules:
- `action` is `stop` exactly when one of the abort rules fires; `stop_reason` names it, otherwise `null`.
- `lowest_open_layer` is the smallest position whose PR is OPEN (drafts count as open); `null` when stopping.
- `merged_layers` lists positions whose PR is MERGED; `draft_layers` lists open positions with `isDraft: true`.
- `self_authored` is true only when `<viewer>` authored every layer.
- `unverified_ci_layers` lists positions with no project-owned CI context whatever the rollup state (bot-only green, or a draft whose only context is a bot).
- `handoff` is `pr-management-code-review pr:<N>` for a PR that is not in a stack, otherwise an empty string.
- `trunk_gated_by_pr` is the number of the open PR whose head is the stack's `baseRefName` when that branch is not the default branch and such a PR exists; otherwise `null`.
- Do not include any text outside the JSON object.
