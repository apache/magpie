<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Other installation methods](#other-installation-methods)
  - [Which one, and when](#which-one-and-when)
    - [Released zip from ASF distribution (offline)](#released-zip-from-asf-distribution-offline)
    - [Git tag (one pinned version)](#git-tag-one-pinned-version)
    - [Git branch (development)](#git-branch-development)
    - [After any recipe — let the skill take over](#after-any-recipe--let-the-skill-take-over)
    - [Subsequent runs and drift detection](#subsequent-runs-and-drift-detection)
  - [Working on Magpie itself — self-adoption](#working-on-magpie-itself--self-adoption)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Other installation methods

**The [Apache Magpie Marketplace](../setup/marketplace.md) is the main install,
and the [quick start](../quick-start.md) walks it.** It takes two commands, it
writes nothing to your repository, and it is complete for day-to-day use. If
that worked for you, you do not need this page.

This page is the rest: a pinned snapshot committed to the repository, in three
flavours, and the self-adoption path a clone of the framework itself takes.

---

## Which one, and when

The framework can *reach* your agent by three routes, and they differ in who
installs it and what it touches:

| | Who installs it | What it touches |
|---|---|---|
| **Marketplace install** | You, per machine | Your agent. Nothing in the repo. |
| **Pinned snapshot install** | The project, once | A committed version pin and a gitignored snapshot in the repo. |
| **Self-adoption** (`method:local`) | The Magpie checkout itself | Committed symlinks onto the repo's own `skills/`. |

Everything below installs the framework as a **pinned snapshot in the
repository**. It is more work, it commits state to the project, and it is the
right answer in exactly three situations:

| You are here because | Method |
|---|---|
| **Your agent has no marketplace at all.** The snapshot path is harness-neutral — it wires skills into *any* agent through the universal `.agents/skills/` layout. | any of the three |
| **You are working on the framework, or want unreleased changes.** Track `main` directly and pick up changes as they land. | [git branch](#git-branch-development) — the development path |
| **You need the signed ASF source release**, or you are installing somewhere without access to GitHub. | [released zip](#released-zip-from-asf-distribution-offline) — the offline path |
| **The project wants every contributor and CI job pinned to one committed version**, with drift detection and project-specific overrides. | [git tag](#git-tag-one-pinned-version) |

If none of those describe you, use the marketplace and stop reading here.

> [!IMPORTANT]
> **Skill names differ on this install.** Installed from the pinned snapshot
> (or self-adoption), a skill is invoked as a **single token** —
> `/magpie-security-issue-triage` — not `/magpie-security:issue-triage`. There
> is no plugin namespace here; the `magpie-` prefix *is* the namespace, and the
> name is the skill's directory name. Magpie's other docs show the
> marketplace form; see
> [Skill names differ by install method](../setup/marketplace.md#skill-names-differ-by-install-method).
>
> The skill listing (Claude Code's `/` menu) also shows the **shorter** frontmatter
> name beside it — `issue-triage` — as a display label; what you type is still
> the single-token command.

Each recipe below is **the bootstrap that gets `setup` into the repo**; once
it is in place, the rest of the adoption (skill-family pick, framework
symlinks, project doc note, gitignored runtime state) runs through
`/magpie-setup` interactively.

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

### Released zip from ASF distribution (offline)

> **Use this when you need the signed artefact, or have no GitHub access.**
> ASF release distribution
> (`https://dist.apache.org/repos/dist/release/magpie/`)
> is the canonical home for ASF-blessed releases per the
> [release-policy](https://www.apache.org/legal/release-policy.html)
> and [infra release-distribution guidelines](https://infra.apache.org/release-distribution.html).
> Magpie ships there from `0.1.0` onwards. It is the only method that gives
> you a signature and checksum to verify before anything lands, and the only
> one that works from a machine that cannot reach `github.com` — mirror the
> zip once and install from it anywhere.
>
> The **canonical release** of Magpie is this artefact. A marketplace entry
> is a convenience layer referencing the same released tag, derived from this
> and not a substitute for it.

```bash
# === Magpie bootstrap — signed zip from ASF dist ===
# Replace <VERSION> with the framework version you want (e.g. 0.1.0).
# Released versions are listed at
# https://dist.apache.org/repos/dist/release/magpie/

cd /path/to/your/repo

VERSION=<VERSION>
# KEYS lives at the project root of the dist area; the artefacts live
# under a per-version subdirectory.
DIST_BASE=https://dist.apache.org/repos/dist/release/magpie
REL_BASE=${DIST_BASE}/${VERSION}
ZIP=apache-magpie-${VERSION}-source.zip

# 1. Download zip + signature + checksum, verify, extract to .apache-magpie/
curl -fsSLO ${REL_BASE}/${ZIP}
curl -fsSLO ${REL_BASE}/${ZIP}.sha512
curl -fsSLO ${REL_BASE}/${ZIP}.asc
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
# by /magpie-setup upgrade. Build artefact, not source. No trailing
# slash: worktree-init makes this a symlink to the main checkout's
# snapshot, and a directory-only pattern would not match it.
/.apache-magpie

# Per-machine local-pin file. Records what THIS machine fetched and
# when. Compared against the committed .apache-magpie.lock to
# detect drift.
/.apache-magpie.local.lock

# Byte-compiled artefacts emitted when framework skill scripts run
# from this checkout. Non-anchored so they match at any depth.
__pycache__/
*.pyc

# (No agent-guard entries. The deterministic PreToolUse guard runs
# from the install — the magpie-agent-guard plugin, or a
# settings.local.json entry resolving the engine inside the snapshot
# — so nothing repository-local exists to ignore, and no worktree
# needs seeding. Repos adopted before that change can drop their
# leftover /.claude/hooks/agent-guard.py and /.claude/hooks/guards.d/
# lines along with the files.)

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

### Git tag (one pinned version)

> **Use this when the project wants everyone on one committed version.**
> The tag goes into `.apache-magpie.lock`, which is committed, so every
> contributor and every CI job installs the same framework version and
> drift against it is detected on each skill run.

```bash
# === Magpie bootstrap — pinned git tag ===
# Replace <TAG> with the framework tag you want
# (e.g. `v1.0.0` once tags exist on apache/magpie).

cd /path/to/your/repo

TAG=<TAG>
git clone --depth=1 \
    --branch ${TAG} \
    https://github.com/apache/magpie.git \
    .apache-magpie

# Copy the `setup` skill to canonical + relays (see the zip recipe, step 2)
mkdir -p .agents/skills .claude/skills .github/skills
cp -r .apache-magpie/skills/setup .agents/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .claude/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .github/skills/magpie-setup

# Add gitignore entries (same block as the zip recipe, step 3 — see there)

# Tell your agent: "follow /magpie-setup to finish adopting Magpie."
```

---

### Git branch (development)

> **Use this when you are working on the framework itself, or want changes
> that are not in a release yet.** It tracks a branch tip rather than a fixed
> point, so what you have installed moves as the branch moves — that is the
> point of it, and the reason it is not the path for a project that wants a
> reproducible install.

```bash
# === Magpie bootstrap — git branch (default: main) ===
cd /path/to/your/repo

BRANCH=main   # or another branch you want to track
git clone --depth=1 \
    --branch ${BRANCH} \
    https://github.com/apache/magpie.git \
    .apache-magpie

# Copy the `setup` skill to canonical + relays (see the zip recipe, step 2)
mkdir -p .agents/skills .claude/skills .github/skills
cp -r .apache-magpie/skills/setup .agents/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .claude/skills/magpie-setup
ln -sf ../../.agents/skills/magpie-setup .github/skills/magpie-setup

# Add gitignore entries (same block as the zip recipe, step 3 — see there)

# Tell your agent: "follow /magpie-setup to finish adopting Magpie."
```

---

### After any recipe — let the skill take over

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
5. **Install a `post-checkout` git hook** so each new
   worktree adds itself to the sandbox allowlist. It does
   *not* re-create the gitignored runtime state — a new
   worktree gets that from `/magpie-setup worktree-init`.
6. **Update your project documentation** with a brief mention
   of the framework adoption.

After this, adopters fresh-cloning the repo can run
`/magpie-setup` and get the framework provisioned per your
project's committed `.apache-magpie.lock` — no need to redo
the manual recipe.

### Subsequent runs and drift detection

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

---

## Working on Magpie itself — self-adoption

Inside a clone of [`apache/magpie`](https://github.com/apache/magpie), the
default is neither of the above: the framework **self-adopts**, linking its own
live `skills/` source so the skills you are editing are the skills that run.

```text
/magpie-setup method:local
```

`/magpie-setup` detects the framework checkout and takes this path by default —
a remote method against it is refused, because snapshotting the framework into
itself would shadow the live source with a stale copy. It fetches nothing: the
`magpie-<skill>` symlinks point at in-repo paths and are **committed**, and
`.apache-magpie.lock` records `method: local` with no URL or ref. Contributors
get it on a fresh clone with no install step at all.

Self-adoption uses the **same single-token names as the snapshot install** —
`/magpie-pairing-self-review`, not `/magpie-pairing:self-review`.
