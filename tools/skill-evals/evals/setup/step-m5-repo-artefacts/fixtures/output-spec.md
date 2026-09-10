<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer_made": true | false,
  "offer_default": "no" | "yes",
  "artefacts_offered": ["settings-block", "config-store"],
  "install_complete_without": true | false
}
```

`offer_made` is `true` only when the detected agent is Claude Code. Codex CLI,
Gemini CLI, VS Code / Copilot and any other client cannot express a committed
per-family default set, so `offer_made` is `false` and `artefacts_offered` is
`[]`.

`offer_default` is `"no"` whenever an offer is made: the block is optional and
is never written without the user asking for it.

`artefacts_offered` lists both repo-side artefacts when an offer is made —
`"settings-block"` and `"config-store"` — in that order.

`install_complete_without` is always `true`. A marketplace install that writes
nothing to the repo is a finished, working install; declining the offer, or
being on a harness that cannot take it, never makes the install partial.

Do not include any text outside the JSON object.
