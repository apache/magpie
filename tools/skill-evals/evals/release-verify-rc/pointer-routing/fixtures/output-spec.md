<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You have only the skill text above. No sibling file has been opened, and you cannot see what any of them say.
Do not guess their contents.
For the situation given, list the sibling files the skill's text tells you to open now, at this point of the run, before acting.
Name a file only if the text gives that file's name and calls for it at this point.
Leave out files the text calls for only at another step, on a failure or warning, or for an optional or conditional path the situation does not mention, and anything outside this skill's directory.

Return ONLY valid JSON with this structure:

```json
{
  "files_to_open": ["<file name>", ...]
}
```

- `files_to_open` — bare file names, sorted alphabetically; `[]` when the situation calls for none.
