<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Install recipes — bootstrap apache-steward in an adopter repo](#install-recipes--bootstrap-apache-steward-in-an-adopter-repo)
  - [Method 1 — released zip from ASF distribution](#method-1--released-zip-from-asf-distribution)
  - [Method 2 — git tag](#method-2--git-tag)
  - [Method 3 — git branch (defaults to `main`)](#method-3--git-branch-defaults-to-main)
  - [After any recipe — let the skill take over](#after-any-recipe--let-the-skill-take-over)
  - [Subsequent runs and drift detection](#subsequent-runs-and-drift-detection)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Install recipes — bootstrap apache-steward in an adopter repo

Three copy-pasteable shell recipes for fetching the framework
into a new adopter project's repo. Each recipe is **the
bootstrap that gets `setup-steward` into the repo**; once it is
in place, the rest of the adoption (skill-family pick, framework
symlinks, project doc note, gitignored runtime state) runs
through `/setup-steward` interactively.

Pick the recipe that matches your distribution preference:

| Method | When to use | Reproducibility |
|---|---|---|
| [**svn-zip**](#method-1--released-zip-from-asf-distribution) | Production adopters once the framework ships official ASF releases. Signed + checksummed. | Frozen by version |
| [**git-tag**](#method-2--git-tag) | Pinning a specific framework version (e.g. for testing a release candidate, or for a cautious adopter who tracks named releases only). | Frozen by tag |
| [**git-branch**](#method-3--git-branch-defaults-to-main) | WIP path — track the framework's `main` branch directly. The default during the framework's pre-release phase. | Tracks branch tip |

> **Adopter convention** — pick the right `cp` step per your
> existing skills layout (see
> [`.claude/skills/setup-steward/conventions.md`](../../.claude/skills/setup-steward/conventions.md)
> for the full taxonomy):
>
> - **A — flat** (`.claude/skills/<n>/SKILL.md` directly): copy
>   `setup-steward` into `.claude/skills/setup-steward/`.
> - **B — double-symlinked** (per-skill
>   `.claude/skills/<n>` → `.github/skills/<n>/` symlinks): copy
>   the content into `.github/skills/setup-steward/` AND symlink
>   `.claude/skills/setup-steward` → `../../.github/skills/setup-steward`.
> - **D — single directory symlink** (one of
>   `.claude/skills` / `.github/skills` is itself a directory
>   symlink to the other): copy the content into the
>   *canonical* side only — `.github/skills/setup-steward/`
>   for D.1 (canonical `.github/skills/`) or
>   `.claude/skills/setup-steward/` for D.2 (canonical
>   `.claude/skills/`). The opposite side is the same
>   directory via the symlink, so there is nothing to wire up.
>
> The `setup-steward` skill itself is the **only** framework
> artefact you commit. Every other framework skill is wired
> in by the `setup-steward adopt` flow as gitignored symlinks
> into the gitignored snapshot.

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
# === apache-steward bootstrap — Method 1: signed zip from ASF dist ===
# Replace <PROJECT> with the host adopter's ASF dist subdirectory
# (e.g. `airflow` once releases land at
# https://dist.apache.org/repos/dist/release/airflow/).
# Replace <VERSION> with the framework version you want.

cd /path/to/your/repo

VERSION=<VERSION>
PROJECT=<PROJECT>
DIST_BASE=https://dist.apache.org/repos/dist/release/${PROJECT}
ZIP=apache-steward-${VERSION}-source-release.zip

# 1. Download zip + signature + checksum, verify, extract to .apache-steward/
curl -fsSLO ${DIST_BASE}/${ZIP}
curl -fsSLO ${DIST_BASE}/${ZIP}.sha512
curl -fsSLO ${DIST_BASE}/${ZIP}.asc
sha512sum -c ${ZIP}.sha512
# Optional but recommended — verify the OpenPGP signature against the
# project KEYS file (see https://infra.apache.org/release-signing.html):
#   curl -fsSLO ${DIST_BASE}/KEYS
#   gpg --import KEYS
#   gpg --verify ${ZIP}.asc ${ZIP}

mkdir -p .apache-steward
unzip -q ${ZIP} -d .apache-steward
mv .apache-steward/apache-steward-${VERSION}/* \
   .apache-steward/apache-steward-${VERSION}/.[!.]* \
   .apache-steward/ 2>/dev/null
rmdir .apache-steward/apache-steward-${VERSION}
rm -f ${ZIP} ${ZIP}.sha512 ${ZIP}.asc

# 2. Copy the `setup-steward` skill into your skills dir.
#    Pick ONE branch based on your existing convention.
#
#    A — flat layout (default):
mkdir -p .claude/skills
cp -r .apache-steward/.claude/skills/setup-steward .claude/skills/setup-steward
#
#    B — double-symlinked layout (per-skill symlinks):
# mkdir -p .github/skills .claude/skills
# cp -r .apache-steward/.claude/skills/setup-steward .github/skills/setup-steward
# ln -sf ../../.github/skills/setup-steward .claude/skills/setup-steward
#
#    D.1 — single directory symlink, canonical .github/skills/:
#    (.claude/skills is itself a symlink → ../.github/skills/)
# cp -r .apache-steward/.claude/skills/setup-steward .github/skills/setup-steward
#    (No second copy needed — .claude/skills/setup-steward resolves
#     to .github/skills/setup-steward via the directory symlink.)
#
#    D.2 — single directory symlink, canonical .claude/skills/:
#    (.github/skills is itself a symlink → ../.claude/skills/)
# cp -r .apache-steward/.claude/skills/setup-steward .claude/skills/setup-steward

# 3. Add gitignore entries (idempotent — re-run is safe)
cat >> .gitignore <<'GITIGNORE'

# apache-steward — gitignored snapshot of the framework, refreshed
# by /setup-steward upgrade. Build artefact, not source.
/.apache-steward/

# Per-machine local-pin file. Records what THIS machine fetched and
# when. Compared against the committed .apache-steward.lock to
# detect drift.
/.apache-steward.local.lock

# Symlinks created by /setup-steward into the gitignored snapshot.
# Pattern A (flat) → keep only the .claude/skills/ block below.
# Pattern B (per-skill double-symlinked) → keep BOTH blocks (one
#   physical symlink per layer needs its own ignore line).
# Pattern D.1 (.claude/skills → .github/skills/) → keep only the
#   .github/skills/ block — git does not descend into the directory
#   symlink, so .claude/skills/ ignore lines are unnecessary.
# Pattern D.2 (.github/skills → .claude/skills/) → keep only the
#   .claude/skills/ block (same reason, opposite orientation).
/.claude/skills/security-*
/.claude/skills/pr-management-*
/.claude/skills/issue-*
/.claude/skills/setup-isolated-setup-*
/.claude/skills/setup-shared-config-sync
/.claude/skills/list-steward-*
/.github/skills/security-*
/.github/skills/pr-management-*
/.github/skills/issue-*
/.github/skills/setup-isolated-setup-*
/.github/skills/setup-shared-config-sync
/.github/skills/list-steward-*
GITIGNORE

# 4. Tell your agent: "follow /setup-steward to finish adopting steward."
#    The skill will write .apache-steward.lock (committed) and
#    .apache-steward.local.lock (gitignored), ask which skill family
#    to wire up, create the gitignored framework-skill symlinks, and
#    update your project docs.
```

---

## Method 2 — git tag

```bash
# === apache-steward bootstrap — Method 2: pinned git tag ===
# Replace <TAG> with the framework tag you want
# (e.g. `v1.0.0` once tags exist on apache/airflow-steward).

cd /path/to/your/repo

TAG=<TAG>
git clone --depth=1 \
    --branch ${TAG} \
    https://github.com/apache/airflow-steward.git \
    .apache-steward

# Copy the `setup-steward` skill — pick A / B / D (see Method 1 step 2)
mkdir -p .claude/skills
cp -r .apache-steward/.claude/skills/setup-steward .claude/skills/setup-steward
# OR for double-symlinked (B):
# cp -r .apache-steward/.claude/skills/setup-steward .github/skills/setup-steward
# ln -sf ../../.github/skills/setup-steward .claude/skills/setup-steward
# OR for single directory-symlink (D) — copy to canonical side only;
# the .claude/skills ↔ .github/skills directory symlink does the rest.

# Add gitignore entries (same block as Method 1 step 3 — see there)

# Tell your agent: "follow /setup-steward to finish adopting steward."
```

---

## Method 3 — git branch (defaults to `main`)

The default WIP path while the framework is pre-release.

```bash
# === apache-steward bootstrap — Method 3: git branch (default: main) ===
cd /path/to/your/repo

BRANCH=main   # or another branch you want to track
git clone --depth=1 \
    --branch ${BRANCH} \
    https://github.com/apache/airflow-steward.git \
    .apache-steward

# Copy the `setup-steward` skill — pick A / B / D (see Method 1 step 2)
mkdir -p .claude/skills
cp -r .apache-steward/.claude/skills/setup-steward .claude/skills/setup-steward
# OR for double-symlinked (B):
# cp -r .apache-steward/.claude/skills/setup-steward .github/skills/setup-steward
# ln -sf ../../.github/skills/setup-steward .claude/skills/setup-steward
# OR for single directory-symlink (D) — copy to canonical side only;
# the .claude/skills ↔ .github/skills directory symlink does the rest.

# Add gitignore entries (same block as Method 1 step 3 — see there)

# Tell your agent: "follow /setup-steward to finish adopting steward."
```

---

## After any recipe — let the skill take over

Once the recipe completes, `setup-steward` is in your repo and
the snapshot is on disk (gitignored). Tell your agent:

```text
follow .claude/skills/setup-steward to adopt steward
```

(or invoke `/setup-steward` directly). The skill walks through
the rest:

1. **Pick the skill families** to symlink in (`security`,
   `pr-management`, `issue`).
2. **Write the lock files**:
   - `.apache-steward.lock` (**committed**) — the project's pin
     (the method + URL + ref you used in the recipe). Future
     adopters of *this same repo* re-install per this pin.
   - `.apache-steward.local.lock` (**gitignored**) — what THIS
     machine actually fetched (commit SHA, timestamp).
3. **Create the symlinks** for chosen skill families
   (gitignored — they target the gitignored snapshot).
4. **Scaffold `.apache-steward-overrides/`** (committed) for
   any local workflow modifications.
5. **Install a `post-checkout` git hook** so worktrees
   re-create the gitignored runtime state.
6. **Update your project documentation** with a brief mention
   of the framework adoption.

After this, adopters fresh-cloning the repo can run
`/setup-steward` and get the framework provisioned per your
project's committed `.apache-steward.lock` — no need to redo
the manual recipe.

## Subsequent runs and drift detection

Every framework skill — and `/setup-steward verify` —
compares the local lock against the committed lock at the top
of its run. If they have drifted (e.g. the project lead bumped
`.apache-steward.lock` to a newer ref, or the local install is
stale on a `main`-tracking adopter), the skill surfaces the
gap and proposes:

```text
/setup-steward upgrade
```

`upgrade` deletes the gitignored snapshot, re-installs per the
committed lock, refreshes the gitignored symlinks (adding any
new framework skills, removing any that were renamed away),
and updates the local lock. See
[`setup-steward/upgrade.md`](../../.claude/skills/setup-steward/upgrade.md)
for the full flow.
