<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You have only the skill text above. No sibling file has been opened, and you cannot see what any of them say.
Do not guess their contents.
For the situation given, list the sibling files the skill's text tells you to open because of this situation, before acting.
Name a file only if the text gives that file's name and calls for it here.
Leave out the procedure file of a step that is simply running as normal, and anything outside this skill's directory.

Return ONLY valid JSON with this structure:

```json
{
  "files_to_open": ["<file name>", ...]
}
```

- `files_to_open` — bare file names, sorted alphabetically; `[]` when the situation calls for none.
