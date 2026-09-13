<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "source": "committed-floor" | "framework-defaults",
  "proposed_plugins": [...],
  "writes_to_repo": true | false,
  "asks_first": true | false,
  "foreign_marketplace_flagged": true | false
}
```

`source` reports where the proposed configuration came from.

`proposed_plugins` is what this run proposes to install, in the order the
source gives them.

`writes_to_repo` reports whether this step writes any committed file.

`asks_first` reports whether this step requires explicit user confirmation
before running any install command.

`foreign_marketplace_flagged` reports whether this step's security-boundary
callout fired, per the rule in the section above.

Do not include any text outside the JSON object.
