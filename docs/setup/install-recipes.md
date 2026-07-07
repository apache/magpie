<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Install recipes — bootstrap Magpie in an adopter repo](#install-recipes--bootstrap-magpie-in-an-adopter-repo)
  - [Method 1 — released zip from ASF distribution](#method-1--released-zip-from-asf-distribution)
  - [Method 2 — git tag](#method-2--git-tag)
  - [Method 3 — git branch (defaults to `main`)](#method-3--git-branch-defaults-to-main)
  - [After any recipe — let the skill take over](#after-any-recipe--let-the-skill-take-over)
  - [Subsequent runs and drift detection](#subsequent-runs-and-drift-detection)
  - [Migrating a pre-Magpie (`apache-magpie`) adopter](#migrating-a-pre-magpie-apache-magpie-adopter)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Install recipes — bootstrap Magpie in an adopter repo

Three copy-pasteable shell recipes for fetching the framework
into a new adopter project's repo. Each recipe is **the
bootstrap that gets `setup` into the repo**; once it is
in place, the rest of the adoption (skill-family pick, framework
symlinks, project doc note, gitignored runtime state) runs
through `/magpie-setup` interactively.

Pick the recipe that matches your distribution preference:

| Method | When to use | Reproducibility |
|---|---|---|
| [**svn-zip**](#method-1--released-zip-from-asf-distribution) | Production adopters once the framework ships official ASF releases. Signed + checksummed. | Frozen by version |
| [**git-tag**](#method-2--git-tag) | Pinning a specific framework version (e.g. for testing a release candidate, or for a cautious adopter who tracks named releases only). | Frozen by tag |
| [**git-branch**](#method-3--git-branch-defaults-to-main) | WIP path — track the framework's `main` branch directly. The default during the framework's pre-release phase. | Tracks branch tip |

> **Canonical layout — no per-project convention to pick.**
> `.agents/skills/` is the one canonical home (see
> [`agents.md`](../../skills/setup/agents.md)). Copy `setup` into
> `.agents/skills/magpie-setup/`, then add a relay symlink to it
> from every agent-specific dir you use
> (`.claude/skills/magpie-setup` and `.github/skills/magpie-setup`
> → `../../.agents/skills/magpie-setup`). This is the same for
> every adopter regardless of how `.claude/` / `.github/` were
> previously organised.
>
> The `setup` skill itself is the **only** framework
> artefact you commit. Every other framework skill is wired
> in by the `setup adopt` flow as gitignored symlinks —
> canonical in `.agents/skills/`, relayed everywhere else.

---

## Method 1 — released zip from ASF distribution

> **Status: forthcoming.** ASF release distribution
> (`https://dist.apache.org/repos/dist/release/<project>/`)
> is the canonical home for ASF-blessed releases per the
> [release-policy](https://www.apache.org/legal/release-policy.html)
> and [infra release-distribution guidelines](https://infra.apache.org/release-distribution.html).
> This recipe will be the recommended path once the framework
> ships its first official release; until then, use
> [Method 3 — git-branch](#method-3--git-branch-defaults-to-main).

```bash
# === Magpie bootstrap — Method 1: signed zip from ASF dist ===
# Replace <PROJECT> with the host adopter's ASF dist subdirectory
# (e.g. `airflow` once releases land at
# https://dist.apache.org/repos/dist/release/airflow/).
# Replace <VERSION> with the framework version you want.

cd /path/to/your/repo

VERSION=<VERSION>
PROJECT=<PROJECT>
DIST_BASE=https://dist.apache.org/repos/dist/release/${PROJECT}
ZIP=apache-magpie-${VERSION}-source-release.zip

# 1. Download zip + signature + checksum, verify, extract to .apache-magpie/
curl -fsSLO ${DIST_BASE}/${ZIP}
curl -fsSLO ${DIST_BASE}/${ZIP}.sha512
curl -fsSLO ${DIST_BASE}/${ZIP}.asc
sha512sum -c ${ZIP}.sha512
# Optional but recommended — verify the OpenPGP signature against the
# project KEYS file (see https://infra.apache.org/release-signing.html):
#   curl -fsSLO ${DIST_BASE}/KEYS
#   gpg --import KEYS
#   gpg --verify ${ZIP}.asc ${ZIP}

mkdir -p .apache-magpie
unzip -q ${ZIP} -d .apache-magpie
mv .apache-magpie/apache-magpie-${VERSION}/* \
   .apache-magpie/apache-magpie-${VERSION}/.[!.]* \
   .apache-magpie/ 2>/dev/null
rmdir .apache-magpie/apache-magpie-${VERSION}
rm -f ${ZIP} ${ZIP}.sha512 ${ZIP}.asc

# 2. Copy the `setup` skill into the canonical .agents/skills/,
#    then relay it from each agent-specific dir you use.
mkdir -p .agents/skills .claude/skills .github/skills
cp -r .apache-magpie/skills/setup .agents/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .claude/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .github/skills/magpie-setup
#    (Drop the .claude or .github relay if you don't use that agent;
#     add the same `ln -sf` line for any holdout like .windsurf/skills.)

# 3. Add gitignore entries (idempotent — re-run is safe)
cat >> .gitignore <<'GITIGNORE'

# Magpie — gitignored snapshot of the framework, refreshed
# by /magpie-setup upgrade. Build artefact, not source.
/.apache-magpie/

# Per-machine local-pin file. Records what THIS machine fetched and
# when. Compared against the committed .apache-magpie.lock to
# detect drift.
/.apache-magpie.local.lock

# Byte-compiled artefacts emitted when framework skill scripts run
# from this checkout. Non-anchored so they match at any depth.
__pycache__/
*.pyc

# Deterministic agent-guard PreToolUse hook — framework code synced
# from the snapshot by /magpie-setup (and seeded into each worktree),
# not an adopter artefact. The committed .claude/settings.json wires
# it; the script itself stays gitignored. Force-add your own guards
# under guards.d/ with `git add -f` if you want them tracked.
/.claude/hooks/agent-guard.py
/.claude/hooks/guards.d/

# Framework-skill symlinks created by /magpie-setup. One uniform
# block per skills dir you use: the `magpie-*` glob ignores them
# all (their targets are the gitignored snapshot, so they would
# dangle on a fresh clone), and the `!…/magpie-setup` negation keeps
# the one committed bootstrap tracked. .agents/skills/ is canonical;
# the rest are relays into it. Drop any block for a dir you don't use.
/.agents/skills/magpie-*
!/.agents/skills/magpie-setup
/.claude/skills/magpie-*
!/.claude/skills/magpie-setup
/.github/skills/magpie-*
!/.github/skills/magpie-setup
GITIGNORE

# 4. Tell your agent: "follow /magpie-setup to finish adopting Magpie."
#    The skill will write .apache-magpie.lock (committed) and
#    .apache-magpie.local.lock (gitignored), ask which skill family
#    to wire up, create the gitignored framework-skill symlinks, and
#    update your project docs.
```

---

## Method 2 — git tag

```bash
# === Magpie bootstrap — Method 2: pinned git tag ===
# Replace <TAG> with the framework tag you want
# (e.g. `v1.0.0` once tags exist on apache/magpie).

cd /path/to/your/repo

TAG=<TAG>
git clone --depth=1 \
    --branch ${TAG} \
    https://github.com/apache/magpie.git \
    .apache-magpie

# Copy the `setup` skill to canonical + relays (see Method 1 step 2)
mkdir -p .agents/skills .claude/skills .github/skills
cp -r .apache-magpie/skills/setup .agents/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .claude/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .github/skills/magpie-setup

# Add gitignore entries (same block as Method 1 step 3 — see there)

# Tell your agent: "follow /magpie-setup to finish adopting Magpie."
```

---

## Method 3 — git branch (defaults to `main`)

The default WIP path while the framework is pre-release.

```bash
# === Magpie bootstrap — Method 3: git branch (default: main) ===
cd /path/to/your/repo

BRANCH=main   # or another branch you want to track
git clone --depth=1 \
    --branch ${BRANCH} \
    https://github.com/apache/magpie.git \
    .apache-magpie

# Copy the `setup` skill to canonical + relays (see Method 1 step 2)
mkdir -p .agents/skills .claude/skills .github/skills
cp -r .apache-magpie/skills/setup .agents/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .claude/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .github/skills/magpie-setup

# Add gitignore entries (same block as Method 1 step 3 — see there)

# Tell your agent: "follow /magpie-setup to finish adopting Magpie."
```

---

## After any recipe — let the skill take over

Once the recipe completes, `setup` is in your repo and
the snapshot is on disk (gitignored). Tell your agent:

```text
follow .agents/skills/magpie-setup to adopt Magpie
```

(or invoke `/magpie-setup` directly). The skill walks through
the rest:

1. **Pick the skill families** to symlink in (`security`,
   `pr-management`, `issue`).
2. **Write the lock files**:
   - `.apache-magpie.lock` (**committed**) — the project's pin
     (the method + URL + ref you used in the recipe). Future
     adopters of *this same repo* re-install per this pin.
   - `.apache-magpie.local.lock` (**gitignored**) — what THIS
     machine actually fetched (commit SHA, timestamp).
3. **Create the symlinks** for chosen skill families
   (gitignored — they target the gitignored snapshot).
4. **Scaffold `.apache-magpie-overrides/`** (committed) for
   any local workflow modifications.
5. **Install a `post-checkout` git hook** so worktrees
   re-create the gitignored runtime state.
6. **Update your project documentation** with a brief mention
   of the framework adoption.

After this, adopters fresh-cloning the repo can run
`/magpie-setup` and get the framework provisioned per your
project's committed `.apache-magpie.lock` — no need to redo
the manual recipe.

## Subsequent runs and drift detection

Every framework skill — and `/magpie-setup verify` —
compares the local lock against the committed lock at the top
of its run. If they have drifted (e.g. the project lead bumped
`.apache-magpie.lock` to a newer ref, or the local install is
stale on a `main`-tracking adopter), the skill surfaces the
gap and proposes:

```text
/magpie-setup upgrade
```

`upgrade` deletes the gitignored snapshot, re-installs per the
committed lock, refreshes the gitignored symlinks (adding any
new framework skills, removing any that were renamed away),
and updates the local lock. See
[`setup/upgrade.md`](../../skills/setup/upgrade.md)
for the full flow.

## Migrating a pre-Magpie (`apache-magpie`) adopter

A repo that adopted the framework **before** it was renamed from
`apache-magpie` to **Apache Magpie** is on the old layout: a committed
`.claude/skills/magpie-setup/` skill, an `.apache-magpie/` snapshot,
`.apache-magpie.lock` / `.apache-magpie-overrides/`, un-prefixed
framework symlinks, and `~/.config/apache-magpie/`. The framework
**no longer ships an automated migration** for this layout — migrate by
hand:

1. Remove the legacy in-repo artefacts: `.apache-magpie*` (snapshot,
   locks, overrides), any un-prefixed framework symlinks under the
   skills dir, and the committed `.claude/skills/magpie-setup/` skill.
2. Re-adopt from scratch with `/magpie-setup` (see
   [`setup/adopt.md`](../../skills/setup/adopt.md)) so the current
   `.apache-magpie*` layout and `magpie-`-prefixed symlinks are written
   fresh. Preserve any `.apache-magpie-overrides/*.md` you want to keep
   by moving them into the new `.apache-magpie-overrides/` first.
3. Move `~/.config/apache-magpie/` (per-user) to
   `~/.config/apache-magpie/`, and update any `~/.config/apache-magpie/`
   entry in your Claude Code sandbox allowlist (project
   `.claude/settings.local.json` / `.claude/settings.json` or user-scope
   `~/.claude/settings.json`) to `~/.config/apache-magpie/` — otherwise
   sandboxed framework tools cannot read the moved credentials.
