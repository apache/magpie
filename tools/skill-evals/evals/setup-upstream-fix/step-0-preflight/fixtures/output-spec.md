<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "route": "work-here" | "clone-here" | "brief-to-session" | "brief-to-user",
  "clone_in_this_sandbox": true | false,
  "confirm_with_user_first": true | false,
  "reason": "<one-sentence explanation>"
}
```

- `route`: where Steps 4–5 happen. `work-here`: in this session's current checkout. `clone-here`: in a clone of `apache/magpie` that this session makes. `brief-to-session`: in another agent session, sent a brief. `brief-to-user`: in a session the user opens, given a brief.
- `clone_in_this_sandbox`: whether this session clones `apache/magpie` itself.
- `confirm_with_user_first`: whether this session shows the user what it is about to hand over, and waits for their OK, before the work leaves this session. `false` when nothing leaves it.

Do not include any text outside the JSON object.
