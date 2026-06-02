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

> **Heads-up — the project is named Apache Magpie; the GitHub
> slug rename is still pending.**
> The framework's name is **Apache Magpie**. The current
> `apache/airflow-steward` slug carries `airflow` for legacy
> reasons, but the framework is project-agnostic (it stewards
> multiple ASF project workflows, not just Airflow's), so the
> working group steering it chose a name that reflects that.
>
> **Magpie** was selected by the founding PMC and confirmed
> available via **PODLINGSEARCH**. Three alternates were carried
> as historical backups during the bikeshed — *Beacon*, *Guild*,
> and *Lichen* — but Magpie cleared the name search and is the
> final name; the alternates are no longer in play.
>
> Until the rename lands on the GitHub side, every clone URL and
> CI integration still uses the legacy `apache/airflow-steward`
> slug — all path examples in this README and the linked docs use
> that slug verbatim. The rename will only change the GitHub
> repository slug; existing checkouts will keep working with a
> single `git remote set-url`.

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
[`setup-steward`](.claude/skills/setup-steward/SKILL.md) —
into their repo. That skill manages everything else:

1. **Snapshot.** `setup-steward` downloads the framework into
   a **gitignored** `<adopter>/.apache-steward/` directory.
   The snapshot is a build artefact, not source — refreshed
   by `/setup-steward upgrade`, never committed.
2. **Symlinks.** `setup-steward` symlinks the framework's
   skills (security, pr-management, the rest of setup) into
   the adopter's existing skill directory, matching whichever
   convention the adopter uses (flat `.claude/skills/`, or the
   double-symlink `.claude/skills/<n>` → `.github/skills/<n>/`
   pattern apache/airflow uses). The symlinks are **also
   gitignored** — they target the gitignored snapshot, so they
   would dangle on a fresh clone before `/setup-steward` runs.
3. **Overrides.** Adopter-specific modifications to framework
   workflows live as agent-readable markdown under
   `<adopter>/.apache-steward-overrides/<skill>.md`,
   **committed** in the adopter repo. The framework's skills
   consult those files at run-time and apply the overrides
   before executing default behaviour. See
   [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md)
   for the contract.

**No git submodules. No marketplace. No vendored copies of
framework skills.** Just one committed skill (the bootstrap),
a gitignored snapshot, and agent-readable override files.

## Adopting the framework

Two phases — a **shell bootstrap** that gets `setup-steward`
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

1. Adds `.apache-steward/`, `.apache-steward.local.lock`, and
   the framework-skill symlinks to `.gitignore`.
2. Downloads + verifies + extracts the framework into
   `.apache-steward/` (gitignored — build artefact, not
   source).
3. Copies the
   [`setup-steward`](.claude/skills/setup-steward/SKILL.md)
   skill into your skills directory, matching your existing
   convention (flat `.claude/skills/<n>/` or the
   double-symlinked `.claude/skills/<n>` →
   `.github/skills/<n>/` pattern).

After the recipe completes, the framework snapshot is on
disk and the bootstrap skill is in your repo.

### 2. Skill takeover

Tell your agent: **"adopt apache/airflow-steward in my repo"**
(or invoke `/setup-steward` directly). The skill walks
through the rest:

- writes `.apache-steward.lock` (committed) — the project's
  pin: install method + URL + ref + verification anchor;
- writes `.apache-steward.local.lock` (gitignored) — what
  this machine actually fetched + when;
- asks which skill families (`security`, `pr-management`) to
  symlink in;
- creates the gitignored framework-skill symlinks;
- scaffolds `.apache-steward-overrides/` (committed) for any
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
Magpie in this repo" (or invoke `/setup-steward`).
The skill reads `.apache-steward.lock` (already committed)
and re-installs to the same version your project pinned. No
need to redo the manual recipe — the committed lock is the
project's source-of-truth.

### Drift detection

Every framework skill compares the gitignored
`.apache-steward.local.lock` against the committed
`.apache-steward.lock` at the top of its run. If they have
drifted (project lead bumped the pin, or the local install
is stale on a `main`-tracking adopter), the skill surfaces
the gap and proposes `/setup-steward upgrade`. `upgrade`
deletes the gitignored snapshot, re-installs per the
committed pin, refreshes the gitignored symlinks, and
reconciles any agentic overrides — see
[`docs/setup/install-recipes.md`](docs/setup/install-recipes.md)
and
[`.claude/skills/setup-steward/upgrade.md`](.claude/skills/setup-steward/upgrade.md)
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

| Family | Modes | Purpose | Detail |
|---|---|---|---|
| [**setup**](docs/setup/README.md) | (infra) | Isolated agent setup, framework adoption + maintenance, shared-config sync. The prerequisite — at minimum the `setup-steward` skill itself runs out of this family. | 6 skills, [`docs/setup/`](docs/setup/) |
| [**security**](docs/security/README.md) | A, C | 16-step security-issue handling lifecycle — from `security@` import through CVE publication, including state sync. Maintainer-only. | 9 skills, [`docs/security/`](docs/security/) |
| **pr-management** | A | Maintainer-facing PR-queue management — triage, stats, and deep code review. | 3 skills, [`docs/pr-management/`](docs/pr-management/README.md) |
| [**release-management**](docs/release-management/README.md) | A, C | 14-step ASF release lifecycle, planning issue, RC cut + sign, `[VOTE]` thread, tally, promote, `[ANNOUNCE]`, archive, audit log. Agent never holds the RM's signing key and never publishes the release. **Proposed**, spec-first, like Mentoring; skill code lands in follow-up PRs. | 10 skills proposed, [`docs/release-management/`](docs/release-management/) |
| [**mentoring**](docs/mentoring/README.md) | Mentoring | Contributor mentoring — spec and tone guide in place; first skill (`pr-management-mentor`) shipping. **Experimental** — shape may change as adopter pilots and contributor-sentiment evaluation land. | 1 skill, [`docs/mentoring/`](docs/mentoring/README.md) |
| **issue** | A, Triage | Issue lifecycle management — triage, bug reproduction, fix drafting, and backlog re-assessment against the current branch. | 5 skills |
| **utilities** | (meta) | Framework meta-skills: author or update skills (`write-skill`); print a live index of all available skills (`list-steward-skills`). | 2 skills |

## Maintenance

After the initial adoption, the same skill handles ongoing
maintenance:

- `/setup-steward upgrade` — refresh the snapshot to a newer
  framework version + reconcile any overrides against the new
  framework structure.
- `/setup-steward verify` — read-only health check (snapshot
  intact, symlinks live, `.gitignore` correct, etc.).
- `/setup-steward override <framework-skill>` — open or
  scaffold an override file for a framework skill.

## Cross-references

- [`MISSION.md`](MISSION.md) — **draft** project-establishment proposal: motivation, scope, design commitments, initial PMC composition target.
- [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md) — the contract between adopters who write overrides and framework skills that read them.
- [`docs/prerequisites.md`](docs/prerequisites.md) — what a maintainer needs installed before invoking any framework skill (Claude Code, Gmail MCP, GitHub auth, browser, `uv`, etc.).
- [`AGENTS.md`](AGENTS.md) — agent instructions, placeholder convention, framework conventions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — for framework contributors.
