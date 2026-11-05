<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

You have only the skill text above. No sibling file has been opened, and you cannot see what any of them say.
Do not guess their contents.
For the tracker described, list the sibling files that a sub-step sends you to on a condition this tracker meets.
Name a file only if the text gives that file's name, and leave out anything outside this skill's directory.
Leave out files for mail handling and GitHub advisories: the tracker described has neither.

Return ONLY valid JSON with this structure:

```json
{
  "files_to_open": ["<file name>", ...]
}
```

- `files_to_open` — bare file names, sorted alphabetically; `[]` when the tracker meets no such condition.
