<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "status": "absent" | "current" | "stale",
  "is_fault": true | false,
  "missing": [...]
}
```

`status` reports which of the three states the repo's committed default set
is in, per the rules in the check above.

`is_fault` reports whether that state is a fault to be fixed, per the same
rules.

`missing` is a list of `<plugin>@<marketplace>` strings — the entries the
rules above say belong in it, in floor order.

Do not include any text outside the JSON object.
