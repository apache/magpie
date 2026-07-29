<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How to use Magpie on a repo that has not adopted it](#how-to-use-magpie-on-a-repo-that-has-not-adopted-it)
  - [Overview](#overview)
  - [Prerequisites](#prerequisites)
  - [Step 1 — Whole-user install: make Magpie skills available in every repo](#step-1--whole-user-install-make-magpie-skills-available-in-every-repo)
    - [Clone the framework to a stable personal location](#clone-the-framework-to-a-stable-personal-location)
    - [Symlink framework skills to your user-scope skills directory](#symlink-framework-skills-to-your-user-scope-skills-directory)
    - [Keeping user-scope skills current](#keeping-user-scope-skills-current)
  - [Step 2 — In the target repo: add one `.gitignore` line](#step-2--in-the-target-repo-add-one-gitignore-line)
  - [Step 3 — Create your personal config directory](#step-3--create-your-personal-config-directory)
    - [Optional — add skill overrides](#optional--add-skill-overrides)
  - [Step 4 — Run skills against the target repo](#step-4--run-skills-against-the-target-repo)
  - [What works vs what doesn't](#what-works-vs-what-doesnt)
  - [If the project later adopts Magpie](#if-the-project-later-adopts-magpie)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# How to use Magpie on a repo that has not adopted it

## Overview

Project X has not adopted Magpie. You want to use Magpie skills to help
with a fix, triage an issue, or run a security audit on Project X's repo
— without waiting for the project to adopt, without committing the
framework artefacts, and without asking teammates to change anything.

This recipe covers that case. The key piece is the **`.apache-magpie-local/`**
personal override directory (added in the framework's override surface; see
[`agentic-overrides.md`](agentic-overrides.md)): a gitignored directory
that lives in the target repo and provides your personal config layer.
Because it is gitignored (and contains no binaries), adding it to a repo
you do not own is safe and non-intrusive.

The recipe has four steps:

1. **Whole-user install** — make Magpie skills available in every repo you
   open, not just adopted ones.
2. **Add one `.gitignore` line** — keep your personal config untracked.
3. **Create `.apache-magpie-local/`** — optionally add your overrides.
4. **Run skills** — invoke them as if the project were adopted.

## Prerequisites

- **Claude Code** installed and working (see
  [`docs/prerequisites.md`](../prerequisites.md)).
- **Secure agent setup** installed — run
  [`/magpie-setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md)
  with **whole-user (global) scope** once. This sets up the sandbox
  allowlist for every repo on your host, not just adopted ones.  If you
  have already done this for another Magpie-adopted project on this machine,
  skip this sub-step — whole-user scope covers the target repo automatically.

## Step 1 — Whole-user install: make Magpie skills available in every repo

In a normal project adoption, Magpie's skills are installed as gitignored
symlinks under `.agents/skills/` (canonical) and `.claude/skills/` (Claude
Code relay). Those symlinks exist only in the adopted repo and its
worktrees.

For a non-adopted repo you need the skills at **user scope** so Claude
Code can find them regardless of what directory you are in.

### Clone the framework to a stable personal location

Pick a directory that will not move — you are about to create symlinks
that point into it. A common convention:

```bash
git clone --depth=1 --branch main \
    https://github.com/apache/magpie.git \
    ~/dev/magpie
```

You can use any local path. The depth `--depth=1` keeps the clone small;
re-clone (or `git pull`) to refresh later.

### Symlink framework skills to your user-scope skills directory

Claude Code reads skills from `~/.claude/skills/` (user scope) in every
session, regardless of the project directory. Link all framework skills
there:

```bash
mkdir -p ~/.claude/skills

for skill_dir in ~/dev/magpie/skills/*/; do
    skill_name=$(basename "$skill_dir")
    target=~/.claude/skills/magpie-${skill_name}
    # Overwrite stale link on re-run; skip if the name somehow collides
    ln -snf "$skill_dir" "$target"
done
```

Verify the links are in place:

```bash
ls ~/.claude/skills/ | grep ^magpie-
```

You should see entries like `magpie-pr-management-triage`,
`magpie-issue-triage`, `magpie-security-issue-import`, etc. — one per
framework skill.

> **Why not `~/.agents/skills/`?** Claude Code's native user-scope path is
> `~/.claude/skills/`. Other agents (Codex, Cursor, Gemini CLI, …) use
> `~/.agents/skills/`. Add a parallel `~/.agents/skills/` loop if you want
> the skills available user-scope in those agents too; the framework's
> per-project canonical dir is `.agents/skills/`, but the user-scope
> equivalent is left to each user's dotfile setup.

### Keeping user-scope skills current

When the framework publishes updates, pull and refresh the links:

```bash
cd ~/dev/magpie && git pull
# Re-run the symlink loop (idempotent; ln -snf updates stale targets):
for skill_dir in ~/dev/magpie/skills/*/; do
    skill_name=$(basename "$skill_dir")
    ln -snf "$skill_dir" ~/.claude/skills/magpie-${skill_name}
done
```

The symlinks resolve through to the updated source files automatically —
you only need to re-run the loop when new skills are added to the
framework (so new `magpie-*` names appear) or when old ones are removed
(so stale links are pruned).

## Step 2 — In the target repo: add one `.gitignore` line

In the target (unadopted) repo, tell git not to track your personal
config:

```bash
echo '/.apache-magpie-local/' >> .gitignore
```

This is the **only change to committed files** that this recipe requires.
You can omit it if you plan to add `.apache-magpie-local/` to your global
gitignore instead (`~/.gitignore_global` or equivalent); either approach
keeps the directory untracked.

If you do not want to touch the repo's `.gitignore` at all, add the entry
to your global gitignore:

```bash
git config --global core.excludesFile ~/.gitignore_global
echo '/.apache-magpie-local/' >> ~/.gitignore_global
```

## Step 3 — Create your personal config directory

```bash
mkdir -p /path/to/target-repo/.apache-magpie-local
```

The directory may be empty. Magpie skills check for
`.apache-magpie-local/<skill-name>.md` before applying framework defaults
— if the file is absent, defaults apply without error.

### Optional — add skill overrides

If you need a Project-X-specific behaviour adjustment, write it as
agent-readable Markdown in a file named after the skill:

```bash
cat > /path/to/target-repo/.apache-magpie-local/pr-management-triage.md <<'EOF'
### Override 1 — Require two approvals for merge

This project requires two approving reviews before a PR is
merged (team policy, not enforced by GitHub branch protection
yet). Treat a PR as mergeable only when it has ≥ 2 approvals.
EOF
```

Overrides follow the same **additive-only** contract as committed
overrides: they may add project-specific context, adjust defaults, or
enable an extra capability (e.g. a release-manager enabling an extra MCP)
— they may **not** weaken the safety, confidentiality, or privacy baseline
the framework always applies.

See [`agentic-overrides.md`](agentic-overrides.md) for the full override
contract and example shapes (skip a step, replace a step, add a step,
pre-empt a decision-table row).

## Step 4 — Run skills against the target repo

Open the target repo's directory in Claude Code and invoke any framework
skill by its `magpie-` name:

```text
/magpie-pr-management-triage
/magpie-issue-triage
/magpie-security-issue-import
/magpie-release-audit-report
```

Because the skills are at user scope (`~/.claude/skills/`), Claude Code
finds them regardless of what project you are in. The skill reads
`.apache-magpie-local/<skill-name>.md` (if present) before applying
framework defaults, so your personal overrides are honoured without any
project-wide config.

You will see the skill's **override disclosure** at the top: it names the
file it read and lists the override headlines, so you know exactly what
personal adjustments are active before the skill does anything.

## What works vs what doesn't

| Works | Does not work |
|---|---|
| All workflow skills — `security-*`, `pr-management-*`, `issue-*`, `release-*`, `mentoring-*`, `pairing-*`, `repo-health-*` | `/magpie-setup adopt` / `verify` / `upgrade` — these manage the committed lock and snapshot, which do not exist here |
| Personal overrides via `.apache-magpie-local/` | Shared overrides (`.apache-magpie-overrides/`) — the committed override directory requires the project to have adopted |
| `setup-isolated-setup-install` / `-verify` / `-doctor` (the secure-setup skills are user-scope artefacts, not per-project) | Drift detection (the skill checks for `.apache-magpie.lock`; finding none, it proceeds without it rather than erroring) |
| The full safety, confidentiality, and privacy baseline (always applied regardless of adoption state) | — |

If a skill raises an unexpected "adoption required" message on a step that
ought to work without adoption, that is a gap — file it on the framework
issue tracker so the step can be made adoption-optional.

## If the project later adopts Magpie

When Project X eventually adopts the framework via
[`install-recipes.md`](install-recipes.md) and `/magpie-setup adopt`,
the project-scope skills will appear under `.agents/skills/` and
`.claude/skills/` in that repo. Claude Code's project-scope skills take
precedence over user-scope ones when both exist, so the project-scope
install will shadow your `~/.claude/skills/magpie-*` links for that repo.

Your `.apache-magpie-local/` files continue to work: the project adoption
adds the `.gitignore` entry automatically (idempotent — the line is
already there if you added it in Step 2), and the override lookup chain
(`personal-local → committed → framework default`) honours
them as the highest-precedence layer. The lookup has only two override
surfaces: the personal-local file and the committed project file.

You can delete the personal directory once the project is adopted and any
overrides you care about have been upstreamed into
`.apache-magpie-overrides/` or the framework itself.

## Cross-references

- [`agentic-overrides.md`](agentic-overrides.md) — the full contract for
  `.apache-magpie-local/` and `.apache-magpie-overrides/`, including
  override shapes and hard rules.
- [`install-recipes.md`](install-recipes.md) — how to do a full project
  adoption once the team is ready.
- [`secure-agent-setup.md`](secure-agent-setup.md) — the full install
  walkthrough for the secure-agent harness (the prerequisite to any
  framework use, adopted or not).
- [`setup` skill](../../skills/setup/SKILL.md) — the entry point for
  project-level adoption (`/magpie-setup adopt`).
- [`setup-status` skill](../../skills/setup-status/SKILL.md) — the
  adoption dashboard; reports whether `.apache-magpie-local/` is present
  in addition to the committed lock and override scaffold.
