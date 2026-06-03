<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# upgrade — one-time pre-Magpie → Magpie migration

You reached this file because a pre-Magpie `/setup-steward upgrade`
refreshed the framework snapshot and reloaded the committed skill
in-flight (its Golden rule 9), and the refreshed framework ships this
migration shim at the legacy `.claude/skills/setup-steward/` path. Run
the migration below **once**. It is idempotent and every mutating step
is surfaced before it runs.

The snapshot has already been re-fetched by the pre-Magpie upgrade and
is the **new Magpie framework**, but it still sits at the old path
`.apache-steward/` and the rest of the repo still uses the old names.
The migration renames everything to the Magpie layout and then removes
this shim.

## Step 0 — Confirm this is a pre-Magpie repo and show the plan

Detect the legacy state. Treat the repo as pre-Magpie if **any** of
these exist:

- `.apache-steward.lock` (committed legacy pin)
- `.apache-steward/` (legacy snapshot dir)
- `.apache-steward-overrides/` (legacy overrides dir)
- `<adopter-skills-dir>/setup-steward/` (committed legacy bootstrap skill)
- a framework symlink in `<adopter-skills-dir>` **without** the
  `magpie-` prefix (e.g. `security-issue-import`, `pr-management-triage`)
- `~/.config/apache-steward/` (legacy per-user config dir)

If **none** exist, the repo is already on Magpie — stop and tell the
user to run `/magpie-setup upgrade` instead; there is nothing to
migrate.

Resolve `<adopter-skills-dir>` exactly as the framework's
[`magpie-setup` conventions](../../../skills/setup/conventions.md) does —
detect Pattern A (flat `.claude/skills/`), B (per-skill double-symlink
to `.github/skills/`), or D (one of `.claude/skills` / `.github/skills`
is a directory symlink to the other). Pin it for the rest of the run.

**Surface the full migration plan** (every rename below, as a single
list) and get the user's confirmation before writing anything. This is
a one-time, repo-reshaping change; the user sees it before it runs.

## Step 1 — Rename the snapshot dir

```bash
# Gitignored build artefact — a plain mv, no history impact.
[ -d .apache-steward ] && mv .apache-steward .apache-magpie
```

If `.apache-magpie/` already exists (a partial prior run), keep it and
`rm -rf .apache-steward`. After this the snapshot is at
`.apache-magpie/`, and the new framework's skills are at
`.apache-magpie/skills/<skill>/` (no longer `.../.claude/skills/...`).

Confirm `.apache-magpie/skills/setup/SKILL.md` exists — that is the new
bootstrap skill source. If it is missing, the re-fetch landed an
unexpected layout; stop and surface it.

## Step 2 — Rename the lock files

```bash
# Committed pin — use git mv so history follows.
[ -f .apache-steward.lock ] && git mv .apache-steward.lock .apache-magpie.lock
# Gitignored per-machine record — plain mv.
[ -f .apache-steward.local.lock ] && mv .apache-steward.local.lock .apache-magpie.local.lock
```

## Step 3 — Rename the overrides dir

```bash
# Committed; preserve every override file and its history.
[ -d .apache-steward-overrides ] && git mv .apache-steward-overrides .apache-magpie-overrides
```

The override **filenames** are keyed to framework skill names. Only one
framework skill was renamed in the Magpie rename: `setup-steward` →
`setup`. So if an override `setup-steward.md` exists, rename it too:

```bash
[ -f .apache-magpie-overrides/setup-steward.md ] && \
  git mv .apache-magpie-overrides/setup-steward.md .apache-magpie-overrides/setup.md
```

All other override filenames (`security-issue-sync.md`,
`pr-management-triage.md`, …) are unchanged — the `magpie-` prefix is an
install-time symlink-name concern, not an override-file concern (an
override targets the skill by its clean source name).

## Step 4 — Replace the committed bootstrap skill (`setup-steward` → `magpie-setup`)

The committed skill currently on disk at `<adopter-skills-dir>/setup-steward/`
is **this shim** (the pre-Magpie upgrade just overwrote it from the
snapshot). Replace it with the real Magpie bootstrap skill, named
`magpie-setup`, per the adopter's layout pattern:

```bash
# Pattern A (flat):
rm -rf <adopter-skills-dir>/setup-steward
cp -r .apache-magpie/skills/setup <adopter-skills-dir>/magpie-setup

# Pattern B (double-symlinked) — copy into .github/skills/, then the
# outer .claude/skills/magpie-setup symlink is created in Step 5:
rm -rf .github/skills/setup-steward .claude/skills/setup-steward
cp -r .apache-magpie/skills/setup .github/skills/magpie-setup

# Pattern D — write to the canonical side only (D.1 → .github/skills/,
# D.2 → .claude/skills/); the symlinked side resolves automatically:
rm -rf <canonical-side>/setup-steward
cp -r .apache-magpie/skills/setup <canonical-side>/magpie-setup
```

`magpie-setup` is the one **committed** framework skill (Golden rule 6);
it lands as new files in `git status` for the migration PR.

## Step 5 — Re-prefix every framework symlink to `magpie-`

Pre-Magpie, framework skills were symlinked under their bare names
(`<adopter-skills-dir>/security-issue-import` → snapshot). Magpie
namespaces every framework skill under a `magpie-` prefix. For **each**
existing framework symlink in `<adopter-skills-dir>` (every entry that
is a symlink resolving into the snapshot, i.e. not the committed
`magpie-setup` and not an adopter-owned skill):

1. Determine its clean source name `<n>` (the snapshot skill it points
   at). **Note the one renamed skill:** a legacy `list-steward-skills`
   symlink maps to the new source name `list-skills`.
2. Create `<adopter-skills-dir>/magpie-<n>` → relative path into
   `.apache-magpie/skills/<n>/` (per pattern — both layers for B; the
   canonical side only for D).
3. Remove the old bare symlink (`security-issue-import`,
   `pr-management-triage`, `list-steward-skills`, …).

Compute the symlink set fresh from `.apache-magpie/skills/` filtered to
the families the project had (read from the renamed
`.apache-magpie.lock` plus the always-on `setup-*` / `list-*` families)
— do not hard-code names. The post-migration state: every framework
skill the project uses is reachable as `magpie-<n>`, and no bare-named
framework symlink remains.

## Step 6 — Rewrite the `.gitignore` block

Replace the legacy framework gitignore entries. The Magpie layout
collapses the per-family symlink lines into a single `magpie-*` glob,
because **every** framework symlink now carries the prefix:

```text
# --- remove these legacy lines if present ---
/.apache-steward/
/.apache-steward.local.lock
/.claude/skills/security-*
/.claude/skills/pr-management-*
/.claude/skills/issue-*
/.claude/skills/setup-isolated-setup-*
/.claude/skills/setup-override-upstream
/.claude/skills/setup-shared-config-sync
/.claude/skills/list-steward-*
/.github/skills/security-*            # (Pattern B/D only)
/.github/skills/pr-management-*
/.github/skills/issue-*
/.github/skills/setup-isolated-setup-*
/.github/skills/setup-override-upstream
/.github/skills/setup-shared-config-sync
/.github/skills/list-steward-*

# --- write these Magpie lines ---
/.apache-magpie/
/.apache-magpie.local.lock
/.claude/skills/magpie-*
/.github/skills/magpie-*              # (Pattern B; or the canonical side for D)
```

Keep the orientation right for the adopter's pattern (Pattern A → only
the `.claude/skills/magpie-*` line; D → only the canonical side). The
committed `.apache-magpie.lock` and `.apache-magpie-overrides/` are
**not** gitignored.

## Step 7 — Migrate the per-user config dir + sandbox allowlist

The per-user credential / config dir moved from `~/.config/apache-steward/`
to `~/.config/apache-magpie/`:

```bash
[ -d ~/.config/apache-steward ] && [ ! -e ~/.config/apache-magpie ] && \
  mv ~/.config/apache-steward ~/.config/apache-magpie
```

This dir is **outside** the repo and per-machine — migrate it once per
machine. **Then tell the operator to update their sandbox allowlist**:
any `~/.config/apache-steward/` entry in their Claude Code settings
(project `.claude/settings.local.json`, project `.claude/settings.json`,
or user-scope `~/.claude/settings.json`) must become
`~/.config/apache-magpie/`, or sandboxed framework tools will not be
able to read the moved credentials. The framework cannot edit those
settings files for the operator — surface the exact one-line change.

## Step 8 — Migrate the post-checkout hook, lint config + doc sections

- **Git hook.** If `.git/hooks/post-checkout` contains the legacy
  `setup-steward verify --auto-fix-symlinks` recipe, update it to
  `magpie-setup verify --auto-fix-symlinks` (same auto-fix behaviour,
  new skill name). Leave any non-framework hook lines untouched.
- **Project docs.** In `README.md` / `AGENTS.md` / `CONTRIBUTING.md`,
  update any adoption section that still names `setup-steward`,
  `/setup-steward`, `.apache-steward*`, or the bare-named framework
  symlinks. Best-effort and surfaced as part of the migration diff; the
  framework-name prose ("Apache Magpie") is independent and not touched
  here.
- **Lint / pre-commit config.** If the adopter's `.pre-commit-config.yaml`
  (or any other prek / linter config) *excludes* the committed framework
  skill or the overrides dir by their old paths — e.g.
  `^\.github/skills/setup-steward/`, `^\.claude/skills/setup-steward/`,
  `^\.apache-steward-overrides/` — re-point those exclusion patterns to the
  magpie paths (`magpie-setup`, `.apache-magpie-overrides/`). Adopters add
  these so the committed bootstrap skill is skipped by license / spellcheck
  / markdown-lint / link-check hooks; leaving a pattern stale lets those
  hooks run on the renamed files and the migration commit **fails**. The
  exact lines are adopter-specific — grep the config for `setup-steward`
  and `apache-steward` and re-point every match. Surfaced as part of the
  migration diff.

## Step 9 — Hand off to `magpie-setup` and finish the upgrade

The repo is now on the Magpie layout and **this shim is gone** (Step 4
replaced the committed `setup-steward` with `magpie-setup`). Reload and
hand off, per Golden rule 9:

1. Re-read `<adopter-skills-dir>/magpie-setup/SKILL.md` and
   `<adopter-skills-dir>/magpie-setup/upgrade.md`.
2. The snapshot is already fresh at `.apache-magpie/`, so **skip** the
   delete/re-fetch steps and resume the migrated upgrade from its
   **Step 5 (reconcile overrides)** onward — reconcile overrides
   against the new framework structure, then the Step 6 symlink-refresh
   pass (idempotent — it confirms the `magpie-*` links Step 5 created),
   the worktree propagation pass, and the upgrade summary.

## Step 10 — Summary

Report the migration as a single block:

```text
Migrated pre-Magpie (apache-steward) → Apache Magpie:
  snapshot     .apache-steward/            → .apache-magpie/
  committed pin .apache-steward.lock        → .apache-magpie.lock
  local pin     .apache-steward.local.lock  → .apache-magpie.local.lock
  overrides     .apache-steward-overrides/  → .apache-magpie-overrides/
  bootstrap     setup-steward               → magpie-setup   (committed)
  symlinks      <bare>-*                    → magpie-*       (N re-prefixed)
  gitignore     per-family lines            → magpie-* glob
  user config   ~/.config/apache-steward/   → ~/.config/apache-magpie/
  hook          setup-steward verify        → magpie-setup verify

Action required (operator): update the ~/.config/apache-steward/ entry
in your Claude Code sandbox allowlist to ~/.config/apache-magpie/.

From now on use /magpie-setup for everything. The setup-steward shim is
removed; commit this migration diff as the upgrade PR.
```
