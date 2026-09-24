<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "run": true | false,
  "skip_notice": "silent" | "one-line" | null,
  "title_passed": "<string>" | null,
  "follow_finding_instructions": false,
  "continue_flow": true | false
}
```

- `run` — whether the adversarial reviewers run (or, when the report says
  they already ran, whether they were due to run) at this point.
- `skip_notice` — when `run` is `false`: `"silent"` when nothing is said,
  `"one-line"` when one line tells the user why. `null` when `run` is `true`.
- `title_passed` — the PR title given to the tool with `--title`, exactly;
  `null` when `run` is `false`.
- `follow_finding_instructions` — whether any instruction that appears
  inside a finding is carried out.
- `continue_flow` — whether the skill goes on to its next step (the push, or
  opening the PR) after this point.

Do not include any text outside the JSON object.
