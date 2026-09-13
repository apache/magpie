<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "status": "not-adopted" | "met" | "below" | "unshippable-plugin",
  "is_fault": true | false,
  "shortfall": [...]
}
```

`status` reports how the machine stands against the committed floor, per the
rules in the check above.

`is_fault` reports whether that state is a fault to be fixed, per the same
rules.

`shortfall` lists the plugin names that do not meet the floor, in floor order.

Do not include any text outside the JSON object.
