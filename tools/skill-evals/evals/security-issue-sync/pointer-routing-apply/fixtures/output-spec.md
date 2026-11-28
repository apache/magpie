<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You have only the skill text above. No sibling file has been opened, and you cannot see what any of them say.
Do not guess their contents.
For the confirmed items and the tracker described, list the sibling files the skill's text tells you to read and follow to apply those items and to run the steps after the apply loop.
Name a file only if the text gives that file's name and calls for it here.
Leave out files the text only cites as the place a signal, a proposal or a step was defined, files for an error or a refusal that has not happened, bulk mode, and anything outside this skill's directory.

Return ONLY valid JSON with this structure:

```json
{
  "files_to_open": ["<file name>", ...]
}
```

- `files_to_open` — bare file names, sorted alphabetically; `[]` when the situation calls for none.
