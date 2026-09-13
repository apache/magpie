<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "updates_plugins": true | false,
  "new_min_version": "<version string, or null>",
  "stages_files": [...],
  "commits": true | false
}
```

`updates_plugins` reports whether this step updates the machine's installed
plugins.

`new_min_version` is the value `min_version` holds after this step, or `null`
if no lock is written.

`stages_files` is the list of repo-relative paths this step `git add`s, empty
if none.

`commits` reports whether this step creates a git commit.

Do not include any text outside the JSON object.
