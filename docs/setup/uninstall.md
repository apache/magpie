<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Removing Magpie from an adopter repo (uninstall)](#removing-magpie-from-an-adopter-repo-uninstall)
  - [Quick removal](#quick-removal)
  - [Invocation](#invocation)
  - [What you'll be asked to confirm](#what-youll-be-asked-to-confirm)
  - [Verifying the removal](#verifying-the-removal)
  - [What remains after uninstall — and how to remove it](#what-remains-after-uninstall--and-how-to-remove-it)
    - [`.apache-magpie-overrides/`](#apache-magpie-overrides)
    - [Symlinks pointing outside the snapshot](#symlinks-pointing-outside-the-snapshot)
    - [`post-checkout` hook with extra logic](#post-checkout-hook-with-extra-logic)
    - [Overlapping `.gitignore` entries](#overlapping-gitignore-entries)
    - [Outside-the-repo state](#outside-the-repo-state)
  - [Setting the framework back up later](#setting-the-framework-back-up-later)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Removing Magpie from an adopter repo (uninstall)

> [!IMPORTANT]
> **Skill names differ on this install.** Installed from the pinned snapshot
> (or self-adoption), a skill is invoked as a **single token** —
> `/magpie-security-issue-triage` — not `/magpie-security:issue-triage`. There
> is no plugin namespace here; the `magpie-` prefix *is* the namespace, and the
> name is the skill's directory name. Magpie's other docs show the
> marketplace form; see
> [Skill names differ by install method](marketplace.md#skill-names-differ-by-install-method).
>
> The skill listing (Claude Code's `/` menu) also shows the **shorter** frontmatter
> name beside it — `issue-triage` — as a display label; what you type is still
> the single-token command.

If your project has decided to stop using Magpie,
or the adoption was experimental and is now over, this
page walks through the removal. It reverses everything an
install recipe in [`install-recipes.md`](../quick-start/other-install-methods.md)
and the subsequent `/magpie-setup` interactive flow put
into your repo.

> **You may not actually want this.** To **change install
> method or version**, use
> [`/magpie-setup upgrade`](../../skills/setup/upgrade.md)
> — it keeps your overrides and re-uses the existing
> wiring. To **temporarily detach a single skill for
> debugging**, edit the relevant file under
> `.apache-magpie-overrides/` instead.

## Quick removal

If you've already decided and want to act fast — from the
main checkout of the adopter repo:

```bash
/magpie-setup uninstall    # surfaces a plan, asks for confirmation, then removes
```

Read on for prerequisites, what the confirmation prompt
looks like, how to verify, and how to clean up what
`uninstall` deliberately leaves behind.

## Invocation

```bash
/magpie-setup uninstall              # default: preserves .apache-magpie-overrides/
/magpie-setup uninstall --purge-overrides
/magpie-setup uninstall dry-run      # print the plan; no writes, no confirmation
```

The flow refuses to run inside `apache/magpie`
itself (the framework is not its own adopter).

## What you'll be asked to confirm

Before any write, the flow surfaces a single plan and asks
for one explicit confirmation. The default selection is
**abort**, not proceed. Each item appears only when
present in your repo. The plan looks like:

```text
The following will be REMOVED:

  Gitignored (no commit needed):
    .apache-magpie/                          (snapshot)
    .apache-magpie.local.lock
    .agents/skills/magpie-<skill-1>          → .apache-magpie/skills/<skill-1>/   (canonical)
    .claude/skills/magpie-<skill-1>          → ../../.agents/skills/magpie-<skill-1>   (relay)
    .github/skills/magpie-<skill-1>          → ../../.agents/skills/magpie-<skill-1>   (relay)
    .git/hooks/post-checkout                  (if it contains the Magpie recipe)

  Committed (will show in `git status`):
    .gitignore                                (the Magpie entries)
    README.md                                 (the adoption section, if present)
    AGENTS.md                                 (the Magpie framework section, if present)
    CONTRIBUTING.md                           (the adoption section, if present)
    .agents/skills/magpie-setup/             (this skill itself — self-destructive; canonical copy)
    .claude/skills/magpie-setup              (relay symlink)
    .github/skills/magpie-setup              (relay symlink)

The following will be PRESERVED:

    .apache-magpie.lock                      (the project's committed floor; belongs to `unadopt`, not `uninstall`)
    .apache-magpie-overrides/                (pass `--purge-overrides` to remove)
```

The framework wires every skills dir the same way per the
[agent-target registry](../../skills/setup/agents.md):
`.agents/skills/` holds the canonical `magpie-*` links into the
snapshot; `.claude/skills/` and `.github/skills/` (and any
holdout) hold relays into `.agents/skills/`. `uninstall` removes the
`magpie-*` entries from every one of them. The skills
directories themselves are adopter-owned and are **not** removed.

If `--purge-overrides` is passed, `.apache-magpie-overrides/`
moves into the *removed* section with its files listed
explicitly. If any uncommitted edits exist under it, the
flow warns and asks for a second confirmation.

Removal is destructive on disk and on the git index.

## Verifying the removal

After the flow finishes, confirm the result:

```bash
git status                       # staged deletions / modifications
git diff --cached                # review patches before committing
ls .apache-magpie 2>/dev/null   # should print nothing — directory gone
```

You should see staged deletions for
your `setup/` skill directory, and modifications
to `.gitignore` plus any of `README.md` / `AGENTS.md` /
`CONTRIBUTING.md` that had adoption sections. Pay extra
attention to the `.gitignore` and doc patches — those are
the lines most likely to need a human re-read before
committing. On disk, `.apache-magpie/` and
`.apache-magpie.local.lock` should no longer exist, but
`.apache-magpie.lock` should still be there, unchanged: this flow
leaves the project's committed floor alone. Removing the floor
itself is [`unadopt`](../../skills/setup/adopt.md#unadopt), a
different operation with a different blast radius.

If anything is missing or unexpected — or if removal failed
partway through — the canonical per-step plan, including
failure modes, lives in
[`.claude/skills/magpie-setup/uninstall.md`](../../skills/setup/uninstall.md).
That's the procedure the agent steps through when you
invoke `/magpie-setup uninstall`.

## What remains after uninstall — and how to remove it

`uninstall` only deletes content the install flow itself
installed. Anything you authored, or anything that
overlapped with the framework's footprint but predates the
adoption, is preserved on purpose.

### `.apache-magpie-overrides/`

Your hand-written customisations: any per-skill overrides
you filled in (e.g. `pr-management-triage.md`) and, if you
used the fallback location instead of the recommended
per-user one, a project-local `user.md` carrying identity
and tool-picks (governance membership, local clone paths, etc.).
Preserved because the content is yours, not the
framework's. Remove with:

```bash
git rm -r .apache-magpie-overrides/
```

Or use `/magpie-setup uninstall --purge-overrides` to do
this in one step.

### Symlinks pointing outside the snapshot

If `uninstall` flagged a symlink under your skills directory
that resolved **outside** the framework snapshot — i.e.
you wired up something extra at the same name post-
adoption — it was left in place. Inspect and remove if no
longer useful:

```bash
ls -l .claude/skills/    # find the flagged symlink(s)
rm .claude/skills/<name>
```

### `post-checkout` hook with extra logic

If your `.git/hooks/post-checkout` contained anything
beyond the Magpie `verify --auto-fix-symlinks` recipe,
`uninstall` left the entire hook in place and told you which
line to delete. Edit it by hand:

```bash
$EDITOR .git/hooks/post-checkout
```

### Overlapping `.gitignore` entries

`uninstall` removes only the exact lines from the install
template. If you had unrelated rules referencing
`.apache-magpie/` (e.g. a custom path under the snapshot
dir), they remain. Audit and clean manually:

```bash
grep apache-magpie .gitignore
```

### Outside-the-repo state

`uninstall` only touches your adopter repo. None of the
following are removed — retire each one only if you are
also retiring Magpie from this machine entirely:

- **`~/.config/apache-magpie/user.md`** — the recommended
  per-user identity / tool-picks config. One file, shared
  across every adopter repo on this machine. If you still
  use Magpie in any other repo, leave it.
  Otherwise:

  ```bash
  rm -i ~/.config/apache-magpie/user.md
  rmdir ~/.config/apache-magpie 2>/dev/null    # only removes the dir if empty (errors silenced)
  ```

- **`~/.claude/` user-scope config, hooks, and settings** —
  not framework-owned. Includes anything
  `setup-shared-config-sync` pushed to your private sync
  repo, which has its own lifecycle.
- **Framework checkout** — your local clone of
  `apache/magpie` from `setup-isolated-setup-install`.
  Remove with `rm -rf <path-to-clone>` if no longer needed.
- **Per-user state from skills that wrote outside this
  repo** — consult each skill's docs.

## Setting the framework back up later

Because uninstalling deletes the `setup` skill
itself, future `/magpie-setup` invocations resolve to
nothing. To set the framework back up, re-run an install recipe in
[`install-recipes.md`](../quick-start/other-install-methods.md) — the same path
a first-time adopter takes.

## See also

- [`docs/setup/README.md`](README.md) — the setup skill
  family overview (verify, upgrade, shared-config sync).
- [Top-level README — Install](../../README.md#install)
  — the original 3-step bootstrap.
- [`install-recipes.md`](../quick-start/other-install-methods.md) — the
  counterpart to this page.
- Report issues against the framework repo at
  [apache/magpie](https://github.com/apache/magpie/issues).
