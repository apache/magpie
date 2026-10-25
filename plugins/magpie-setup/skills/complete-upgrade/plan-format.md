<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The plan — one screen, one approval

The plan [`SKILL.md` → Plan](SKILL.md#plan) shows.
The user should be able to read it in seconds and approve it knowingly.

## Layout

This is the canonical layout:

```text
complete-upgrade — Magpie 0.9.0.dev202610250024 (was 0.9.0.dev202610200101)

Fix
  1. [bypass] container-gateway-hook.sh is stale (missing #1804 hardening) → copy framework version
Update
  2. pre-flight checker in .apache-magpie-local/ → refresh from magpie-setup
Add
  3. mentoring-config.md (needed by mentor) → scaffold, 1 value to ask
  4. [bypass] sandbox allowlist for 3 worktrees → sandbox-add-project-root.sh --all-worktrees
Check
  5. [bypass] claude-iso sourced in ~/.zshrc → read-only grep

Run these yourself (blocked by a hard line) — shown again at the end
  • grep cache-dir ~/.config/uv/uv.toml   (credential file: absolute path outside ~/.cache expected)

Apply all? (yes / drop 2,5 / details 1 / no)
```

- **Header**: the installed version, and the previous one when known.
  Below it, one line saying how many items leave the sandbox, for example `3 of 5 items run outside the sandbox ([bypass]).`
  Omit that line when no item carries `[bypass]`.
- **Groups** in this order, each omitted when empty: **Fix**, **Update**, **Add**, **Check**.
- **Items** numbered across groups, one line each, under about 100 characters: what is wrong, an arrow, what will be done.
  Prefix `[bypass]` when the item needs `dangerouslyDisableSandbox: true`.
- **Paths** are named as they resolve: in a linked worktree a personal-layer item names the main checkout's `.apache-magpie-local/`, never a new one in the worktree.
- **Run these yourself** previews every hard-line or user-terminal command now, so nothing in the closing summary is a surprise.
  Render each as [`hard-lines.md`](hard-lines.md) describes.
- **Still open** (optional, before the approval line): items Gather found but will not offer, with their reason.
  A user-scope script copy with local-only lines goes here with its diff path, never into *Update*.

## Classification

| Group | Put an item here when |
|---|---|
| **Fix** | Something is broken or stale: a copy missing a framework fix, a hook pointing at a missing file, a config that no longer resolves. |
| **Update** | A newer framework copy exists for something that still works: the pre-flight checker, a script copy, a settings template entry. |
| **Add** | Something the installed version needs is missing: a required config file, an allowlist entry, a hook, the `setup config` run on an unconfigured repo. |
| **Check** | A read-only probe that needs the bypass to run at all: a `~/.zshrc` grep, a `~/.claude-config` diff, the overlay `_gui_available` probe, the `~/.claude.json` MCP projection, the out-of-sandbox `setup_preflight.isolated configured` confirmation. |

A *Check* item reads only.
What it finds is handled by the second plan in [`SKILL.md` → Apply](SKILL.md#apply).

On a harness with no sandbox bypass (Codex, Gemini CLI, Copilot CLI), every item that would carry `[bypass]` is listed under *Run these yourself* instead, as the exact command, and the header line counts none.

## Approval grammar

```text
yes                 apply every item
drop 2,5            apply all but items 2 and 5 (asks again, showing the reduced plan)
details 1           show item 1's diff or exact command, then ask again
no                  apply nothing
```

`details <n>` shows a long diff truncated, with the path of the full diff in the scratch directory.
The approval names the bypass explicitly through the header line, so one `yes` satisfies the loud sandbox-bypass rule for the listed `[bypass]` items only.

## Questions in the same message

- **Values that cannot be derived** (a team handle, a URL) are asked as one batched, numbered question below the plan, never guessed.
  An item waiting for a value says `N values to ask` on its line.
- **The isolated-setup offer**, when it applies, is one more question in the same message: the two or three lines of why, and whether to run `setup-isolated-setup-install` after this run.
  A decline is recorded as [`SKILL.md` → Gather](SKILL.md#gather) describes.
- **`setup adopt`**, when Magpie is not configured here, appears as one information line only, never as an item.

## Nothing to do

When Gather finds nothing actionable and nothing for *Run these yourself*:

```text
complete-upgrade — Magpie 0.9.0.dev202610250024: this machine and this project are already in line.
```

Then run the re-check, record the stamps, and stop.
