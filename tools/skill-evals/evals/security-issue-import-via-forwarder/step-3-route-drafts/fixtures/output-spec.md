<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **reporter-facing draft routing** step of the `security-issue-import-via-forwarder` skill.

A parent `mode`, the matched adapter (with its `contact_handle` and `via_forwarder_question_mode` attribute), the drafted project-voice `inner_body`, the context `links`, and (for `sync` mode) the milestone being routed are provided, along with the forwarder-routing policy's negative-space (do-not-relay) list. Apply the Step 3 routing rules and return the routing components the skill hands back to the parent. The skill never creates the draft itself; it returns components.

Return a JSON object with exactly these fields:

```json
{
  "mode": "import" | "invalidate" | "sync",
  "to_recipients": ["<contact_handle>"] | [],
  "addressing_block_emitted": true | false,
  "question_mode": true | false,
  "negative_space_suppressed": true | false,
  "rationale": "<one sentence>"
}
```

Field rules:
- `mode`: echo the parent mode that drove the routing.
- `to_recipients`: the matched adapter's `contact_handle` (pick the first available when the adapter returns a list). Empty list `[]` when negative-space suppression applies.
- `addressing_block_emitted`: `true` when a paste-ready `reporter_addressing_block()` is produced; `false` when the milestone is suppressed.
- `question_mode`: the adapter's `via_forwarder_question_mode` attribute value. Omit this field when the draft is suppressed.
- `negative_space_suppressed`: `true` only when `mode` is `sync` and the milestone falls on the forwarder-routing policy's do-not-relay list; `false` otherwise.
- `rationale`: one sentence explaining the routing decision.
