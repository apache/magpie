<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Removing apache-steward from an adopter repo (unadopt)](#removing-apache-steward-from-an-adopter-repo-unadopt)
  - [Quick removal](#quick-removal)
  - [Invocation](#invocation)
  - [What you'll be asked to confirm](#what-youll-be-asked-to-confirm)
  - [Verifying the removal](#verifying-the-removal)
  - [What remains after unadopt — and how to remove it](#what-remains-after-unadopt--and-how-to-remove-it)
    - [`.apache-steward-overrides/`](#apache-steward-overrides)
    - [Symlinks pointing outside the snapshot](#symlinks-pointing-outside-the-snapshot)
    - [`post-checkout` hook with extra logic](#post-checkout-hook-with-extra-logic)
    - [Overlapping `.gitignore` entries](#overlapping-gitignore-entries)
    - [Outside-the-repo state](#outside-the-repo-state)
  - [Re-adopting later](#re-adopting-later)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Removing apache-steward from an adopter repo (unadopt)

If your project has decided to stop using apache-steward,
or the adoption was experimental and is now over, this
page walks through the removal. It reverses everything an
install recipe in [`install-recipes.md`](install-recipes.md)
and the subsequent `/setup-steward` interactive flow put
into your repo.

> **You may not actually want this.** To **change install
> method or version**, use
> [`/setup-steward upgrade`](../../.claude/skills/setup-steward/upgrade.md)
> — it keeps your overrides and re-uses the existing
> wiring. To **temporarily detach a single skill for
> debugging**, edit the relevant file under
> `.apache-steward-overrides/` instead.

## Quick removal

If you've already decided and want to act fast — from the
main checkout of the adopter repo:

```bash
/setup-steward unadopt    # surfaces a plan, asks for confirmation, then removes
```

Read on for prerequisites, what the confirmation prompt
looks like, how to verify, and how to clean up what
`unadopt` deliberately leaves behind.

## Invocation

```bash
/setup-steward unadopt              # default: preserves .apache-steward-overrides/
/setup-steward unadopt --purge-overrides
/setup-steward unadopt dry-run      # print the plan; no writes, no confirmation
```

The flow refuses to run inside `apache/airflow-steward`
itself (the framework is not its own adopter).

## What you'll be asked to confirm

Before any write, the flow surfaces a single plan and asks
for one explicit confirmation. The default selection is
**abort**, not proceed. Each item appears only when
present in your repo. The plan looks like:

```text
The following will be REMOVED:

  Gitignored (no commit needed):
    .apache-steward/                          (snapshot)
    .apache-steward.local.lock
    <skills-dir>/<symlink-1>                  → .apache-steward/.claude/skills/<skill-1>/
    <skills-dir>/<symlink-2>                  → ...
    .github/skills/<symlink-1>                (Pattern B only — second physical layer)
    .git/hooks/post-checkout                  (if it contains the steward recipe)

  Committed (will show in `git status`):
    .apache-steward.lock                      (your project's pin)
    .gitignore                                (the steward entries)
    README.md                                 (the adoption section, if present)
    AGENTS.md                                 (the apache-steward framework section, if present)
    CONTRIBUTING.md                           (the adoption section, if present)
    <skills-dir>/setup-steward/               (this skill itself — self-destructive)

The following will be PRESERVED:

    .apache-steward-overrides/                (pass `--purge-overrides` to remove)
```

`<skills-dir>` resolves to your skills directory per the
[skills-dir convention](../../.claude/skills/setup-steward/conventions.md)
your repo uses:

- **Pattern A** — `.claude/skills/`.
- **Pattern B** — both `.claude/skills/` and `.github/skills/`
  (one physical symlink per layer).
- **Pattern D** — the canonical side only (D.1:
  `.github/skills/`; D.2: `.claude/skills/`). The directory
  symlink itself is adopter-owned and is **not** removed by
  unadopt.

If `--purge-overrides` is passed, `.apache-steward-overrides/`
moves into the *removed* section with its files listed
explicitly. If any uncommitted edits exist under it, the
flow warns and asks for a second confirmation.

Removal is destructive on disk and on the git index.

## Verifying the removal

After the flow finishes, confirm the result:

```bash
git status                       # staged deletions / modifications
git diff --cached                # review patches before committing
ls .apache-steward 2>/dev/null   # should print nothing — directory gone
```

You should see staged deletions for `.apache-steward.lock`,
your `setup-steward/` skill directory, and modifications
to `.gitignore` plus any of `README.md` / `AGENTS.md` /
`CONTRIBUTING.md` that had adoption sections. Pay extra
attention to the `.gitignore` and doc patches — those are
the lines most likely to need a human re-read before
committing. On disk, `.apache-steward/` and
`.apache-steward.local.lock` should no longer exist.

If anything is missing or unexpected — or if removal failed
partway through — the canonical per-step plan, including
failure modes, lives in
[`.claude/skills/setup-steward/unadopt.md`](../../.claude/skills/setup-steward/unadopt.md).
That's the procedure the agent steps through when you
invoke `/setup-steward unadopt`.

## What remains after unadopt — and how to remove it

`unadopt` only deletes content the adopt flow itself
installed. Anything you authored, or anything that
overlapped with the framework's footprint but predates the
adoption, is preserved on purpose.

### `.apache-steward-overrides/`

Your hand-written customisations: any per-skill overrides
you filled in (e.g. `pr-management-triage.md`) and, if you
used the fallback location instead of the recommended
per-user one, a project-local `user.md` carrying identity
and tool-picks (PMC status, local clone paths, etc.).
Preserved because the content is yours, not the
framework's. Remove with:

```bash
git rm -r .apache-steward-overrides/
```

Or use `/setup-steward unadopt --purge-overrides` to do
this in one step.

### Symlinks pointing outside the snapshot

If `unadopt` flagged a symlink under your skills directory
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
beyond the steward `verify --auto-fix-symlinks` recipe,
`unadopt` left the entire hook in place and told you which
line to delete. Edit it by hand:

```bash
$EDITOR .git/hooks/post-checkout
```

### Overlapping `.gitignore` entries

`unadopt` removes only the exact lines from the adopt
template. If you had unrelated rules referencing
`.apache-steward/` (e.g. a custom path under the snapshot
dir), they remain. Audit and clean manually:

```bash
grep apache-steward .gitignore
```

### Outside-the-repo state

`unadopt` only touches your adopter repo. None of the
following are removed — retire each one only if you are
also retiring apache-steward from this machine entirely:

- **`~/.config/apache-steward/user.md`** — the recommended
  per-user identity / tool-picks config. One file, shared
  across every adopter repo on this machine. If you still
  use apache-steward in any other repo, leave it.
  Otherwise:

  ```bash
  rm -i ~/.config/apache-steward/user.md
  rmdir ~/.config/apache-steward 2>/dev/null    # only removes the dir if empty (errors silenced)
  ```

- **`~/.claude/` user-scope config, hooks, and settings** —
  not framework-owned. Includes anything
  `setup-shared-config-sync` pushed to your private sync
  repo, which has its own lifecycle.
- **Framework checkout** — your local clone of
  `apache/airflow-steward` from `setup-isolated-setup-install`.
  Remove with `rm -rf <path-to-clone>` if no longer needed.
- **Per-user state from skills that wrote outside this
  repo** — consult each skill's docs.

## Re-adopting later

Because unadoption deletes the `setup-steward` skill
itself, future `/setup-steward` invocations resolve to
nothing. To re-adopt, re-run an install recipe in
[`install-recipes.md`](install-recipes.md) — the same path
a first-time adopter takes.

## See also

- [`docs/setup/README.md`](README.md) — the setup skill
  family overview (verify, upgrade, shared-config sync).
- [Top-level README — Adopting the framework](../../README.md#adopting-the-framework)
  — the original 3-step bootstrap.
- [`install-recipes.md`](install-recipes.md) — the
  counterpart to this page.
- Report issues against the framework repo at
  [apache/airflow-steward](https://github.com/apache/airflow-steward/issues).
