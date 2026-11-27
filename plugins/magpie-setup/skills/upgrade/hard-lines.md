<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hard lines and *Run these yourself*

These lines stay exactly as the framework draws them, even when the user approves an item that would cross one.
A blocked item never runs; it is rendered under *Run these yourself* (a deny weakening under *Not offered*), in the plan preview and again in the summary, with a one-line reason.
A hard-line item is never under *Still open*.

## The four hard lines

### 1. Never write the vetted-ops policy

Covers `.apache-magpie-overrides/tools/vetted-ops/**` and the personal-layer copies.
It is a security control, and the sandbox profile denies the agent's writes to it.

Render: the drafted policy written to the scratch directory, and the target path to save it to.
A caller grant finding (reconcile check 3a) adds only what the README example lists, as the minimal diff, also written to the scratch directory.

```text
• save <scratch>/vetted-ops-policy.toml as <target path>   (vetted-ops policy: the agent never writes it)
    adds git-fetch, git-worktree-add, … to "pr-management-shepherd"; diff: <scratch>/vetted-ops-policy.diff
```

When the policy is committed (`.apache-magpie-overrides/tools/vetted-ops/config.toml`), the change also lands through the project's review, as hard line 2 says.

**Re-approval.** The write entry points act only on a byte-for-byte copy in `~/.config/apache-magpie/vetted-ops/`, which the agent can neither read nor write.
When `vetted-op-read approval-status` reports `"approved": false`, or a grant change above was just drafted, render the user's copy command with the paths it printed, the policy path single-quoted:

```text
• review the policy's diff since your last approval first, then:
  mkdir -p ~/.config/apache-magpie/vetted-ops && cp '<policy>' ~/.config/apache-magpie/vetted-ops/<project>.toml   (stale approved copy: writes are refused until you re-approve)
```

Render `<project>` as the concrete name, never the placeholder: the project's slug, `short_name` in `project.md` lowercased, else the main checkout's basename ([the naming rule](../../../../tools/vetted-ops/README.md#configuration)).
Add one line: an earlier approved copy under another name approves nothing now, so the user may delete it.
A missing operator `[git]` table is not this skill's finding: `vetted-op-git` reports it in its own refusal.

### 2. Never edit a committed file

Covers `.claude/settings.json`, `.gitignore`, `.apache-magpie.lock` and `.apache-magpie-overrides/**`.

Render: the unified diff written to the scratch directory, and the command to apply it.

```text
• git apply <scratch>/settings-json.diff   (committed file: review, apply and commit it yourself)
```

The per-machine `.claude/settings.local.json` (each worktree's) and the user-scope `~/.claude/settings.json` are not committed files: they can be plan items, marked `[bypass]` with their diff under `details <n>`, as [`SKILL.md` → Apply](SKILL.md#apply) describes.
Such an item adds only entries copied verbatim from the framework template or reference config, or written by the helper that owns the write.
If the harness refuses such a write, the item renders here as the copy command:

```text
• cp <scratch>/settings.local.json <worktree>/.claude/settings.local.json   (harness refused the approved settings write)
```

The committed reconciliation stamp in `.apache-magpie.lock` is rendered as `/magpie-setup:setup reconcile`, which shows the stamp diff and stages it.

### 3. Never weaken a deny rule or remove a sandbox restriction

Any settings scope.
Adding a missing deny, an allow-read for an already-intended path, or an exclusion the framework's reference config carries is allowed as a plan item; removing or loosening one is not.

Render: on a separate *Not offered* line, not under *Run these yourself*, with the reason and no command.

```text
Not offered
  • <rule> would be removed from <file>   (weakens a sandbox restriction)
```

### 4. Never read credential files

Covers `~/.config/uv/uv.toml`, `~/.config/apache-magpie/**`, `~/.ssh` private keys, `~/.config/gh`, and the rest of the `permissions.deny` `Read(...)` set.
A check that needs one is never a *Check* item, bypass or not.

Render: the command for the user's own terminal, and what its output should show.

```text
• grep cache-dir ~/.config/uv/uv.toml   (credential file: absolute path outside ~/.cache expected)
```

## Bypassed calls run only code the sandbox cannot write

Not a fifth hard line, but held as firmly: see [`SKILL.md` → Golden rules](SKILL.md#golden-rules).
A command that cannot meet it renders here:

```text
• re-run setup-isolated-setup-install Step L   (not a plain-content script copy: the container_gateway package)
```

## Always the user's commands

These are never run by the agent, whatever the plan says; each is printed with its reason:

- `git config --global …` changes.
- Anything needing `sudo`.
- Anything needing a physical device, such as `ykman`.
- A claude-code upgrade: `npm install -g --no-save @anthropic-ai/claude-code@latest`.
- A plugin or marketplace update, a framework `git pull`, or a snapshot bump (`/magpie-setup:setup update`).
- Pinned-tool bumps (`bubblewrap`, `socat`): a manifest PR, never run here.
- On a harness with no sandbox bypass, every item that would carry `[bypass]`.
