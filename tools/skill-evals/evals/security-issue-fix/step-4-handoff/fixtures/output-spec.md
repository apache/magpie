<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "hand_off": true | false,
  "route": "work-here" | "stop" | "live-session" | "sub-agent-worktree" | "scratch-clone" | "brief-file",
  "brief_file_dir": "<directory the brief file is written to>" | null,
  "commit_subject": "<the commit subject the brief carries>" | null,
  "pr_title": "<the PR title the brief carries>" | null,
  "brief": "<the full brief text this session would show the user and hand over>" | null,
  "resume_here_at": "step-4" | "step-10" | null,
  "reason": "<one-sentence explanation>"
}
```

- `hand_off`: whether Steps 7–9 go to a session in another checkout.
- `route`: the first option this session offers the user; `work-here` when it does the work itself, `stop` when the run stops without handing anything over.
- `brief_file_dir`: the directory the brief is written to when the chosen route writes it to a file (with `~` and a trailing `/`), else `null`.
- `commit_subject`, `pr_title`, `brief`: the text the hand-off carries, `null` when there is no hand-off.
- `resume_here_at`: where this session carries on: `step-4` when it does the work itself, `step-10` when it waits for the reported PR, `null` when it stops.

Do not include any text outside the JSON object.
