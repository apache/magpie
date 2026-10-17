<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "offered": ["<companion id>", ...],
  "commands_run": true | false,
  "names_sandbox_step": true | false
}
```

`offered` lists the registry `id` of every companion the recap offers, sorted
alphabetically; `[]` when it offers none.

`commands_run` is whether the agent runs any companion install command
itself rather than printing it for the operator.

`names_sandbox_step` is whether the recap names the companion's sandbox step
in `setup-isolated-setup-install` (roborev: Step B); `false` when nothing
with such a step is offered.

Do not include any text outside the JSON object.
