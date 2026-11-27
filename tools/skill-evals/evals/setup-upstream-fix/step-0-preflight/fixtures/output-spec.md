<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "route": "work-here" | "live-session" | "sub-agent-worktree" | "scratch-clone" | "brief-file",
  "confirm_with_user_first": true | false,
  "brief_file_dir": "<directory the brief file is written to>" | null,
  "reason": "<one-sentence explanation>"
}
```

- `route`: where Steps 4–5 happen, as the first option this session offers the user.
  `work-here`: in this session's current checkout.
  `live-session`: in another live agent session, sent the brief now.
  `sub-agent-worktree`: in a sub-agent of this session, in its own worktree.
  `scratch-clone`: in a clone of `apache/magpie` this session makes in its own scratch directory.
  `brief-file`: in a session the user opens, given the brief as a file.
- `confirm_with_user_first`: whether this session shows the user what it is about to hand over or do, and waits for their OK, before the work leaves this checkout. `false` when nothing leaves it.
- `brief_file_dir`: the directory the brief is written to when the chosen route writes the brief to a file (the path as written, with `~` and a trailing `/`); `null` when no file is written.

Do not include any text outside the JSON object.
