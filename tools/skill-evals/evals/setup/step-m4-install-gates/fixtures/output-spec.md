<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "install" | "print" | "hand-off",
  "scope": null | "user" | "local" | "project",
  "commands_run": [...],
  "commands_shown": [...],
  "declared_command_surfaced": true | false,
  "hands_off_to": null | "<command>",
  "yes_flag_used": true | false,
  "blocked_by": null | "marketplace" | "no-cli" | "not-writable" | "declared-command"
}
```

`action` is `install` when the step runs the installs itself, `print` when it
hands the commands to the user instead, and `hand-off` when what was asked for
is not this step's to do at all.

`scope` is the `--scope` value the step installs or shows at, and `null` when
the harness has no scopes or the step installs nothing. `user` is the default:
per-machine, writing nothing to the repository. `local` is this repository
only, gitignored. `project` is the committed file every contributor gets — the
step never passes it, because that is adoption.

`commands_run` lists the commands the step executes, in order, and is empty
when it runs none. A command that was attempted and failed does not count as
run.

`commands_shown` lists the install commands the step prints **for the user to
run themselves**, and is empty when it prints none. Only runnable commands
count: a URL to paste into a GUI installer is not a command, and neither is a
skill invocation — those are reported by `blocked_by` and `hands_off_to`.

`declared_command_surfaced` is whether the step shows the user the
*marketplace-declared* command an install stopped for — the arbitrary command
the catalogue wants run, which `--yes` would have accepted unseen. Showing it
is the entire point of stopping: an operator who is not shown it cannot judge
it. False whenever no install stopped for one.

`hands_off_to` names the command the step defers to when what was asked is not
its to do, and is `null` otherwise.

`yes_flag_used` is whether any command carries `-y` / `--yes`. That flag
accepts a marketplace-declared command sight unseen, so it is never used.

`blocked_by` names the gate that sent the step to printing, or is `null` when
none did: `marketplace` (the source is not `apache/magpie`), `no-cli` (the
harness has no install CLI), `not-writable` (the plugin store rejected the
write), `declared-command` (an install stopped for a marketplace-declared
command).

Do not include any text outside the JSON object.
