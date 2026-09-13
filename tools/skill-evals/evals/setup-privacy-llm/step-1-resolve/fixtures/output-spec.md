<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "continue-to-detection" | "read-and-verify",
  "rewrites_existing": true | false,
  "winning_file": null | ".apache-magpie-local/privacy-llm.md" | ".apache-magpie-overrides/privacy-llm.md",
  "reports_shadowing": true | false
}
```

`action` is `continue-to-detection` only when neither copy exists — the first
run. Any existing configuration goes to `read-and-verify` instead.

`rewrites_existing` is whether the step overwrites a configuration that is
already there. It never does; being invoked is not a reason to rewrite a
working file.

`winning_file` names the copy that resolves, local first, or `null` when
neither exists.

`reports_shadowing` is whether the step tells the user that a local copy is
shadowing the project's committed one. True only when both exist.

Do not include any text outside the JSON object.
