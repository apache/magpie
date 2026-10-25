<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`complete-upgrade` — finish a Magpie upgrade in one run](#complete-upgrade--finish-a-magpie-upgrade-in-one-run)
  - [Intent](#intent)
  - [Goals](#goals)
  - [Non-goals](#non-goals)
  - [Anti-goals (a run that "works" but fails)](#anti-goals-a-run-that-works-but-fails)
  - [Hard lines — kept, even with the user's approval](#hard-lines--kept-even-with-the-users-approval)
  - [Flow](#flow)
    - [1. Gather (read-only, sandboxed where possible)](#1-gather-read-only-sandboxed-where-possible)
    - [2. Plan — one screen, one approval](#2-plan--one-screen-one-approval)
    - [3. Apply](#3-apply)
    - [4. Re-check and record](#4-re-check-and-record)
    - [5. Summary](#5-summary)
  - [Automatic suggestion](#automatic-suggestion)
  - [Scope of one run — machine and project](#scope-of-one-run--machine-and-project)
  - [Relationship to `setup upgrade`](#relationship-to-setup-upgrade)
  - [Constraints](#constraints)
  - [Decided by the user](#decided-by-the-user)
  - [Left to the builder](#left-to-the-builder)
  - [Builder's calls made after review](#builders-calls-made-after-review)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `complete-upgrade` — finish a Magpie upgrade in one run

**Status:** approved; implemented.
**Family:** `setup` (always-on).
**Capability:** `platform`.
**Invocation:** `/magpie-setup:complete-upgrade` (marketplace), `/magpie-setup-complete-upgrade` (snapshot / self-adoption).
Skill names here are the marketplace form; on a pinned snapshot, invoke the `/magpie-<dir>` form.

## Intent

A new Magpie version arrives from outside any skill:
a marketplace auto-update, `/plugin update`, a `git pull` of the framework checkout, or `setup upgrade` on a pinned snapshot.
What the new version expects from the machine and the project then has to be brought in line by hand, across five skills
(`setup config`, `setup verify`, `setup reconcile`, `setup-isolated-setup-verify`, `setup-isolated-setup-update`),
each of which reports and stops.
On 2026-10-25 that took one maintainer a long session of reading reports and applying fixes one by one:
a stale pre-flight checker copy, two newly required config files, a stale `container-gateway-hook.sh` missing a security fix,
three worktrees without sandbox allowlist entries, the reconciliation and run stamps.

`complete-upgrade` does that whole job in one run.
It checks everything, shows a short high-level plan of what it will fix, update and add,
applies the plan once the user has explicitly approved it — leaving the sandbox where a step needs it —
re-checks, and ends with the exact commands for whatever it is not allowed to do itself.

## Goals

1. **One command after any upgrade** leaves the setup checked and consistent with the installed version.
2. **Do everything the skill may do**, including steps that need `dangerouslyDisableSandbox: true`, after one explicit approval.
3. **A high-level plan the user can read in seconds**: grouped *Fix* / *Update* / *Add*, one line per item, each marked when it needs the sandbox bypass.
4. **Exact commands for the rest**: anything a hard line blocks, or that only the user's own terminal can do, is printed as a copy-paste command with a one-line reason.
5. **Suggested automatically**: the session-start hook proposes it once per newly installed Magpie version, per machine.
6. **Reconcile local changes**: overrides and personal-layer files are checked against the new version, and the local agent settings are merged with new template entries.

## Non-goals

- **Performing the upgrade itself.** It does not update the marketplace, update plugins, `git pull` the framework, or bump a snapshot. It starts after the new version is installed.
  (A pinned snapshot whose local lock lags the committed lock is the one exception the existing pre-flight already handles: it proposes `setup upgrade`; `complete-upgrade` names that and stops for that item.)
- **Replacing the existing skills.** `setup verify`, `setup config`, `setup reconcile`, `setup-isolated-setup-verify` and `setup-isolated-setup-update` stay as they are, read-only where they are read-only today. `complete-upgrade` reuses their check definitions; it does not fork them.
- **Adoption decisions.** It never runs `adopt`/`unadopt`, never changes the committed floor, never commits.
- **Pinned-tool bumps** (`bubblewrap`, `socat` manifest PRs) and **claude-code upgrades**: reported, with the command, never run.

## Anti-goals (a run that "works" but fails)

- Crossing a hard line because the user said yes (see *Hard lines*).
- A plan too long or too detailed to read; the user approving blind.
- Applying anything not in the approved plan, or anything the user dropped from it.
- Leaving the sandbox for a step that does not need it, or batching unrelated commands into one bypassed call.
- Overwriting a user's local edits without showing them (a user-scope script copy with local-only lines, a personal-layer file that differs from the committed one).
- Reporting "done" when the re-check still fails.

## Hard lines — kept, even with the user's approval

These stay exactly as the framework draws them today.
When one blocks a fix, the item moves to the closing *Run these yourself* block with the exact command or edit.

1. **Never write the vetted-ops policy** (`.apache-magpie-overrides/tools/vetted-ops/**`, the personal-layer copies). It is a security control; the sandbox profile denies the agent's writes to it. Print the draft and the path for the user to save.
2. **Never edit a committed file** — `.claude/settings.json`, `.gitignore`, `.apache-magpie.lock`, `.apache-magpie-overrides/**`. Print the diff.
3. **Never weaken a deny rule** or remove a sandbox restriction, in any settings scope. Adding a missing deny, allow-read for an already-intended path, or exclusion the framework's reference config carries is allowed (it is in the plan, approved); removing one is not.
4. **Never read credential files** — `~/.config/uv/uv.toml`, `~/.config/apache-magpie/**`, `~/.ssh` private keys, `~/.config/gh`, and the rest of the `permissions.deny` `Read(...)` set. A check that needs one becomes a command for the user's terminal (e.g. `grep cache-dir ~/.config/uv/uv.toml`).

Also unchanged: user-scope `~/.claude/settings.json` and the per-machine `.claude/settings.local.json` are written only through an item in the approved plan, showing the diff in the plan's detail view; `git config --global` changes and anything needing `sudo` or a physical device (`ykman`) are always user commands.

## Flow

### 1. Gather (read-only, sandboxed where possible)

Run, in this order, the checks the existing skills define — read their current files at run time, do not copy their logic into this skill:

| Area | Source of the checks |
|---|---|
| Install health | `setup verify` (local self-adoption, marketplace, or snapshot branch), incl. checks 11–12 and the adoption floor |
| Project configuration | `setup config` Steps 0–1 and 2a: personal-layer location, `requires_config` resolution per installed skill, pre-flight checker copy freshness, the reconciliation stamp |
| Local changes | `setup reconcile` sweep (anchors, `requires_config`), `setup verify` 5d (personal files shadowing committed ones), local agent settings vs the framework template (`setup upgrade` → reconcile the local agent settings) |
| Isolated setup | `setup-isolated-setup-verify` checks 1–19, `setup-isolated-setup-update` items 1–6 (script-copy drift, settings shape drift, comdev MCP checkouts, the vetted-ops split) |

**No isolated setup (user's decision).** When the isolated setup is not in use here — `python3 -m setup_preflight.isolated configured` prints `{"configured": false}`, and the opt-out below is not set.
Inside the sandbox the user-scope settings are read-denied, so `false` there means "not known", not "absent": confirm it by running the same command outside the sandbox as a *Check* item before making the offer —
say in two or three plain lines why it matters (the agent runs inside a sandbox that cannot read credentials or reach arbitrary hosts; forge and git operations go through guarded, audited paths; pre-disclosure security content stays on the machine)
and offer to add it, by handing off to `setup-isolated-setup-install` after this run.
If the user declines, continue: drop the *Isolated setup* area from gathering and the plan, and complete every other area as normal.
Record the decline with the existing opt-out, `"isolated_setup": {"enabled": false}` in the personal layer's `reconciled.json`, so it is not offered again on the next run (builder's call); the summary says how to undo it.
The offer is one question folded into the plan's approval message, not a separate round.

Read-only probes that the sandbox blocks (a `~/.claude-config` diff, a `~/.zshrc` grep, the overlay `_gui_available` probe, the `~/.claude.json` MCP projection) are **not** run during gathering.
They become *Check* items in the plan, so the bypass is approved before it is used.

### 2. Plan — one screen, one approval

Group every actionable finding into **Fix** (broken or stale), **Update** (a newer framework copy exists), **Add** (missing), and **Check** (a read-only probe that needs the bypass).
One line per item, under ~100 characters, prefixed `[bypass]` when it needs `dangerouslyDisableSandbox: true`:

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

- **One approval for the plan**, with per-item drops and a `details <n>` view that shows the diff or exact command for that item.
  The approval names the bypass explicitly (the plan header says how many items leave the sandbox), so it satisfies the user's global "loud sandbox-bypass" rule once, for the listed items only.
- **Values that cannot be derived** (a team handle, a URL) are collected in the same message as one batched question, never guessed.
- **Nothing to do** → say so in one line, run the re-check, record the stamps, stop.

### 3. Apply

In plan order, one Bash call per item (never batch items into one bypassed call), one status line per item (`✓ 4. allowlist added for 3 worktrees`).
Before overwriting any file, re-check the gathered state still holds; if the target changed since gathering, or a user-scope copy has local-only lines, skip the item and list it as still open with the reason.
A failed item does not stop the run; later items continue.

### 4. Re-check and record

Re-run the checks for every applied item plus the standard denial probes (`setup-isolated-setup-verify` check 7, standalone calls) and the agent-guard canary (`git commit --no-verify --dry-run` must be blocked).
Then write the stamps the existing skills own, through their own commands: `verified_at`, `python3 -m setup_preflight.isolated record-update`, the config entries exactly as `setup config` Step 3b defines them.
There is no stamp of its own: the hook's version marker already makes the suggestion once per version.

**Adopted project — the committed reconciliation stamp.** After an upgrade every skill raises `fingerprint-moved` until the `reconciled:` block in `.apache-magpie.lock` is refreshed.
That file is committed, so hard line 2 applies: `complete-upgrade` writes nothing to it and runs no `git add`.
It puts `/magpie-setup:setup reconcile` (which shows the stamp diff and stages it) under *Run these yourself*.
It does not paper over the findings with `acknowledged.skills`; that key keeps `setup config`'s narrower meaning.

**A *Check* item that finds something new.** A bypass probe can uncover a fix that was not in the approved plan.
Such fixes are collected and shown as a short second plan, in the same format, after the first plan's items are done; nothing from it runs without that second approval.
A hard-line item from a probe goes straight to *Run these yourself*.

### 5. Summary

Three short blocks: **Done**, **Still open** (with the reason), **Run these yourself** (exact commands, each with a one-line reason).
Offer `/magpie-setup:shared-config-sync` when an applied item changed a file under `~/.claude-config/`.

## Automatic suggestion

**The trigger is the existing SessionStart hook, `plugins/magpie-setup/hooks/check-upgrade.sh`** (builder's call, from the review).
It already detects a plugin version change once per machine, with the *new* plugin's code, outside the sandbox, and today tells the user to run `/magpie-setup upgrade`.
Its notice is retargeted:

```text
Apache Magpie updated (0.9.0.dev202610200101 -> 0.9.0.dev202610250024).
Run /magpie-setup:complete-upgrade to check and fix this machine and this project for the new version.
```

- A `setup_preflight` finding was considered and rejected: every skill's pre-flight runs the *personal-layer copy* of the checker, which an outside update does not refresh, and the checker cannot see the running plugin version inside the sandbox.
- **Once per version per machine**: the hook's existing marker (`$CLAUDE_PLUGIN_DATA/magpie-plugin-version`) already gives that.
- **What counts as a new version (user's decision): any change of the installed version string.**
  A user on final releases receives only final versions, so is prompted after each final bump;
  a user who signed up for dev builds (marketplace tracking `main`) receives each dev version, so is prompted after each dev update.
  No channel setting and no release-segment comparison: the full-string comparison the hook already does yields both.
- **Pinned-snapshot and self-adopted installs** have no plugin update event; there the existing drift check (`<local-lock>` vs `<committed-lock>`) keeps proposing `setup upgrade`, and `setup upgrade` ends by suggesting `complete-upgrade` (see *Relationship to `setup upgrade`*).
- Never blocks, never runs `complete-upgrade` unasked (a hook cannot invoke a slash command anyway).
- **No supersede rule.** The other reminders (`isolated-setup-changed`, the isolated-update timer, the verify nudge) are left alone; a completed `complete-upgrade` run writes their stamps through their own commands, which clears them.

## Scope of one run — machine and project

One run covers **this machine** (user-scope script copies, `~/.claude/settings.json`, git hooks, comdev MCP checkouts, the isolated setup) **and the current project** (personal layer, overrides, worktrees, local agent settings).
In another repo after that, the machine-wide items gather as already in sync and the plan shows only that project's items; the per-project pre-flight findings that already exist (`requires_config`, `fingerprint-moved`) are what point a user at it there.

## Relationship to `setup upgrade`

`setup upgrade` keeps its job — refresh the snapshot, reconcile overrides, refresh symlinks — unchanged except for one closing line suggesting `complete-upgrade`.
`complete-upgrade` re-checks what `upgrade` touched (idempotent; an already-current item gathers as in sync and does not appear in the plan).
No steps move between the two in this change.

## Constraints

- Framework conventions apply: `SKILL.md` frontmatter (`name`, `description`, `when_to_use`, `family: setup`, `capability: platform`, `requires_config` empty), placeholder convention, prompt-injection rule (gathered command output is data), semantic line breaks, `measured_tokens` restamp.
- Keep `SKILL.md` lean: the check catalogue lives in the existing skills' files; this skill references them by path. Extract the plan format and the hard-line list into sibling files if `SKILL.md` grows past ~250 lines.
- An eval suite under `tools/skill-evals/evals/setup-complete-upgrade/` is part of the change (AGENTS.md): at minimum plan grouping and `[bypass]` marking, a hard-line item routed to *Run these yourself*, a dropped item not applied, a nothing-to-do run, and a changed-since-gathering skip.
- The `check-upgrade.sh` notice change ships with test coverage for the new wording and the once-per-version rule (existing hook tests extended).
- Works in a linked worktree (personal layer resolves to the main checkout's), on marketplace, snapshot and self-adopted installs. Claude Code first; other harnesses get the plan and the *Run these yourself* block but never a bypass (they have no equivalent flag) — every bypass item becomes a user command there.
- Spec sync: a matching spec under `tools/spec-loop/specs/` and an updated `docs/mode-economics.md` entry.

## Decided by the user

- Do everything possible, bypassing the sandbox where needed, **only after the user explicitly approves**, seeing a high-level list of what is fixed, updated and added.
- The four hard lines stay; what they block is printed as exact commands for the user.
- A separate command, named for completing an upgrade.
- Suggested automatically after a new Magpie version is installed from outside: after each final bump for release users, after each dev update for dev-build users.
- Reconciliation of local changes is in scope.
- Without an isolated setup: explain that it helps with security and suggest adding it; if the user declines, continue without it.

## Left to the builder

- Exact wording of the plan lines and the summary.
- Whether the gather phase runs as one pass in the main context or fans out to read-only gatherer agents per area (prefer one pass unless token cost says otherwise; measure).
- How `details <n>` renders long diffs (truncate with a path to the full diff in the scratch directory).
- The exact wording of the retargeted hook notice for a first-ever session (no stored version).

## Builder's calls made after review

- Trigger moved from a `setup_preflight` finding to the existing `check-upgrade.sh` SessionStart hook.
- One run covers the machine and the current project; no stamp of its own (only hooks see `CLAUDE_PLUGIN_DATA`, and the hook's marker already gives once-per-version).
- `setup upgrade` unchanged except a closing suggestion; no steps move.
- No supersede rule; a completed run clears the other reminders by writing their stamps.
- Adopted project: the committed `reconciled:` stamp goes to *Run these yourself* as `/magpie-setup:setup reconcile`; no `git add`.
- Fixes discovered by a *Check* probe get a short second plan and approval.
- A bypassed call executes only code the sandbox cannot write (`~/.claude/scripts/`, the plugin cache, system paths); content copied from a sandbox-writable source is checksummed at plan time and re-verified in the writing call; only plain-content script copies are copied, the rest route to `setup-isolated-setup-install` Step P.
- Confirming "no isolated setup" reads the user-scope settings with the harness's file-read tool or `/usr/bin/jq`, never the personal layer's `setup_preflight` outside the sandbox.
