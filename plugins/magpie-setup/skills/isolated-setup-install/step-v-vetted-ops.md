<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step V — the vetted-ops split and exclusion

Read this when the walk-through reaches Step V and both of its conditions in `SKILL.md` hold:
the adopter routes forge operations through `vetted-ops`, and the sandbox is on.

There are six console scripts over one catalogue, and which of them
gets the `allow` is the entire security question:

| Entry point | Can write? | Permission |
|---|---|---|
| `vetted-op-read` | never — refused before policy or `--caller` is consulted | `allow` |
| `vetted-op-tracker` | only the tracker rollup / body-field procedures — everything else refused before policy | `ask` |
| `vetted-op-tracker-batch` | only a checked manifest of private-tracker writes, when the approved policy turns batching on (`batch` or `none`) | `ask` |
| `vetted-op-tracker-batch-unprompted` | the same, and only under a policy set to `none`; refuses any other policy before reading the manifest | `ask` (`allow` only on the adopter's explicit `private_tracker_writes = "none"`) |
| `vetted-op-git` | only the git operations the sandbox blocks, plus `git-pr-create` | `ask` |
| `vetted-op` | yes | `ask` |

**Never propose an `allow` on `vetted-op`.** It is tempting, because
the policy declares a read-only caller and the invocation names it.
That reasoning is wrong: `--caller` is an argv string chosen by
whoever runs the command, so an `allow` on the write dispatcher
grants every operation in the catalogue no matter which caller the
example names. The read dispatcher needs no such trust — it refuses
writes structurally.

```jsonc
"permissions": {
  "allow": [
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)"
  ],
  "ask": [
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-git *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-git *)"
  ],
  "deny": [
    // `Edit(path)` is the path rule for every file-writing tool — Write and
    // NotebookEdit included. A `Write(path)` rule is NOT matched by the file
    // permission check; do not add one alongside, it reads as a second layer
    // that is not there.
    //
    // the operation catalogue — the read `allow` rests on its shape
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)",
    // the fixed path the rules name, which points into that catalogue
    "Edit(~/.claude/magpie/**)",
    // the policy naming which caller may run which operation
    "Edit(.apache-magpie-overrides/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-overrides/tools/vetted-ops/**)",
    "Edit(~/.config/apache-magpie/vetted-ops/**)",
    "Edit(//**/.git/**/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.svn/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-local/tools/vetted-ops/**)"
  ]
}
```

Allow **both** invocation forms, and add both to
`sandbox.excludedCommands` (`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *"` and
`"uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *"`). Skills document `uv run --project`; read-only
gatherer agents use `uvx --from`, because `uv run` in the plugin cache
needs to write a venv there. A rule for only one form leaves every call
in the other form prompting.

Add both forms of `vetted-op-tracker`, `vetted-op-tracker-batch`, `vetted-op-tracker-batch-unprompted`, `vetted-op-git` and `vetted-op` to `sandbox.excludedCommands` too
(`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *"`, `"uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *"`,
`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *"`, `"uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch *"`,
`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *"`, `"uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker-batch-unprompted *"`,
`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-git *"`, `"uvx --from ~/.claude/magpie/vetted-ops vetted-op-git *"`,
`"uv run --project ~/.claude/magpie/vetted-ops vetted-op *"` and `"uvx --from ~/.claude/magpie/vetted-ops vetted-op *"`):
their writes need a `gh` that can verify TLS, which a sandboxed one cannot,
and a sandboxed `vetted-op` cannot even read `~/.claude/magpie/` to start.
`vetted-op-git` does what cannot happen inside at all: an SSH push gets no connection through the sandbox's proxy,
and a linked worktree's administrative directory is read-only there.
Excluding them is acceptable because every operation is a fixed `gh` argv with no shell
and bodies come only from the workspace, so they reach less than the bare `gh *` already excluded;
`vetted-op-tracker` is further closed to the tracker procedures, and the two batch entry points to a checked manifest of them and the other private-tracker writes.
**All five stay in `ask`, never `allow`**, so each write (or each batch) keeps its confirmation;
`sandbox-lint` fails an exclusion that has lost its `ask`.
The one exception is the adopter's to make, never the agent's to propose unprompted:
a project whose approved policy sets `[approval] private_tracker_writes = "none"` may move the two `vetted-op-tracker-batch-unprompted` rules, and only those, to `allow` (never `vetted-op-tracker-batch`, which also runs `batch` policies), after reading what that gives up in the
[batch design note](../../../../docs/designs/2026-11-26-vetted-ops-batch-tracker-writes.md#how-approval-maps-to-harness-prompts).

Before the user approves the policy, propose the grants the installed skills use.
Run the caller-grant comparison of [`setup reconcile` check 3a](../setup/reconcile.md#the-sweep): every installed
skill whose caller the README's `[callers]` example names gets the operations listed there, among them the
`git-*` publishing steps and `pr-add-label`, and a caller that opens and labels pull requests gets the repository's
taxonomy labels, discovered with `gh label list`, proposed by name in `[values] upstream_labels`.
Show each proposal as a TOML diff; the policy is `Edit`-denied to the agent, so the user applies it.

Outside the sandbox, the write dispatchers act only on a policy the user approved:
a byte-for-byte copy in `~/.config/apache-magpie/vetted-ops/`, which the agent cannot write.
Ask the user to review the project's policy and approve it **in their own terminal** (a `!` command runs sandboxed and cannot write there),
and to repeat it after every change to the policy:

```bash
mkdir -p ~/.config/apache-magpie/vetted-ops && cp .apache-magpie-overrides/tools/vetted-ops/config.toml ~/.config/apache-magpie/vetted-ops/<project>.toml
```

Never write that directory yourself, and never suggest a symlink instead of a copy: a link back into the repository re-trusts a path the agent can reach.

The rules name the fixed path `~/.claude/magpie/vetted-ops`, never the
versioned plugin-cache directory. The plugin's `SessionStart` hook points
that path at the installed version every session, so an upgrade needs no
rule change. **Never write a rule with `*` in place of the plugin
version.** A `*` also matches spaces, so it approves — and, in
`excludedCommands`, runs unsandboxed — a command with extra `uv` options
spliced in at that position (`--with <any package>`, a second `--from`).
If an adopter's settings still carry the versioned `*` form, replace it
with the fixed path.

Tell the operator plainly what this buys and what it does not:

- The catalogue is protected twice — by these rules, and by the
  plugin cache sitting outside every `sandbox.filesystem.allowWrite`
  root, so sandboxed Bash cannot write there either.
- The policy TOML is protected **once**, and that is tolerable only
  because the read dispatcher ignores policy when it refuses a
  write. Editing the policy can widen which repo is *read*; it
  cannot turn a read into a write.
- Writes are not unattended. They keep the harness confirmation —
  the dispatcher bounds their *shape*, not the operator's decision
  to make them.

Do not describe per-caller scoping as isolation. It is
least-privilege hygiene for a cooperating skill, and it is worth
having for that, but it stops nothing that chooses to name a
different caller.

## Step V.1 — Read-only vetted ops MUST never prompt

This is not optional. No `vetted-op-read` invocation may ever prompt, in
any form: bulk skills run it from background gatherer agents, which cannot
surface a prompt, so each prompt is a silent denial and the sync returns
partial results nobody can verify. Rationale and the full shape:
[`docs/setup/secure-agent-setup.md` → Read-only vetted ops never prompt](../../../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).

Resolve `$HOME`, read every settings scope (user, project, project-local,
and managed where readable), and propose the exact edit for each gap. The
operator applies it; never write a settings file on your own.

1. **Allow both launchers.** `Bash(<launcher> ~/.claude/magpie/vetted-ops vetted-op-read *)`
   MUST be allowed for each launcher in {`uvx --from`, `uv run --project`}:
   two rules, in the committed project `.claude/settings.json` (as in the
   framework's own) or in user scope. The literal `~` is the only spelling:
   the agent-guard `vetted-ops-spelling` guard refuses an expanded home path,
   so no absolute-path rule is needed. If an earlier run left
   `<resolved $HOME>/.claude/magpie/vetted-ops` allow rules or exclusions,
   propose removing them.
2. **No ask rule.** Propose removing every `permissions.ask` rule, in any
   scope, that matches a `vetted-op-read` command in either launcher form —
   a broad rule such as `Bash(uvx *)` counts. An ask rule prompts even when
   an allow rule matches.
3. **Read block off.** If `permissions.blockReadsOutsideWorkingDirectories`
   is `true` in any scope, propose removing it (or setting it `false`). With
   it on, every call prompts, because the check cannot resolve the literal
   `~` the commands spell, and no `allow` rule overrides it. Never offer an
   `additionalDirectories` entry or `/add-dir` for the checkout instead (see
   item 7). Say plainly that Bash stays
   sandboxed and the credential `Read` denies still apply. If managed
   settings force it on, the imperative cannot be met on this machine:
   tell the operator, and that bulk skills must not run their gatherer
   agents there.
4. **Tamper protection.** The three `Edit` deny rules above MUST be present,
   in the project settings or in user scope; propose any that is missing.
   They are what makes the unprompted read safe.
5. **Exclusions for both launchers.** `sandbox.excludedCommands` keeps
   the `vetted-op-read` and `vetted-op-tracker` entries in both `~`
   launcher forms. Without them an allowed call runs inside the sandbox,
   where its `gh` cannot verify TLS: a silent failure again.
6. **The spelling guard.** The agent-guard plugin MUST be installed, so its
   `vetted-ops-spelling` guard turns an expanded spelling into a refusal that
   names the `~` command, instead of a sandboxed call that fails silently.
7. **The checkout is not a working directory.** No
   `permissions.additionalDirectories` entry in any scope may cover
   `$HOME/.claude/magpie` (that path, its `~` spelling, anything inside it
   such as `~/.claude/magpie/vetted-ops`, or a parent such as
   `$HOME/.claude` or `$HOME`). A working directory is writable to sandboxed
   Bash, and item 5's exclusions run that checkout outside the sandbox.
   `sandbox-add-project-root.sh` removes the `~/.claude/magpie` entry it once
   added from each worktree's `settings.local.json`; propose the hand edit for
   any other covering entry, naming the file.

This covers the read dispatcher only. `vetted-op-tracker`, `vetted-op-git` and `vetted-op`
are excluded but stay in `ask`, never in `allow`.

## Step V.2 — The read-only gatherer agent (Claude Code)

Bulk skills fan out one background agent per item.
A general-purpose agent has `Bash`, `Edit` and `Write`, and reads content written by outsiders:
the read-then-act exposure Step V.1's unprompted reads should not widen.
The framework ships a narrower agent, which `pr-management-code-review`'s prefetch and `pr-management-stack-review`'s layer readers use where it is installed,
[`tools/agent-isolation/agents/magpie-gatherer.md`](../../../../tools/agent-isolation/agents/magpie-gatherer.md):
`Read`, `Grep`, `Glob`, `vetted-op-read` as its only Bash, and the four PonyMail reads, which its own `PreToolUse` hook approves (a background agent cannot answer a prompt).
It has no `Edit`, `Write`, general Bash or write tool.

Claude Code only, and only after Step V.1 passes: without it every gatherer read is a silent denial.
On another harness, report **n/a**.

1. Propose copying it to the user scope, `~/.claude/agents/magpie-gatherer.md`
   (`cp <framework>/tools/agent-isolation/agents/magpie-gatherer.md ~/.claude/agents/`).
   It must be a user-scope agent, not a plugin agent: Claude Code ignores a plugin agent's `hooks`, `mcpServers` and `permissionMode`, and a plugin-wide hook matching the agent's name would match any agent that takes the name.
   The operator runs the copy; never write it yourself.
2. If a file is already there and differs, show the diff and let the operator choose;
   a local edit that adds a tool to its `tools:` line widens what the fan-out can do and is theirs to keep or drop knowingly.
3. Say that a session started before the copy does not see the agent: it takes effect in the next session.
