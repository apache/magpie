<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "confirmed_actions": ["<action description>", ...],
  "skipped_actions": ["<action description>", ...]
}
```

- Each action description uses the form `"post closing comment on #<N>"`,
  `"add duplicate label to #<N>"`, `"close #<N>"`, or
  `"post cross-ref comment on #<kept>"`.
- `confirmed_actions` lists what the maintainer approved and what will be applied.
- `skipped_actions` lists what the maintainer declined or what was not applicable.
- When the maintainer says `cancel` or `none`, `confirmed_actions` must be empty
  and `skipped_actions` must list all four possible actions.
- When `all` was confirmed, `confirmed_actions` must list all applicable actions
  and `skipped_actions` must be empty (or list only actions genuinely not applicable,
  e.g. if `cross_ref_comment` was null).

Do not include any text outside the JSON object.
