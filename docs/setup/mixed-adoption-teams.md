<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How to use Magpie on a team where not everyone has adopted it](#how-to-use-magpie-on-a-team-where-not-everyone-has-adopted-it)
  - [Overview](#overview)
  - [Prerequisites](#prerequisites)
  - [Step 1 — Install Magpie at whole-user (global) scope](#step-1--install-magpie-at-whole-user-global-scope)
  - [Step 2 — Add one `.gitignore` line to the shared repo](#step-2--add-one-gitignore-line-to-the-shared-repo)
  - [Step 3 — Create your personal config directory](#step-3--create-your-personal-config-directory)
  - [Step 4 — Run skills as normal](#step-4--run-skills-as-normal)
  - [What your teammates see (nothing)](#what-your-teammates-see-nothing)
  - [What works vs what does not](#what-works-vs-what-does-not)
  - [Skills that assume every teammate has Magpie](#skills-that-assume-every-teammate-has-magpie)
  - [If the team later adopts Magpie](#if-the-team-later-adopts-magpie)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# How to use Magpie on a team where not everyone has adopted it

## Overview

You work on a repo with other people. You want to use Magpie skills — to
triage issues, draft security responses, or review PRs — but your
teammates have not adopted Magpie and are not interested in doing so yet.

This recipe shows how to run Magpie **only for yourself** against a shared
repo, without committing any framework artefacts, without changing the
project's settings files, and without asking teammates to do anything.

The mechanism is the same one used for unadopted repos: a **whole-user
install** (so skills are available in every directory you work in) plus a
**`.apache-magpie-local/`** personal directory (gitignored, so it stays
off the repo's history). Your teammates open the same files and branches
they always have; nothing about the repo changes from their point of view.

The recipe has four steps:

1. **Whole-user install** — make Magpie skills available in any repo.
2. **Add one `.gitignore` line** — keep your personal config untracked.
3. **Create `.apache-magpie-local/`** — your personal config layer.
4. **Run skills** — invoke them against the shared repo normally.

## Prerequisites

- **Claude Code** installed and working.
- You have at least read access to the shared repo (clone or existing
  working copy on your machine).
- Your teammates have not (and need not) install anything.

## Step 1 — Install Magpie at whole-user (global) scope

A per-project adoption wires Magpie skills as symlinks under the repo's
`.agents/skills/`. In a mixed-adoption team you cannot commit those
symlinks, so you need skills available at **user scope** instead — where
Claude Code finds them in every directory you open.

**Clone the framework** to a stable personal location:

```bash
git clone --depth=1 --branch main \
    https://github.com/apache/magpie.git \
    ~/.magpie
```

**Create user-scope skill symlinks** so Claude Code finds the skills in
any project:

```bash
mkdir -p ~/.claude/skills
for skill_dir in ~/.magpie/.claude/skills/*/; do
    skill_name=$(basename "$skill_dir")
    ln -sfn "$skill_dir" ~/.claude/skills/"$skill_name"
done
```

**Install the secure agent setup** at user scope. This wires the sandbox
allowlist so the secure posture applies to every repo on your machine, not
just adopted ones:

```bash
# From any directory:
/magpie-setup-isolated-setup-install
```

When prompted for scope, choose **whole-user (global)**. If you have
already done this for another Magpie-adopted project on this machine, the
user-scope sandbox already covers new repos automatically — skip this
sub-step.

**Keeping skills current** — pull the framework clone periodically:

```bash
git -C ~/.magpie pull --ff-only
# Symlinks stay valid; no re-linking needed.
```

## Step 2 — Add one `.gitignore` line to the shared repo

Your personal config directory (`.apache-magpie-local/`) must not land on
the repo's history. Add it to the repo's `.gitignore`:

```bash
echo '.apache-magpie-local/' >> .gitignore
git add .gitignore
git commit -m 'chore: ignore .apache-magpie-local (personal Magpie config)'
```

If the repo uses a per-user gitignore convention (`~/.gitignore_global` or
`git config core.excludesFile`) and you prefer not to commit a `.gitignore`
change, add `.apache-magpie-local/` there instead. The directory will
still stay untracked; it just will not be visible to teammates who clone
the repo later.

If you do not want to commit a `.gitignore` change at all, add the
directory to your global gitignore:

```bash
echo '.apache-magpie-local/' >> ~/.gitignore_global
# or wherever your core.excludesFile points
```

Either approach works. Committing the `.gitignore` line is friendlier to
future adopters and makes the intent visible, so it is the recommended
path.

## Step 3 — Create your personal config directory

```bash
mkdir -p /path/to/shared-repo/.apache-magpie-local
```

The directory can stay empty. Framework skills check for it at startup; an
empty directory is equivalent to "no personal overrides, use defaults."

**Optional — add a project-context override** so skills know where to
look for the tracker, upstream repo, or security list:

```yaml
# .apache-magpie-local/project.md
# Personal project context for <PROJECT> — not committed.
tracker: https://github.com/<ORG>/<PROJECT>
upstream: https://github.com/<ORG>/<PROJECT>
```

Replace `<ORG>` and `<PROJECT>` with the values for your shared repo. This
is the same format as a committed `projects/<project>/project.md`; the
personal version is just read from a different directory. See
[`agentic-overrides.md`](agentic-overrides.md) for the full override
syntax.

## Step 4 — Run skills as normal

Open Claude Code in the shared repo's directory and invoke any skill:

```text
/magpie-issue-triage
/magpie-pr-management-triage
/magpie-security-issue-import
```

The skills find the framework via the user-scope symlinks (Step 1), read
your personal context from `.apache-magpie-local/` (Step 3), and proceed
exactly as they would in a fully adopted repo.

## What your teammates see (nothing)

From a teammate's perspective:

- The `.gitignore` change (if you commit it) adds one line. They can
  ignore it.
- The `.apache-magpie-local/` directory is gitignored and never shows up
  in `git status` or PRs for them.
- No shared settings file changes. No committed skill symlinks. No
  `.apache-magpie.lock` file.
- Their own Claude Code sessions are unaffected — the user-scope skills
  live in your `~/.claude/`, not theirs.

A teammate who later wants to adopt Magpie runs
`/magpie-setup install` as normal; the one `.gitignore` line you added is
already present and helps them.

## What works vs what does not

| Scenario | Works without full adoption? |
|---|---|
| Running any read-only skill locally (triage, stats, review) | **Yes** |
| Drafting outbound messages (email, comments) for human review | **Yes** |
| Using personal overrides from `.apache-magpie-local/` | **Yes** |
| Skill drift detection and upgrade checks | **Yes** (user-scope install) |
| Framework version pinning shared with the team | **No** — without a committed `.apache-magpie.lock`, each team member's install drifts independently. If consistent framework behaviour across team members matters, full adoption is the right next step. |
| Per-project committed overrides (`.apache-magpie-overrides/`) | **Partial** — you can read them from `.apache-magpie-local/` if you copy them locally, but they are not committed. Any shared customisations that should be consistent across the team should go into `.apache-magpie-overrides/` via full adoption. |
| Automated CI or bot runs using Magpie skills | **No** — CI needs a committed install. |

## Skills that assume every teammate has Magpie

Most Magpie skills only act on behalf of the person invoking them and do
not require teammates to have the framework installed. A few skills,
however, coordinate across contributors (for example, assigning reviewers
from a configured roster, sending onboarding emails via the committer
onboarding skill, or checking reviewer load). Those skills degrade
gracefully when run personally: they operate on the data available to you
but cannot read teammate configuration they cannot reach.

If a skill fails outright with a message like "no `<project-config>/`
found" or "adapter not configured", it means it is trying to read a
committed project config that does not exist in the unadopted repo. The
fix is either:

- Add a minimal `project.md` to your `.apache-magpie-local/` to satisfy
  the lookup, or
- File the hard failure as a gap and open an issue against
  `apache/magpie` so the skill is fixed to degrade gracefully.

The mixed-adoption pattern is intended to work for read-heavy, local
skills. Skills that write to shared project state (labels, PR assignments,
roster files) work best in a fully adopted repo where the team has agreed
to let the agent touch those surfaces.

## If the team later adopts Magpie

When the project decides to adopt, the transition from your personal setup
is straightforward:

1. Run `/magpie-setup install` in the shared repo (see
   [`install-recipes.md`](install-recipes.md)) — this commits the bootstrap
   skill and lock, wires the skill symlinks under `.agents/skills/` and
   `.claude/skills/`, and adds the sandbox block to the shared
   `.claude/settings.json`.
2. Move any project context from `.apache-magpie-local/project.md` into
   the committed `projects/<project>/project.md`.
3. Move any personal overrides from `.apache-magpie-local/` that should be
   shared into `.apache-magpie-overrides/`.
4. Keep `.apache-magpie-local/` for anything that remains personal (your
   local clone paths, personal MCP servers).

The `.gitignore` line you added in Step 2 is already correct for the
adopted setup — `.apache-magpie-local/` stays gitignored even after full
adoption.

## Cross-references

- [Agentic overrides](agentic-overrides.md) — full contract for what you
  can put in `.apache-magpie-local/` and `.apache-magpie-overrides/`,
  including enabling role-specific MCP servers just for yourself.
- [Full install recipe](install-recipes.md) — if the team later decides
  to adopt Magpie, this is the canonical install walkthrough.
- [Secure agent setup](secure-agent-setup.md) — the full install reference
  including the user-scope sandbox.
- [Setup skill family](README.md) — overview of all setup skills and deep
  documentation pages.
