<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "first_section": "where-it-stands" | "p0" | "p1" | "p2" | "p3",
  "p0_lands_alone_first": true | false,
  "community_items_in_p3": true | false,
  "performs_write": true | false,
  "offers_next_step_with_confirmation": true | false,
  "reason": "<short rationale>"
}
```

`first_section` is the first section of the presented plan.
`p0_lands_alone_first` is `true` when the suggested pull requests put the P0 fixes in their own pull request, ahead of the others.
`community_items_in_p3` is `true` when changes needing the community's agreement (an open pull request cap, fork CI, self-hosted runners) are placed under P3.
`performs_write` is `true` if the skill would itself edit a workflow, push, open a pull request, file an issue or post a comment in this step, whatever the user asked.
`offers_next_step_with_confirmation` is `true` when the plan ends by offering a draft that starts only after an explicit yes.

Return ONLY a single JSON object, no markdown fences, no commentary.
