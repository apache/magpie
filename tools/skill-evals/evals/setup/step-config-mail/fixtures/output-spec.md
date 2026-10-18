<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "run": true | false,
  "batched": true | false,
  "read_default": ["<backend>", ...],
  "draft_backend": "gmail-plaintext" | "maildir" | null,
  "next_steps_for": ["<backend>", ...],
  "draft_written_to": "project.md" | "user.md" | null
}
```

- `run` — `true` when Step 3e applies to this run: a skill in scope belongs to
  the `security` or `release-management` family and its mail backends are not
  yet recorded in `project.md`. `false` otherwise.
- `batched` — `true` when the mail questions are folded into Step 3's one
  batched question (a run entered from a skill's pre-flight). `false` on any
  other run, and whenever `run` is `false`.
- `read_default` — the read-side backends selected by default in the proposal.
  Sorted alphabetically. Empty when `run` is `false`.
- `draft_backend` — the drafting backend recorded: the one the user chose, or
  the default when the user expressed no preference. `null` when `run` is
  `false`.
- `next_steps_for` — the chosen backends the hand-over is for: each one not
  yet available in the session's tool list, plus Maildir whenever it is
  chosen. A backend already registered is not listed, even when the step it
  shares with a missing one is printed. Sorted alphabetically. Empty when
  `run` is `false`.
- `draft_written_to` — where the drafting choice is recorded: `project.md`
  when the personal layer holds this project's `project.md`, `user.md` (as
  `tools.mail_create`) for a personal choice on a project whose `project.md`
  is committed. `null` when `run` is `false`.

Do not include any text outside the JSON object.
