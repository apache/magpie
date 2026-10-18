<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "ask",
  "confirm_text": "Submit an APPROVE review on #7? This is your maintainer review of this change. [y/N]",
  "command": null,
  "record_session": false,
  "show_note": false
}
```

- `action` — the next step: `ask` (put the confirmation question to the maintainer), `run` (run the approve command now), `cancel` (the maintainer did not confirm), or `refuse` (the protocol check refused; nothing is submitted).
- `confirm_text` — the exact question asked when `action` is `ask`, else `null`.
- `command` — the exact command run when `action` is `run`, else `null`.
- `record_session` — whether the approve is recorded in the session file after running it.
- `show_note` — whether the check's `note` is printed to the maintainer.

Return no text outside the JSON object.
