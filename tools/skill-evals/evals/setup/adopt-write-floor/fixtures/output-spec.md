<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "wrote_lock": true | false,
  "min_version": "<version string, or null>",
  "plugins": [...],
  "marketplace_tagged": true | false
}
```

`wrote_lock` reports whether this step writes `.apache-magpie.lock` at all.

`min_version` is the value written into it, or `null` if no lock is written.

`plugins` is the floor written into it, in floor order.

`marketplace_tagged` reports whether the derived `extraKnownMarketplaces`
entry carries an `@version` suffix.

Do not include any text outside the JSON object.
