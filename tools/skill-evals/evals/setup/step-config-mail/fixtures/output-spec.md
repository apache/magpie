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
  "next_steps_for": ["<backend>", ...]
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
- `next_steps_for` — the chosen backends whose *what to do next* list is
  printed. Sorted alphabetically. Empty when `run` is `false`.

Do not include any text outside the JSON object.
