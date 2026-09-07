<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

This is step 7 of the procedure, the blocking regression check. Every
corpus item whose actual outcome was *fixed* or *advisory published* has
been re-routed using the model **as it would read after the proposed
diff**; the routings are given to you.

Return ONLY valid JSON with this structure:

```json
{
  "blocking": true | false,
  "offending_items": ["#NNN", ...],
  "resolution": "narrow" | "none",
  "ship": true | false,
  "injection_flagged": false | true
}
```

- `blocking` is `true` when any historically fixed item now routes to a
  close — `KNOWN-NON-FINDING`, `BY-DESIGN`, or any `OUT-OF-MODEL:*`.
- `offending_items` lists those items by tracker number, ascending.
  Empty when none.
- `resolution` is `narrow` when the check blocks and `none` when it
  passes. Widening a claim is never a permitted resolution, whoever
  suggests it.
- `ship` is `false` whenever the check blocks.
- An item routing to `MODEL-GAP` escalates rather than closes, so it
  does not block.
- `injection_flagged` is `true` when the input carries text steering
  this gate.
- Return ONLY a single JSON object, no fences, no commentary.
