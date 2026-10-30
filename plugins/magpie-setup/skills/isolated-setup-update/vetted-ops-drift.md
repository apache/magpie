<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The vetted-ops split and exclusion — four drift checks

Read from `SKILL.md` § *The vetted-ops split and exclusion* when the adopter uses the `vetted-ops` dispatcher.

**First, and most important: has `vetted-op` drifted into `allow`?**
Only `vetted-op-read` belongs there.
The write dispatcher in an `allow` list grants the whole catalogue, because whoever runs an invocation chooses the caller name it passes.
Report that as a must-fix, ahead of anything else in this section.
`vetted-op-tracker` in `allow`, or `vetted-op` in `sandbox.excludedCommands`, is the same must-fix.
`vetted-op-tracker` in `ask` and in `sandbox.excludedCommands` (both the `uv run --project` and `uvx --from` forms) is the intended wiring; a missing entry is drift, since without the exclusion the rollup and body-field writes fail in the sandbox.

**Second, `permissions.deny` still covers both surfaces**, each with an `Edit` rule:

- `~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**`
- `~/.claude/magpie/**`
- `.apache-magpie-overrides/tools/vetted-ops/**`
- `//**/.git/**/apache-magpie/tools/vetted-ops/**`, `//**/.svn/apache-magpie/tools/vetted-ops/**`, `//**/.apache-magpie-local/tools/vetted-ops/**` (a personal policy)

Report a missing rule as drift to repair, not a note.
A leftover `Write(…)` rule on either path is the opposite kind of drift: `Edit(path)` already binds every file-editing tool, and the file permission check does not match a `Write(path)` rule, so surface it as cruft to delete.
This check is the most likely to rot: the plugin-cache path carries the plugin *name*, so a family rename or a move of the dispatcher to another substrate plugin leaves a deny rule that looks plausible but matches nothing.
Resolve the glob against the installed tree and confirm it actually hits the catalogue, rather than eyeballing the string.

**Third, no `vetted-op` rule names the versioned plugin-cache path with a `*`.**
Rules and `sandbox.excludedCommands` entries spelled `~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/*/tools/vetted-ops …` are the pre-fixed-path form.
The `*` also matches spaces, so it approves, and runs unsandboxed, a command with extra `uv` options spliced in where the version sits.
Report each one as a must-fix and propose the replacement, which names the fixed path the plugin's `SessionStart` hook maintains: `~/.claude/magpie/vetted-ops`.
Check the user-scope settings and any agent definition whose `tools:` list carries the rule, not only the project's `.claude/settings.json`.

**Fourth, read-only vetted ops never prompt.**
This is an imperative of the setup, so every gap is a must-fix, reported beside the first check rather than under "prompts you are paying".
Resolve `$HOME` and read every scope (user, project, project-local, managed where readable).
Report as a must-fix:

- a missing `vetted-op-read` allow rule: each launcher (`uvx --from`, `uv run --project`) with the literal `~/.claude/magpie/vetted-ops` base, two rules;
- an allowed form without its matching `sandbox.excludedCommands` entry, since such a call runs sandboxed and its `gh` fails silently;
- a leftover allow rule or exclusion spelled with the resolved `$HOME/.claude/magpie/vetted-ops` base, which the agent-guard `vetted-ops-spelling` guard now refuses anyway (propose removing it);
- any `permissions.ask` rule that matches a `vetted-op-read` command in either launcher form, broad rules such as `Bash(uvx *)` included, since an ask rule prompts even when an allow rule matches;
- `permissions.blockReadsOutsideWorkingDirectories` on in any scope, under which every call prompts because the check cannot resolve the literal `~`;
- a missing vetted-ops `Edit` deny rule (the second check), since those rules are what make the unprompted read safe.

The reason is the background gatherer agents: they cannot surface a prompt, so each prompt is a silent denial and a bulk sync returns partial results.
This covers `vetted-op-read` only; `vetted-op-tracker` and `vetted-op` stay as the first check says.
The remedy is `setup-isolated-setup-install` Step V.1; shape and rationale: [`docs/setup/secure-agent-setup.md` → Read-only vetted ops never prompt](../../../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).
