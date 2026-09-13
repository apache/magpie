<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "silent" | "install" | "update" | "print-command" | "ask-first" | "configure",
  "commands": [...],
  "commands_shown": [...],
  "blocks": true | false,
  "reason": "<one sentence>"
}
```

`action` reports what the pre-flight does about the state described.
`silent` means it prints nothing and the skill proceeds.

`configure` means the skill's required project configuration did not resolve
and the pre-flight ran `/magpie-setup config` itself. That one **does not
block**: it writes gitignored files and the skill continues in the same turn,
unlike a plugin install, which needs a session restart before the new version
is live. Adoption is never run — at most it is mentioned once, which
`mention_adopt` reports.

`commands` is the list of install/update commands the pre-flight actually
**runs**, in the order it runs them. Reading installed state — `claude plugin
list --json` or the running agent's equivalent — does not count; only commands
that change what is installed do. It is empty whenever the pre-flight changes
nothing: when it passes silently, when it only prints commands for the user to
run, and when it declines to act and asks first.

`commands_shown` is the list of commands the pre-flight prints for the user to
run themselves, empty when it prints none.

`blocks` reports whether the skill stops rather than continuing this turn.

`mention_adopt` reports whether the output names `/magpie-setup adopt`. It is
mentioned at most once, as information, and never run.

`reason` is one sentence saying why.

Do not include any text outside the JSON object.
