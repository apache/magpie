<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer_adjustments": true | false,
  "deltas": ["<delta-slug>", ...],
  "delegated_commands": ["<magpie-setup command>", ...]
}
```

`offer_adjustments` is `false` when `no_adjust` was set or when the collected state has no gaps.
`deltas` contains zero or more of: `"target-unwired"`, `"family-not-installed"`, `"dangling-symlinks"`, `"drift"`.
`delegated_commands` contains the exact `setup` commands to propose, or is empty when there are no gaps.
Do not include any text outside the JSON object.
