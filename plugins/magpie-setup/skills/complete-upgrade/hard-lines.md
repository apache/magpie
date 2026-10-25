<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hard lines and *Run these yourself*

These lines stay exactly as the framework draws them, even when the user approves an item that would cross one.
A blocked item never runs; it is rendered under *Run these yourself*, in the plan preview and again in the summary, with a one-line reason.

## The four hard lines

### 1. Never write the vetted-ops policy

Covers `.apache-magpie-overrides/tools/vetted-ops/**` and the personal-layer copies.
It is a security control, and the sandbox profile denies the agent's writes to it.

Render: the drafted policy written to the scratch directory, and the target path to save it to.

```text
• save <scratch>/vetted-ops-policy.toml as <target path>   (vetted-ops policy: the agent never writes it)
```

### 2. Never edit a committed file

Covers `.claude/settings.json`, `.gitignore`, `.apache-magpie.lock` and `.apache-magpie-overrides/**`.

Render: the unified diff written to the scratch directory, and the command to apply it.

```text
• git apply <scratch>/settings-json.diff   (committed file: review, apply and commit it yourself)
```

The per-machine `.claude/settings.local.json` (each worktree's) and the user-scope `~/.claude/settings.json` are not committed files: they can be plan items, marked `[bypass]` with their diff under `details <n>`, as [`SKILL.md` → Apply](SKILL.md#apply) describes.
If the harness refuses such a write, the item renders here as the copy command:

```text
• cp <scratch>/settings.local.json <worktree>/.claude/settings.local.json   (harness refused the approved settings write)
```

The committed reconciliation stamp in `.apache-magpie.lock` is rendered as `/magpie-setup:setup reconcile`, which shows the stamp diff and stages it.

### 3. Never weaken a deny rule or remove a sandbox restriction

Any settings scope.
Adding a missing deny, an allow-read for an already-intended path, or an exclusion the framework's reference config carries is allowed as a plan item; removing or loosening one is not.

Render: refused with the reason, and no command.

```text
• not offered: <rule> would be removed from <file>   (weakens a sandbox restriction)
```

### 4. Never read credential files

Covers `~/.config/uv/uv.toml`, `~/.config/apache-magpie/**`, `~/.ssh` private keys, `~/.config/gh`, and the rest of the `permissions.deny` `Read(...)` set.
A check that needs one is never a *Check* item, bypass or not.

Render: the command for the user's own terminal, and what its output should show.

```text
• grep cache-dir ~/.config/uv/uv.toml   (credential file: absolute path outside ~/.cache expected)
```

## Always the user's commands

These are never run by the agent, whatever the plan says; each is printed with its reason:

- `git config --global …` changes.
- Anything needing `sudo`.
- Anything needing a physical device, such as `ykman`.
- A claude-code upgrade: `npm install -g --no-save @anthropic-ai/claude-code@latest`.
- A plugin or marketplace update, a framework `git pull`, or a snapshot bump (`/magpie-setup:setup upgrade`).
- Pinned-tool bumps (`bubblewrap`, `socat`): a manifest PR, never run here.
- On a harness with no sandbox bypass, every item that would carry `[bypass]`.
