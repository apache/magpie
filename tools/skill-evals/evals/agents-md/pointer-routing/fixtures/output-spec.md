<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{"must_read": "<repository-relative path, or none>"}
```

- `must_read` is the one file the instructions send you to before this kind
  of task, written as a repository-relative path without a leading `./`.
- Use `none` when the instructions point at no file for this task.
- Return ONLY a single JSON object, no fences, no commentary.
