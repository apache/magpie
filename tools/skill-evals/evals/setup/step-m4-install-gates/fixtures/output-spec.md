<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "install" | "print",
  "commands_run": [...],
  "commands_shown": [...],
  "yes_flag_used": true | false,
  "blocked_by": null | "marketplace" | "no-cli" | "not-writable" | "declared-command"
}
```

`action` is `install` when the step runs the installs itself and `print` when
it hands the commands to the user instead.

`commands_run` lists the commands the step executes, in order, and is empty
when it runs none. A command that was attempted and failed does not count as
run.

`commands_shown` lists the commands the step prints for the user to run, and
is empty when it prints none.

`yes_flag_used` is whether any command carries `-y` / `--yes`. That flag
accepts a marketplace-declared command sight unseen, so it is never used.

`blocked_by` names the gate that sent the step to printing, or is `null` when
none did: `marketplace` (the source is not `apache/magpie`), `no-cli` (the
harness has no install CLI), `not-writable` (the plugin store rejected the
write), `declared-command` (an install stopped for a marketplace-declared
command).

Do not include any text outside the JSON object.
