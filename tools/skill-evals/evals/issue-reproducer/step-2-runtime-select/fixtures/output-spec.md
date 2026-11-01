<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "chosen_location": "body | comment-<N> | attachment-<filename> | null",
  "runtime_source": "default | language-table | null",
  "command": "<the command template that will run the file, or null>",
  "translated": false,
  "outcome": "run | cannot-run-environment",
  "missing_runtimes": ["<language>", ...]
}
```

- `chosen_location` — the block that will run; `null` when none can.
- `runtime_source` — `default` when the single `<runtime>` recipe runs it (no *Runtimes by language* table, or an `unknown`-language block); `language-table` when a table row does; `null` when nothing runs.
- `command` — the command template exactly as configured (with `<file>`), or `null`.
- `translated` — `true` only if a block is rewritten into a different language to run it. Always `false` under the step.
- `outcome` — `run` when a block will run; `cannot-run-environment` when no candidate has a runtime.
- `missing_runtimes` — the languages of candidate blocks that had no runtime, sorted, without duplicates; `[]` when none.
