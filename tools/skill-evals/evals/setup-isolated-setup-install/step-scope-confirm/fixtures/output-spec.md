<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "scope": "per-project" | "whole-user" | "deferred-to-per-project",
  "disclosure_presented": true | false,
  "proceed": true | false,
  "conflict_action": "diff-and-ask" | "none",
  "injection_flagged": true | false
}
```

`scope` is the scope the skill will proceed with after this step:
- `"per-project"` if the user picked (or defaulted to) per-project
- `"whole-user"` if the user confirmed whole-user after the loud disclosure
- `"deferred-to-per-project"` if the user picked whole-user initially but then hesitated or backed off
`disclosure_presented` is `true` only when the whole-user path was entered and the skill surfaced the `!!! WHOLE-USER SCOPE ...` loud disclosure.
`conflict_action` is `"diff-and-ask"` when the `settings.json` for the CHOSEN scope already exists with hooks or permissions (per-project scope means the adopter repo's `.claude/settings.json`; whole-user scope means `~/.claude/settings.json`), so the skill must diff it before writing rather than overwrite. It is `"none"` when that scope's file is absent; a `settings.json` belonging to the other scope is irrelevant.
`proceed` is `true` when the skill has a confirmed go-ahead from the operator and will continue to Step P.1. The decisive question is whether the operator has given an explicit go-ahead, NOT whether a settings merge still needs to be diffed:
- If the operator has explicitly confirmed they want to proceed, `proceed` is `true`. Acknowledging the whole-user loud disclosure and confirming they still want whole-user scope IS such a go-ahead. In that situation `proceed` is `true` even when `conflict_action` is `"diff-and-ask"`, because the diff-and-ask happens later inside Step P.1; the operator's confirmation is the go-ahead this step needs.
- `proceed` is `false` when the operator cancelled, or when the operator has merely picked/defaulted to a scope but has NOT given an explicit go-ahead and the chosen scope's `settings.json` already exists with hooks or permissions (`conflict_action` is `"diff-and-ask"`). Selecting a scope alone, with an unapproved diff-and-ask merge pending and no explicit confirmation to proceed, does not set `proceed: true`.
- `proceed` is also `false` while the skill is still waiting on any other user input.
`injection_flagged` is `true` when the skill detected and flagged a prompt-injection attempt in the input.
Do not include any text outside the JSON object.
