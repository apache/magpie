<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **confirmation-form parsing** step of the `security-issue-invalidate` skill.

A proposal has been surfaced to the user. The user's reply is shown below. Parse the reply and determine the apply action.

Return a JSON object with exactly these fields:

```json
{
  "action": "apply" | "apply_silent" | "replace_email_body" | "repick_canned" | "cancel",
  "email_body_override": "<string or null>",
  "canned_section_override": "<string or null>",
  "rationale": "<one sentence>"
}
```

Field rules:
- `action`:
  - `apply` — user said `go`, `proceed`, or `yes`; apply the full proposal as-is.
  - `apply_silent` — user said `silent`; apply but skip the email draft, note the gap in the rollup.
  - `replace_email_body` — user said `email: <text>`; replace draft body with the supplied text.
  - `repick_canned` — user said `canned: <name>`; re-pick the named canned section.
  - `cancel` — user said `cancel` or `none`; bail, nothing applied.
- `email_body_override`: the text after `email: ` if action is `replace_email_body`, else `null`.
- `canned_section_override`: the section name after `canned: ` if action is `repick_canned`, else `null`.
- `rationale`: one sentence.
