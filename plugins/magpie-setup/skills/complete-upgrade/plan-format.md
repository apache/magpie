<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The plan — one screen, one approval

The plan [`SKILL.md` → Plan](SKILL.md#plan) shows.
The user should be able to read it in seconds and approve it knowingly.

## Layout

This is the canonical layout:

```text
complete-upgrade — Magpie 0.9.0.dev202610250024 (was 0.9.0.dev202610200101)
!!! 3 of 5 items leave the sandbox: 1, 4, 5 !!!

Fix
  1. [bypass] container-gateway-hook.sh is stale (missing #1804 hardening) → copy framework version
Update
  2. pre-flight checker in .apache-magpie-local/ → refresh from magpie-setup
Add
  3. mentoring-config.md (needed by mentor) → scaffold, 1 value to ask
  4. [bypass] sandbox allowlist for 3 worktrees → ~/.claude/scripts/sandbox-add-project-root.sh --all-worktrees
Check
  5. [bypass] claude-iso sourced in ~/.zshrc → read-only grep

Run these yourself (blocked by a hard line) — shown again at the end
  • grep cache-dir ~/.config/uv/uv.toml   (credential file: absolute path outside ~/.cache expected)

Apply all? (yes / drop 2,5 / details 1 / no)
```

- **Header**: the installed version, and the previous one when known.
  Below it, one loud line counting and listing the items that leave the sandbox, for example `!!! 3 of 5 items leave the sandbox: 1, 4, 5 !!!`.
  Omit that line when no item carries `[bypass]`.
- **Groups** and the `[bypass]` rule are defined in [`SKILL.md` → Plan](SKILL.md#plan); each group is omitted when empty.
- **Items** are one line each: what is wrong, an arrow, what will be done.
- **What a `[bypass]` item executes** comes only from locations the sandbox cannot write: `~/.claude/scripts/` (literal `~`), the plugin cache under `~/.claude/plugins/`, and system paths.
  Never the checkout (including `tools/…`), the snapshot `.apache-magpie/`, the personal layer, `~/.cache/…` (including `~/.cache/apache-magpie/framework/current`), or the scratch directory.
- **Copied content** (a framework script copy, a merged settings file prepared in the scratch directory) shows the SHA-256 recorded at plan time under `details <n>`; the one bypassed call that writes it re-verifies that checksum first, and a mismatch skips the item as `changed`.
- **Script copies**: only a plain-content copy from [`script-inventory.md`](../isolated-setup-update/script-inventory.md) is an item; a symlinked entry, a git-hook flavour, the two Python packages or `guards.d` go to *Run these yourself* as "re-run `setup-isolated-setup-install` Step P".
- **A `[bypass]` target the sandbox cannot read** (such as `~/.claude/settings.json`) is compared and written in one bypassed call; `details <n>` names its post-apply re-check, one bypassed read under the same approval.
  A target Gather could not read starts as a *Check* item, never a *Fix*.
- **Settings items** target only each worktree's `.claude/settings.local.json` or the user-scope `~/.claude/settings.json`, and show their unified diff under `details <n>`.
  They add only entries copied verbatim from `tools/agent-isolation/claude-settings.local.template.json` or the framework `.claude/settings.json`, or written by the helper that owns the write; never a value taken from gathered text.
  A change to the committed `.claude/settings.json` is never an item; it goes to *Run these yourself* as a diff.
- **A lagging pinned snapshot** (local lock behind the committed lock) is never a *Fix* item; it goes to *Run these yourself* as `/magpie-setup:setup upgrade`.
- **Paths** are named as they resolve: in a linked worktree a personal-layer item names the main checkout's `.apache-magpie-local/`, never a new one in the worktree.
  Such a write needs no `[bypass]` when it is inside the gathered write scope.
- **Run these yourself** previews every hard-line or user-terminal command now, so nothing in the closing summary is a surprise.
  Render each as [`hard-lines.md`](hard-lines.md) describes.
- **Not offered** (optional): a deny weakening or removed sandbox restriction, with its reason and no command.
- **Still open** (optional, before the approval line): items Gather found but will not offer, with their reason; after Apply it also holds items skipped there (dropped, changed, failed).
  A hard-line item is never here.
  A user-scope script copy with local-only lines goes here with its diff path, never into *Update*.

## Classification

The groups and the first-match-wins rule that assigns items to them are in [`SKILL.md` → Plan](SKILL.md#plan).
Examples of a *Check* item: a `~/.zshrc` grep, a `~/.claude-config` diff, the overlay `_gui_available` probe, the `~/.claude.json` MCP projection, the out-of-sandbox read of the user-scope settings that confirms no isolated setup (harness file-read tool or `/usr/bin/jq`, never the personal layer's `setup_preflight`).

A *Check* item reads only.
What it finds is handled by the second plan in [`SKILL.md` → Apply](SKILL.md#apply).

On a harness with no sandbox bypass (Codex, Gemini CLI, Copilot CLI), every item that would carry `[bypass]` is listed under *Run these yourself* instead, as the exact command, and the header line counts none.

## Approval grammar

```text
yes                 apply every item
drop 2,5            apply every other item immediately (part of the one approval, no extra round)
details 1           show item 1's diff or exact command, then ask again
no                  apply nothing, write no stamps
```

`details <n>` shows a long diff truncated, with the path of the full diff in the scratch directory.
The approval names the bypass explicitly through the header line, so one `yes` satisfies the loud sandbox-bypass rule for the listed `[bypass]` items only.

## Questions in the same message

- **Values that cannot be derived** (a team handle, a URL) are asked as one batched, numbered question below the plan, never guessed.
  An item waiting for a value says `N values to ask` on its line.
- **The isolated-setup offer**, when it applies, is one more question in the same message: the two or three lines of why, and whether to run `setup-isolated-setup-install` after this run.
  A decline is recorded as [`SKILL.md` → Gather](SKILL.md#gather) describes.
  A decline given in the same reply as the approval wins: every *Isolated setup* area item is dropped.
- **`setup adopt`**, when Magpie is not configured here, appears as one information line only, never as an item.

## Nothing to do

When there is nothing actionable, as [`SKILL.md` → Plan](SKILL.md#plan) defines it:

```text
complete-upgrade — Magpie 0.9.0.dev202610250024: this machine and this project are already in line.
```

Then run the re-check, record the stamps, and stop.
