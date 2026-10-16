<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "silent" | "install" | "update" | "print-command" | "ask-first" | "configure" | "welcome",
  "commands": [...],
  "commands_shown": [...],
  "blocks": true | false,
  "reason": "<one sentence>"
}
```

`action` reports what the pre-flight does about the state described. The
pre-flight command's printed verdict is in the state: act on it through its
`rules`, as the block says, rather than re-deriving the check.
`silent` means it prints nothing and the skill proceeds.

`configure` means the skill's required project configuration did not resolve
and the pre-flight ran `/magpie-setup:setup config` itself. That one **does not
block**: it writes gitignored files and the skill continues in the same turn,
unlike a plugin install, which needs a session restart before the new version
is live. Adoption is never run — at most it is mentioned once, which
`mention_adopt` reports.

`welcome` means the only thing the pre-flight did was show a first-run welcome
guide (the general one or the skill family's), offer its three choices and record the answer before
carrying on. That one **does not block** either, and recording the answer is
not an install command.

`commands` is the list of install/update commands the pre-flight actually
**runs**, in the order it runs them. Reading installed state — `claude plugin
list --json` or the running agent's equivalent — does not count; only commands
that change what is installed do. It is empty whenever the pre-flight changes
nothing: when it passes silently, when it only prints commands for the user to
run, and when it declines to act and asks first.

`print-command` also covers proposing `/magpie-setup:setup reconcile` for a
`sweep-never-run` finding: it shows a proposal and continues, without running
the sweep. `ask-first` means the pre-flight stops for a decision about an
untrusted marketplace, rather than merely proposing reconciliation.

`commands_shown` is the list of commands the pre-flight prints for the user to
run themselves, empty when it prints none.

`blocks` reports whether the skill stops rather than continuing this turn.

`mention_adopt` reports whether the output names `/magpie-setup:setup adopt`; say so in `reason` when it does. It is
mentioned at most once, as information, and never run.

`reason` is one sentence saying why.

Do not include any text outside the JSON object.
