<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "verdict": "satisfied" | "below-floor" | "plugin-missing" | "not-marketplace" | "malformed",
  "is_pin": true | false,
  "needs": [...]
}
```

`verdict` reports how the machine's installed state stands against the lock,
per the rules in the section above. `not-marketplace` is for a lock using one
of the three snapshot methods; `malformed` is for a lock this section's rules
cannot read.

`is_pin` reports whether this lock pins an exact version — that is, whether a
machine running a *newer* version than the lock names is out of compliance.

`needs` is a list of plugin names that must be installed or updated to reach
the floor, in floor order. Empty when nothing is needed.

Do not include any text outside the JSON object.
