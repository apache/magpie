<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You have only the skill text above and the situation below.
No other file has been opened, and you cannot see what any of them say.
Do not guess their contents.
For the situation given, list every file the skill's text tells you to open during Gather, wholly or one section of it, before the plan.
Name a file only if the text links it and calls for it in this situation.

Return ONLY valid JSON with this structure:

```json
{
  "files_to_open": ["<path exactly as the text's link gives it, without any #anchor>", ...]
}
```

- `files_to_open` — each file once, sorted alphabetically; `[]` when the situation calls for none.
