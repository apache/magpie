<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Step R — the adversarial-review exclusion

Read this when the walk-through reaches Step R and the `magpie-adversarial-review` plugin is installed.

The reviewer CLIs it runs (`codex`, `copilot`, `agy`, `pi`, `goose`, `grok`, `claude`)
need network access and read their own credentials (`~/.codex`,
`~/.copilot`, `~/.gemini/antigravity-cli`, `~/.pi/agent`, `~/.config/goose`, `~/.grok`, `~/.claude`), which this sandbox denies. The tool therefore
runs outside it, through one exclusion. It names `~/.claude/magpie/adversarial-review`,
a link the plugin's `SessionStart` hook points at the installed version every
session, never a `*` where the version sits: that would also match `uv`
options spliced in at that position, and run them outside the sandbox.

```jsonc
"sandbox": {
  "excludedCommands": [
    "uvx --from ~/.claude/magpie/adversarial-review adversarial-review *"
  ]
},
"permissions": {
  "deny": [
    // the tool runs unsandboxed, so the code it runs must not be editable
    // by the agent that calls it
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/**)",
    "Edit(~/.claude/magpie/**)"
  ]
}
```

**Do not add an `allow` for it.** Every run sends the change to other
model providers and costs money; the harness prompt is the gate, by design.

Tell the operator what the exclusion covers and what it does not:

- It matches only the single-line form, spelled with a literal `~` and an
  unquoted path. A pipe, `$(…)`, `&&`, a redirection, quotes, or an
  expanded home directory put the command back in the sandbox, where the
  reviewer CLIs fail to read their credentials and report `unavailable`.
- The `*` in the pattern can match more than a version directory — a path
  with `..` segments would still match. The prompt that every run keeps is
  the gate against that; read the path in it before approving.
- The tool refuses a `--body-file` or `diff:` file outside the repository
  or a temporary directory, so an approved run cannot be pointed at
  `~/.ssh` or a private checkout to send it to a model.
- Outside the sandbox the tool only runs each reviewer CLI in its own
  read-only mode, and writes nothing to the repository. `codex`'s
  read-only mode still reads files anywhere on the machine; see the tool's
  README for what that means for a machine that also holds a private
  checkout.
