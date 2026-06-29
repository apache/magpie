<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie](#apache-magpie)
  - [How adoption works](#how-adoption-works)
  - [Adopting the framework](#adopting-the-framework)
    - [1. Bootstrap (copy-pasteable shell)](#1-bootstrap-copy-pasteable-shell)
    - [2. Skill takeover](#2-skill-takeover)
    - [Subsequent contributors](#subsequent-contributors)
    - [Drift detection](#drift-detection)
  - [Skill families](#skill-families)
  - [Maintenance](#maintenance)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Apache Magpie

A reusable, project-agnostic framework for ASF-project automation.
Currently in development for ASF projects + Python Core team
friendlies. **Not** a public marketplace skill — adoption is by
invitation while the framework is pre-release; once we ship via
the [ASF release policy](https://www.apache.org/legal/release-policy.html),
the marketplace path opens up. See
[release-distribution](https://infra.apache.org/release-distribution.html)
for the canonical distribution mechanism we will adopt.

> [!IMPORTANT]
> The motivation, scope, and design commitments behind this work
> live in [`MISSION.md`](MISSION.md) — the **draft** project-
> establishment proposal for an Apache Top-Level Project built on
> this framework. Read that for the *why*; this README is the
> *how* once you've decided to adopt.

## How adoption works

The framework uses a **snapshot + agentic-override** adoption
model. An adopter project commits a single skill —
[`setup`](skills/setup/SKILL.md) —
into their repo. That skill manages everything else:

1. **Snapshot.** `setup` downloads the framework into
   a **gitignored** `<adopter>/.apache-magpie/` directory.
   The snapshot is a build artefact, not source — refreshed
   by `/magpie-setup upgrade`, never committed.
2. **Symlinks.** `setup` symlinks the framework's
   skills (security, pr-management, the rest of setup) under
   one canonical home — `.agents/skills/` (the path shared by
   Codex, Cursor, Gemini CLI, Copilot, …) — and gives every
   other agent dir (`.claude/skills/`, `.github/skills/`, …) a
   thin per-skill **relay** symlink pointing back at the
   canonical entry. This is the same regardless of how the
   adopter previously organised those dirs. The symlinks are
   **also gitignored** — they ultimately target the gitignored
   snapshot, so they would dangle on a fresh clone before
   `/magpie-setup` runs.
3. **Overrides.** Adopter-specific modifications to framework
   workflows live as agent-readable markdown under
   `<adopter>/.apache-magpie-overrides/<skill>.md`,
   **committed** in the adopter repo. The framework's skills
   consult those files at run-time and apply the overrides
   before executing default behaviour. See
   [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md)
   for the contract.

**No git submodules. No marketplace. No vendored copies of
framework skills.** Just one committed skill (the bootstrap),
a gitignored snapshot, and agent-readable override files.

## Adopting the framework

Two phases — a **shell bootstrap** that gets `setup`
into your repo, then the **skill takeover** that wires up the
rest interactively.

### 1. Bootstrap (copy-pasteable shell)

Pick an install method and follow the verbatim recipe in
[**`docs/setup/install-recipes.md`**](docs/setup/install-recipes.md):

| Method | When to use | Reproducibility |
|---|---|---|
| `svn-zip` | Production once ASF official releases ship to `dist.apache.org` (signed + checksummed) | Frozen by version |
| `git-tag` | Pin a specific framework version | Frozen by tag |
| `git-branch` (default `main`) | WIP path — track the framework's `main` directly. The default during the framework's pre-release phase. | Tracks tip |

Each recipe is a single shell block that:

1. Adds `.apache-magpie/`, `.apache-magpie.local.lock`, and
   the framework-skill symlinks to `.gitignore`.
2. Downloads + verifies + extracts the framework into
   `.apache-magpie/` (gitignored — build artefact, not
   source).
3. Copies the
   [`setup`](skills/setup/SKILL.md)
   skill into the canonical `.agents/skills/magpie-setup/` and
   adds a relay symlink to it from each agent dir you use
   (`.claude/skills/magpie-setup`, `.github/skills/magpie-setup`).

After the recipe completes, the framework snapshot is on
disk and the bootstrap skill is in your repo.

### 2. Skill takeover

Tell your agent: **"adopt apache/magpie in my repo"**
(or invoke `/magpie-setup` directly). The skill walks
through the rest:

- writes `.apache-magpie.lock` (committed) — the project's
  pin: install method + URL + ref + verification anchor;
- writes `.apache-magpie.local.lock` (gitignored) — what
  this machine actually fetched + when;
- asks which skill families (`security`, `pr-management`) to
  symlink in;
- creates the gitignored framework-skill symlinks;
- scaffolds `.apache-magpie-overrides/` (committed) for any
  local workflow modifications;
- installs a `post-checkout` git hook so worktrees re-create
  runtime state automatically;
- updates your project documentation with a brief mention.

After the skill finishes, you commit the small, focused
diff — the bootstrap skill, the `.gitignore` entries, the
two lock files (committed + gitignore exclusion for the
local one), the overrides scaffold, the doc note — and you're
done. Open a PR.

### Subsequent contributors

Future contributors who clone your repo just say "adopt
Magpie in this repo" (or invoke `/magpie-setup`).
The skill reads `.apache-magpie.lock` (already committed)
and re-installs to the same version your project pinned. No
need to redo the manual recipe — the committed lock is the
project's source-of-truth.

### Drift detection

Every framework skill compares the gitignored
`.apache-magpie.local.lock` against the committed
`.apache-magpie.lock` at the top of its run. If they have
drifted (project lead bumped the pin, or the local install
is stale on a `main`-tracking adopter), the skill surfaces
the gap and proposes `/magpie-setup upgrade`. `upgrade`
deletes the gitignored snapshot, re-installs per the
committed pin, refreshes the gitignored symlinks, and
reconciles any agentic overrides — see
[`docs/setup/install-recipes.md`](docs/setup/install-recipes.md)
and
[`skills/setup/upgrade.md`](skills/setup/upgrade.md)
for the full flow.

## Skill families

Four skill families ship in the framework (plus one experimental
family, mentoring; one proposed family, release-management; and
two meta utilities). Pick whichever families the adopter wants to
use; symlinks for the picked families land in the adopter's skill
directory.

The **Modes** column maps each family to the MISSION agent-assistance
taxonomy — see [`docs/modes.md`](docs/modes.md) for what each mode
means and which modes are still proposed vs. shipping today.

Most families work on **any** project, ASF or not. Families marked
**🪶 ASF-specific** in the **Scope** column encode Apache Software Foundation
processes (the release lifecycle, the contributor-to-committer path) and assume
an ASF adopter profile by default — non-ASF projects adopt them through the
adapter/config layer.

| Family | Modes | Scope | Purpose | Detail |
|---|---|---|---|---|
| [**setup**](docs/setup/README.md) | (infra) | Any project | Isolated agent setup, framework adoption + maintenance, shared-config sync. The prerequisite — at minimum the `setup` skill itself runs out of this family. | 6 skills, [`docs/setup/`](docs/setup/) |
| [**security**](docs/security/README.md) | A, C | Any project | 16-step security-issue handling lifecycle — from `security@` import through CVE publication, including state sync. Maintainer-only. | 9 skills, [`docs/security/`](docs/security/) |
| **pr-management** | A | Any project | Maintainer-facing PR-queue management — triage, stats, and deep code review. | 3 skills, [`docs/pr-management/`](docs/pr-management/README.md) |
| [**release-management**](docs/release-management/README.md) | A, C | 🪶 ASF-specific | 14-step ASF release lifecycle, planning issue, RC cut + sign, `[VOTE]` thread, tally, promote, `[ANNOUNCE]`, archive, audit log. Agent never holds the RM's signing key and never publishes the release. **Proposed**, spec-first, like Agentic Mentoring; skill code lands in follow-up PRs. | 10 skills proposed, [`docs/release-management/`](docs/release-management/) |
| [**mentoring**](docs/mentoring/README.md) | Agentic Mentoring | Any project | Contributor mentoring — spec and tone guide in place; first skill (`pr-management-mentor`) shipping. **Experimental** — shape may change as adopter pilots and contributor-sentiment evaluation land. | 1 skill, [`docs/mentoring/`](docs/mentoring/README.md) |
| **issue** | A, Agentic Triage | Any project | Issue lifecycle management — triage, bug reproduction, fix drafting, and backlog re-assessment against the current branch. | 5 skills |
| **utilities** | (meta) | Any project | Framework meta-skills: author or update skills (`write-skill`); print a live index of all available skills (`list-skills`). | 2 skills |

## Maintenance

After the initial adoption, the same skill handles ongoing
maintenance:

- `/magpie-setup upgrade` — refresh the snapshot to a newer
  framework version + reconcile any overrides against the new
  framework structure.
- `/magpie-setup verify` — read-only health check (snapshot
  intact, symlinks live, `.gitignore` correct, etc.).
- `/magpie-setup override <framework-skill>` — open or
  scaffold an override file for a framework skill.

## Cross-references

- [`MISSION.md`](MISSION.md) — **draft** project-establishment proposal: motivation, scope, design commitments, initial PMC composition target.
- [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md) — the contract between adopters who write overrides and framework skills that read them.
- [`docs/prerequisites.md`](docs/prerequisites.md) — what a maintainer needs installed before invoking any framework skill (Claude Code, Gmail MCP, GitHub auth, browser, `uv`, etc.).
- [`AGENTS.md`](AGENTS.md) — agent instructions, placeholder convention, framework conventions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — for framework contributors.
