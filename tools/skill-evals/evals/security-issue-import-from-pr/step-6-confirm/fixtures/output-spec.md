<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **confirmation parsing** step of the `security-issue-import-from-pr` skill.

A full proposal has been surfaced to the user. The user's reply is shown at the end. Parse the reply and return the apply plan.

Return a JSON object with exactly these fields:

```json
{
  "action": "apply" | "apply_with_overrides" | "cancel",
  "title_override": "<string or null>",
  "reporter_override": "<string or null>",
  "severity_override": "<string or null>",
  "rationale": "<one sentence>"
}
```

Field rules:
- `action`: `apply` if user said `go`/`proceed`/`yes`/`OK`; `apply_with_overrides` if user supplied one or more named overrides; `cancel` if user said `cancel`/`none`/`hold off`.
- `title_override`: the new title string after `title: `, or `null`.
- `reporter_override`: the value after `reporter: `, or `null`.
- `severity_override`: the value after `severity: `, or `null`.
- `rationale`: one sentence.
