<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offer": true | false,
  "preticked": ["<backend>", ...],
  "command_files": ["<harness>", ...],
  "invocation_only": ["<harness>", ...]
}
```

- `offer` — `true` when this run offers adversarial-reviewer configuration at
  all: only when the user named it (`config adversarial-review`) and the
  `magpie-adversarial-review` plugin is installed. `false` on a plain `config`
  run, on a run entered from a skill's pre-flight, and without the plugin.
- `preticked` — the backends pre-ticked in the proposal: every backend
  `detect` reports available, except the one marked `self`. Sorted
  alphabetically. Empty when `offer` is `false`.
- `command_files` — the harnesses whose command file is offered for writing
  under the user's home: every harness whose CLI is installed (on `PATH`)
  other than Claude Code (its command ships in the plugin) and Copilot (it has
  no command mechanism). Sorted alphabetically. Empty when `offer` is `false`.
- `invocation_only` — harnesses installed on this machine that get the
  one-line invocation shown instead of a file: `["copilot"]` when Copilot's CLI
  is installed, else empty. Empty when `offer` is `false`.

Do not include any text outside the JSON object.
