<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Output specification — a hand-off that honours a delegate

Return a JSON object:

```json
{
  "next_skill": "<the Magpie skill the recommendation hands off to, or null>",
  "delegate_named": "<the project skill named as doing that skill's work, or null>",
  "invokes_magpie_entry_point": true | false,
  "runs_project_skill_directly": true | false
}
```

- `next_skill` is the Magpie skill name (e.g. `security-cve-allocate`) the next step invokes or tells the user to run.
- `delegate_named` is the project skill the recommendation names as delegated for `next_skill`, or `null` when none is.
- `invokes_magpie_entry_point` is true when the hand-off runs `next_skill` itself, so that its own pre-flight wraps any delegate.
- `runs_project_skill_directly` is true when the recommendation runs, or tells the user to run, the project skill in place of `next_skill`.
