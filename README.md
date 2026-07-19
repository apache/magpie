<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie](#apache-magpie)
  - [Install](#install)
  - [Usage](#usage)
  - [Update / maintain](#update--maintain)
  - [Skill families](#skill-families)
    - [External skill sources](#external-skill-sources)
  - [Acknowledgements](#acknowledgements)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Apache Magpie

[![Magpie](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/apache/magpie/main/assets/badge.json)](https://magpie.apache.org/)

**Adopt a Magpie.** Apache Magpie provides high-quality recipes for
agent-assisted software project maintenance.

These recipes allow human maintainers working with AIs to efficiently handle
the repetitive parts of running an open-source project: issue triage, PR
review, mentoring contributors, managing security reports, and more.

Magpie is currently in development for ASF projects + Python Core team
friendlies. Testers welcome!

> [!IMPORTANT]
> The motivation, scope, and design commitments behind this work
> live in [`MISSION.md`](MISSION.md) — the founding mission of the
> Apache Magpie Top-Level Project, originally filed as its
> establishment proposal. Read that for the *why*; this README is
> the *how* once you've decided to install.

## Install

Magpie's recipes are plain-text instructions followed by an AI agent you
control. There are two ways to install them:

**From an agent marketplace (easiest).** Install the skills directly into your
agent — Claude Code, Codex, Copilot, Gemini, Cursor, and more — with nothing
committed to your repository. See
[`docs/setup/marketplaces.md`](docs/setup/marketplaces.md).

**As a committed snapshot (full install into your repo).** For a project that
installs Magpie as part of its own source — pin a release and let
`/magpie-setup` set up the snapshot, overrides, and drift detection in the
adopter repo:

1. [Download / pin a release](https://magpie.apache.org/downloads/)
2. Set up the symlinks and git-ignores — see
   [`docs/setup/install-recipes.md`](docs/setup/install-recipes.md)
3. Ask your agent to complete the install: `/magpie-setup install`
   (`/magpie-setup adopt` is an alias)

## Usage

Magpie is used by interacting with your AI agents. You'll use plain-language
prompts like

> review PR #5193

or

> triage the latest security reports

or skill calls starting with a slash, like

> /dependency-audit

## Update / maintain

- `/magpie-setup upgrade` — refresh the snapshot to a newer
  framework version + reconcile any overrides against the new
  framework structure.
- `/magpie-setup verify` — read-only health check (snapshot
  intact, symlinks live, `.gitignore` correct, etc.).
- `/magpie-setup override <framework-skill>` — open or
  scaffold an override file for a framework skill.

## Skill families

The following skill families ship in the framework, all at `experimental` or
`stable`, and each skill declares its family in a `family:` frontmatter
key. At install (and on every upgrade), `/magpie-setup` offers the
**opt-in** families — and the optional **MCP servers** (`ponymail`,
`apache-projects`, `gmail-plaintext`) — in a single install choice;
symlinks for the picked families land in the skill directory.
The two **always-on** families (`setup`, `utilities`) are wired
unconditionally and never prompted for.

The **Modes** column maps each family to the MISSION agent-assistance
taxonomy — see [`docs/modes.md`](docs/modes.md) for what each mode
means and which modes are still proposed vs. shipping today.

| Family | Type | Modes | Purpose | Detail |
|---|---|---|---|---|
| [**setup**](docs/setup/README.md) | always-on | (infra) | Isolated agent setup, framework install + maintenance, shared-config sync. The prerequisite — at minimum the `setup` skill itself runs out of this family. | 9 skills, [`docs/setup/`](docs/setup/) |
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

Skill families or individual skills can be pulled
from a **trusted external source** — a repo other than `apache/magpie` that
ships Magpie-shaped skills (with their evals and tests). Where a skill
directory would sit, a `skills/<name>/source.md` **redirect** names a
pinned, verified source the adopter has vouched for; `/magpie-setup` fetches
it into the gitignored snapshot and wires it in exactly like a framework
skill. Nothing is fetched unless the adopter commits the pin — see
[`docs/skill-sources/`](docs/skill-sources/README.md),
[`PRINCIPLES.md` §13](PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
and [`RFC-AI-0006`](docs/rfcs/RFC-AI-0006.md).

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
