<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "write_dir": "<absolute directory the diff is written to> | null",
  "create_dir": true | false,
  "offers_overrides": true | false,
  "stopped": true | false
}
```

- `write_dir`: the directory both config files are written to, exactly as resolved; null when nothing is written.
- `create_dir`: whether the skill has to create `write_dir` before writing.
- `offers_overrides`: whether the skill offers, proposes or accepts writing to `.apache-magpie-overrides/`.
- `stopped`: whether the skill stops without writing because there is nowhere to keep personal configuration.

Do not include any text outside the JSON object.
