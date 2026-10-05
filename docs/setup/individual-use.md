<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Individual use — Magpie on any repo, without adopting it](#individual-use--magpie-on-any-repo-without-adopting-it)
  - [Overview](#overview)
  - [Prerequisites](#prerequisites)
  - [Step 1 — Marketplace install (recommended): covers every repo](#step-1--marketplace-install-recommended-covers-every-repo)
    - [Fallback — pinned-snapshot whole-user install](#fallback--pinned-snapshot-whole-user-install)
    - [Clone the framework to a stable personal location](#clone-the-framework-to-a-stable-personal-location)
    - [Symlink framework skills to your user-scope skills directory](#symlink-framework-skills-to-your-user-scope-skills-directory)
    - [Keeping user-scope skills current](#keeping-user-scope-skills-current)
  - [Step 2 — Create your personal config directory](#step-2--create-your-personal-config-directory)
    - [Optional — add skill overrides](#optional--add-skill-overrides)
  - [Step 3 — Run skills against the target repo](#step-3--run-skills-against-the-target-repo)
  - [What your teammates see (nothing)](#what-your-teammates-see-nothing)
  - [Skills that assume everyone has Magpie](#skills-that-assume-everyone-has-magpie)
  - [What works vs what doesn't](#what-works-vs-what-doesnt)
  - [If the project later adopts Magpie](#if-the-project-later-adopts-magpie)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Individual use — Magpie on any repo, without adopting it

> [!IMPORTANT]
> **Skill names differ on this install.** This page's recommended path is a
> **marketplace plugin install**, invoked `/<plugin>:<alias>` — e.g.
> `/magpie-security:issue-triage`. Its fallback path is the **pinned-snapshot
> whole-user install**, invoked as a **single token** —
> `/magpie-security-issue-triage`, not `/magpie-security:issue-triage`. There
> is no plugin namespace on the fallback; the `magpie-` prefix *is* the
> namespace there, and the name is the skill's directory name. See
> [Skill names differ by install method](marketplace.md#skill-names-differ-by-install-method).
>
> The skill listing (Claude Code's `/` menu) also shows the **shorter** frontmatter
> name beside it — `issue-triage` — as a display label; what you type is still
> the single-token command.

## Overview

This is one of the two ways to use Magpie, and it asks nothing of anybody
else. You install the plugins you want and run them against whatever repo you
are working in — one that has [adopted Magpie](team-adoption.md), one that has
not, one whose maintainers have never heard of it, one where you are the only
person on the team who uses it. Nothing is committed, no shared settings file
changes, and no teammate has to do anything.

It is not a lesser path or a waiting room for adoption. Most people who use
Magpie use it exactly like this, indefinitely.

Two situations it covers, which used to be documented separately because they
looked different and are not:

- **The repo has not adopted Magpie.** You want to help with a fix, triage an
  issue, or run a security audit without waiting for the project to decide
  anything.
- **Your teammates have not adopted it.** You work on a shared repo and want
  Magpie for yourself, without asking anyone to change how they work.

A **marketplace plugin install already covers this**: Claude Code keeps
plugin state in one user-scope store (`~/.claude/plugins/`), so a plugin you
install once is available in every repo you open next, adopted or not —
nothing project-specific is required. See
[Step 1](#step-1--marketplace-install-recommended-covers-every-repo) below.
The rest of this recipe is your **personal config layer**
(see [`agentic-overrides.md`](agentic-overrides.md)).
On a repo that has not adopted Magpie it is
**`<git-common-dir>/apache-magpie/`** — `.git/apache-magpie/` in an
ordinary clone — inside the repository's git directory, not its working tree.
Git never tracks it, so it needs no ignore entry, never shows up in
`git status`, and is shared by every worktree of the clone.
Nothing lands in the working tree of a repo you do not own.

The recipe has three steps:

1. **Marketplace install** (recommended) — install the plugins you want once;
   they are then available in every repo, adopted or not. A pinned-snapshot
   whole-user install is the fallback, for when a marketplace is not
   reachable.
2. **Create your personal config directory** — optionally add your overrides.
3. **Run skills** — invoke them as if the project were adopted.

## Prerequisites

- **Claude Code** installed and working (see
  [`docs/prerequisites.md`](../quick-start/prerequisites.md)).
- **Secure agent setup** installed — run
  [`/magpie-setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md)
  with **whole-user (global) scope** once. This sets up the sandbox
  allowlist for every repo on your host, not just adopted ones.  If you
  have already done this for another Magpie-adopted project on this machine,
  skip this sub-step — whole-user scope covers the target repo automatically.

## Step 1 — Marketplace install (recommended): covers every repo

[Add the marketplace](marketplace-install.md) for your agent if you have not
already, then install the families you want:

```text
/plugin install magpie-setup@apache-magpie
/plugin install magpie-pr-management@apache-magpie
```

That's it — nothing else in this step. Claude Code's plugin state lives in
one user-scope store (`~/.claude/plugins/`), so the skills are now available
in every repo you open on this machine, Project X included, whether or not
Project X has adopted Magpie. Skip to
[Step 2](#step-2--create-your-personal-config-directory).

### Fallback — pinned-snapshot whole-user install

Use this instead of Step 1 only when a marketplace is not reachable (no
plugin mechanism for your agent, or the project wants the signed ASF source
release rather than a git clone).

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

## Step 2 — Create your personal config directory

The easy way is `/magpie-setup config` in the target repo: it creates the
directory, scaffolds the configuration your skills need, and writes nothing
anyone else will see.

By hand, from the target repo:

```bash
mkdir -p "$(git rev-parse --git-common-dir)/apache-magpie"
```

The directory may be empty. Magpie skills check for
`<personal-layer>/<skill-name>.md` before applying framework defaults
— if the file is absent, defaults apply without error.

Because it lives in the git directory, the personal layer goes with the
clone: a fresh clone starts unconfigured, and deleting the clone deletes it.
Keep a copy elsewhere if you want it to outlive the clone.

> [!NOTE]
> Older versions put this directory in the working tree, as
> `.apache-magpie-local/`, with an ignore entry in `.git/info/exclude`.
> That still works: it is read after the git-directory home, and the
> pre-flight offers to move it.

### Optional — add skill overrides

If you need a Project-X-specific behaviour adjustment, write it as
agent-readable Markdown in a file named after the skill:

```bash
cat > "$(git rev-parse --git-common-dir)/apache-magpie/pr-management-triage.md" <<'EOF'
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

## Step 3 — Run skills against the target repo

Open the target repo's directory in Claude Code and invoke any installed
skill. **On the marketplace install** (Step 1), use `/<plugin>:<alias>`:

```text
/magpie-pr-management:pr-triage
/magpie-issue:triage
/magpie-security:issue-import
/magpie-release-management:audit-report
```

**On the pinned-snapshot fallback**, use the single-token `magpie-` name
instead:

```text
/magpie-pr-management-triage
/magpie-issue-triage
/magpie-security-issue-import
/magpie-release-audit-report
```

Either way, the skills are at user scope, so Claude Code finds them
regardless of what project you are in. The skill reads
`<personal-layer>/<skill-name>.md` (if present) before applying
framework defaults, so your personal overrides are honoured without any
project-wide config.

You will see the skill's **override disclosure** at the top: it names the
file it read and lists the override headlines, so you know exactly what
personal adjustments are active before the skill does anything.

## What your teammates see (nothing)

From a teammate's perspective:

- Nothing in the working tree changes: your personal layer is inside your
  clone's git directory, which is never pushed, so it never shows up in
  `git status` or in a PR.
- No shared settings file changes. No committed skill symlinks. No
  `.apache-magpie.lock`.
- Their own sessions are unaffected — anything user-scope lives in your home
  directory, not theirs.

## Skills that assume everyone has Magpie

Most skills act only on behalf of the person invoking them and need nothing
from your teammates. A few coordinate across contributors — assigning reviewers
from a configured roster, sending onboarding mail, checking reviewer load — and
those degrade gracefully when run this way: they work from the data available
to you, and cannot read teammate configuration they cannot reach.

If a skill instead stops with something like "no `<project-config>/` found"
and proposes `/magpie-setup config`, that is its pre-flight: a configuration
file it needs resolves in neither your personal layer nor a committed
`.apache-magpie-overrides/`, and it stops rather than guess at every
unresolved placeholder in its body.
Running `/magpie-setup config` fills your personal layer and satisfies it,
without committing anything. If a skill still stops after that,
[report it](../../skills/report-framework-issue/SKILL.md) so the skill is
fixed to degrade gracefully instead.

Skills that write to shared project state — labels, PR assignments, roster
files — are the ones that benefit most from the project having
[adopted Magpie](team-adoption.md), because then the team has agreed on what
the agent may touch.

## What works vs what doesn't

| Works | Does not work |
|---|---|
| Every **install** — marketplace or snapshot — works exactly as it does on an adopted repo | A workflow skill run with no project config at all: its pre-flight stops and proposes `/magpie-setup` rather than guessing. The install is fine; what is missing is the repo's configuration |
| All workflow skills — `security-*`, `pr-management-*`, `issue-*`, `release-*`, `mentoring-*`, `pairing-*`, `repo-health-*` — once the repo has a `.apache-magpie-overrides/` for them to read | `/magpie-setup verify` / `upgrade` — these read the committed lock and snapshot, which do not exist here |
| Personal configuration and overrides in `<git-common-dir>/apache-magpie/` | Shared overrides (`.apache-magpie-overrides/`) — the committed override directory requires the project to have adopted |
| `setup-isolated-setup-install` / `-verify` / `-doctor` (the secure-setup skills are user-scope artefacts, not per-project) | Drift and floor detection — there is no `.apache-magpie.lock` to compare against, so the pre-flight falls through to the project-config check above |
| The full safety, confidentiality, and privacy baseline (always applied regardless of adoption state) | — |

If a skill raises an unexpected "adoption required" message on a step that
ought to work without adoption, that is a gap — file it on the framework
issue tracker so the step can be made adoption-optional.

## If the project later adopts Magpie

Nothing you did here is undone by that, and you do not have to switch paths.

**A floor is a minimum, never a ceiling.** Once the repo has adopted, the
pre-flight at the top of every framework skill you run there compares your
machine against the project's `.apache-magpie.lock` and brings you up to the
floor it names if you fall short — installing or updating only the plugins
the floor lists, then stopping so you can restart — and nothing more. If you
are already at or ahead of the floor, a newer Magpie release, extra families
installed, or both, the pre-flight changes nothing and says nothing: your
own installs and versions are always left alone.

[Adoption](team-adoption.md) commits a recommendation: a default set of
families that a contributor gets on clone, plus the repo's shared overrides. If
you already have those families installed, nothing changes for you. If you do
not, you can take the defaults or keep your own selection — the committed set
is a floor, not an allowlist.

Your personal configuration keeps working, but its home moves.
Once the repo carries a committed `.apache-magpie.lock`, the personal layer
is `.apache-magpie-local/` in the working tree, gitignored by the line
adoption commits, and the git-directory home is no longer read.
Move what you hold in `<git-common-dir>/apache-magpie/` into
`.apache-magpie-local/` after you pull the adoption.
It then sits at the top of the lookup chain (`.apache-magpie-local/` →
`.apache-magpie-overrides/` → framework default), so your personal overrides
still win. Anything in there that everyone would want is worth moving into
the committed `.apache-magpie-overrides/` — and anything genuinely personal,
such as the contributor-growth thresholds, should stay where it is.

If the project also takes the [pinned snapshot install](../quick-start/other-install-methods.md) —
a separate decision from adopting — its project-scope skills will shadow any
user-scope symlinks you set up under the fallback path in Step 1.

## Cross-references

- [**Team adoption**](team-adoption.md) — the other half of this pair: what a
  repo commits so every contributor gets a recommended set on arrival.
- [**The Apache Magpie Marketplace**](marketplace.md) — installing the plugins
  this page runs.
- [`agentic-overrides.md`](agentic-overrides.md) — the full contract for
  the personal layer and `.apache-magpie-overrides/`, including the lookup
  order, override shapes and hard rules.
- [`secure-agent-setup.md`](secure-agent-setup.md) — the secure-agent harness,
  worth running whether or not any repo has adopted Magpie.
- [`install-recipes.md`](../quick-start/other-install-methods.md) — install methods, if you need the
  pinned snapshot rather than the marketplace.
- [`setup-status` skill](../../skills/setup-status/SKILL.md) — reports what is
  installed and wired here, including where your personal layer is and whether it exists.
