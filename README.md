<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

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
    - [External skill sources](#external-skill-sources)
  - [Maintenance](#maintenance)
  - [Acknowledgements](#acknowledgements)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Apache Magpie

[![Magpie](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/apache/magpie/main/assets/badge.json)](https://magpie.apache.org/)

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
> live in [`MISSION.md`](MISSION.md) — the founding mission of the
> Apache Magpie Top-Level Project, originally filed as its
> establishment proposal. Read that for the *why*; this README is
> the *how* once you've decided to adopt.

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

Ten skill families ship in the framework, all at `experimental` or
`stable`, and each skill declares its family in a `family:` frontmatter
key. At adoption (and on every upgrade), `/magpie-setup` offers the
**opt-in** families — and the optional **MCP servers** (`ponymail`,
`apache-projects`, `gmail-plaintext`) — in a single install choice;
symlinks for the picked families land in the adopter's skill directory.
The two **always-on** families (`setup`, `utilities`) are wired
unconditionally and never prompted for.

The **Modes** column maps each family to the MISSION agent-assistance
taxonomy — see [`docs/modes.md`](docs/modes.md) for what each mode
means and which modes are still proposed vs. shipping today.

| Family | Type | Modes | Purpose | Detail |
|---|---|---|---|---|
| [**setup**](docs/setup/README.md) | always-on | (infra) | Isolated agent setup, framework adoption + maintenance, shared-config sync. The prerequisite — at minimum the `setup` skill itself runs out of this family. | 9 skills, [`docs/setup/`](docs/setup/) |
| **utilities** | always-on | (meta) | Framework meta-skills: author skills (`write-skill`), restructure them (`optimize-skill`), reconcile skill state (`skill-reconciler`), and print a live index (`list-skills`). | 4 skills |
| [**security**](docs/security/README.md) | opt-in | Triage, Drafting | 16-step security-issue handling lifecycle — from `security@` import through CVE publication, including state sync. Maintainer-only. | 12 skills, [`docs/security/`](docs/security/) |
| [**pr-management**](docs/pr-management/README.md) | opt-in | Triage | Maintainer-facing PR-queue management — triage, stats, deep code review, express-lane merge, stale-sweep, reviewer routing, and pre-first-PR checks. | 8 skills, [`docs/pr-management/`](docs/pr-management/README.md) |
| [**issue**](docs/issue-management/README.md) | opt-in | Triage, Drafting | General-issue lifecycle: triage, reproduction, fix drafting, reassess, stale-sweep, deduplication, and backlog reporting. | 8 skills, [`docs/issue-management/`](docs/issue-management/README.md) |
| [**release-management**](docs/release-management/README.md) | opt-in | Triage, Drafting | 14-step ASF release lifecycle, planning issue, RC cut + sign, `[VOTE]` thread, tally, promote, `[ANNOUNCE]`, archive, audit log. Agent never holds the RM's signing key and never publishes the release. **Experimental**, all 10 skills shipped. | 10 skills, [`docs/release-management/`](docs/release-management/) |
| [**repo-health**](docs/repo-health/README.md) | opt-in | Triage | Read-only repository-health audits: obsolete runner labels, Actions workflow security, dependency vulnerabilities, license/NOTICE compliance, flaky-test patterns, plus audit-finding fixes. | 6 skills, [`docs/repo-health/`](docs/repo-health/) |
| [**pairing**](docs/pairing/README.md) | opt-in | Pairing | Pair a change with a structured self-review or a multi-agent adversarial review before it lands. | 2 skills, [`docs/pairing/`](docs/pairing/README.md) |
| [**mentoring**](docs/mentoring/README.md) | opt-in | Mentoring | Newcomer-facing mentoring — first-contact welcome, newcomer-issue explanations, and good-first-issue authoring + backlog curation. **Experimental**. | 4 skills, [`docs/mentoring/`](docs/mentoring/README.md) |
| [**contributor-growth**](docs/contributor-growth/README.md) | opt-in | Triage, Mentoring | The path-to-committer track: activity sweeps, nomination briefs, contributor-sentiment signals, readiness tracking, and committer / post-vote onboarding. | 6 skills, [`docs/contributor-growth/`](docs/contributor-growth/README.md) |

### External skill sources

Beyond the in-tree families, an adopter can pull a skill or whole family
from a **trusted external source** — a repo other than `apache/magpie` that
ships Magpie-shaped skills (with their evals and tests). Where a skill
directory would sit, a `skills/<name>/source.md` **redirect** names a
pinned, verified source the adopter has vouched for; `/magpie-setup` fetches
it into the gitignored snapshot and wires it in exactly like a framework
skill. Nothing is fetched unless the adopter commits the pin — see
[`docs/skill-sources/`](docs/skill-sources/README.md),
[`PRINCIPLES.md` §13](PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
and [`RFC-AI-0006`](docs/rfcs/RFC-AI-0006.md).

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

## Acknowledgements

Apache Magpie was first developed and proven inside **Apache Airflow**, and was
maintained for a time as the `apache/airflow-steward` repository under the
Airflow PMC before being renamed and established as its own project. It also
incorporates early skill work contributed by way of the **Apache Groovy**
community. All of that code carries the same rightsholder — Copyright The Apache
Software Foundation, under the Apache License 2.0 — so it is not a third-party
inclusion; the required attribution lines from the originating projects' NOTICE
files are reproduced in [`NOTICE`](NOTICE).

## Cross-references

- [`MISSION.md`](MISSION.md) — **draft** project-establishment proposal: motivation, scope, design commitments, initial PMC composition target.
- [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md) — the contract between adopters who write overrides and framework skills that read them.
- [`docs/prerequisites.md`](docs/prerequisites.md) — what a maintainer needs installed before invoking any framework skill (Claude Code, Gmail MCP, GitHub auth, browser, `uv`, etc.).
- [`docs/source-release-contents.md`](docs/source-release-contents.md) — what ships in the signed `apache-magpie-<version>-source.zip` (and what is excluded), with the rationale for the repository-root metadata/config files it keeps.
- [`docs/release-management/manual-release-process.md`](docs/release-management/manual-release-process.md) — the concrete, as-executed runbook for cutting a Magpie release by hand on the current hybrid SVN-dist + ATR-vote backend (with the abstract per-backend runbooks and the 14-step lifecycle alongside it in [`docs/release-management/`](docs/release-management/README.md)).
- [`AGENTS.md`](AGENTS.md) — agent instructions, placeholder convention, framework conventions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — for framework contributors.
