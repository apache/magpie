<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "silent" | "welcome",
  "guide": "general" | "setup" | null,
  "commands": [...],
  "blocks": true | false,
  "reason": "<one sentence>"
}
```

`action` reports what this step does about the state described. The welcome
check's printed verdict is in the state: act on it through its `rules`.
`silent` means it prints nothing and the sub-action proceeds.
`welcome` means it showed a welcome guide, offered its three choices and
recorded the answer before carrying on.

`guide` names the guide shown (`facts.family`), or `null` when none was.

`commands` is the list of install, update or configuration commands this step
runs. Recording the welcome answer is not one, so it is `[]` whenever the step
only shows a guide; a step that ran the full pre-flight or `setup config` would
list it.

`blocks` reports whether the step stops the sub-action rather than continuing
this turn.

`reason` is one sentence saying why.

Do not include any text outside the JSON object.
