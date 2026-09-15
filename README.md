<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie](#apache-magpie)
  - [See it in action](#see-it-in-action)
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

Apache Magpie provides skills for AI agents that assist with open-source project maintenance.
The skills cover issue and pull-request triage, code review, contributor mentoring, fix drafting, and security-report handling.
They work with Claude Code, Codex, Gemini CLI, Copilot, and other agents; support varies by [adapter](docs/adapters/README.md).

Skills propose actions for human review.
Posting comments, changing labels, and other shared-state changes require explicit confirmation.
Autonomous operation is disabled.

The [secure setup](docs/setup/secure-agent-setup.md) provides filesystem and network isolation, a credential-stripped environment, and command guards where the agent supports them.
These protections require setup; installing a skill family alone does not enable them.

Magpie is licensed under Apache-2.0 and requires no Magpie account or hosted service.
Project telemetry is opt-in and disabled by default.
The framework is under development, with current testing focused on ASF projects and Python Core contributors.

## See it in action

This example follows a security report from installation and secure setup through intake, triage, fix drafting, and CVE publication.

![Installing Magpie from the marketplace, running the secure-agent and privacy setup, then importing two security reports, triaging one as a high-severity path traversal and the other as not a vulnerability, drafting the fix as a scrubbed public PR, and publishing the CVE](assets/quickstart/demo.svg)

*Illustrative transcript, not a recording.*
The [interactive version](https://magpie.apache.org/#see-it-in-action) lets you step through each command and its output.
For the project's scope and design commitments, see [`MISSION.md`](MISSION.md).

## Install

Follow the [quick start](docs/quick-start.md) for your agent.
For example, in Claude Code:

```text
/plugin marketplace add apache/magpie                # Claude Code
/plugin install magpie-setup@apache-magpie           # install first
/plugin install magpie-agent-guard@apache-magpie     # command guard
/plugin install magpie-utilities@apache-magpie       # skill index and authoring tools
/plugin install magpie-pr-management@apache-magpie   # PR triage and review
```

The first three plugins are the recommended baseline.
Add a plugin for each family you need.
Installed skill descriptions consume context even when unused, approximately 0.2–2.0k tokens per family; there is no combined install-everything plugin.

After installing `magpie-setup`, you can also request families in plain language:

> Install the Magpie families for PR review.

Plugin installation is per-user and does not modify your repository.
Project configuration, isolation, and privacy setup are separate steps covered in the quick start.

**Pinned-snapshot alternative.** Use a snapshot if your agent has no plugin mechanism, you need a signed ASF source release, or contributors and CI jobs must use a committed version pin with drift detection.

1. [Download / pin a release](https://magpie.apache.org/downloads/)
2. Set up the symlinks and git-ignores — see
   [other installation methods](docs/quick-start/other-install-methods.md)
3. Ask your agent to complete the install: `/magpie-setup install`

You can use personal marketplace plugins alongside a project's pinned snapshot.

## Usage

Ask your agent for a task, including the repository and scope when needed:

> Summarize the open PR backlog for this repository. Do not post comments or change labels.

For a named skill, use the command supplied by your install method.
For example, a marketplace install provides:

```text
/magpie-repo-health:dependency-audit
```

This audit reports dependency vulnerabilities and proposed upgrades without changing manifests or lock files.
Review the report before deciding which upgrades to make.
If project configuration is missing, the skill starts the setup flow before running the audit.

See [skill names by install method](docs/setup/marketplace.md#skill-names-differ-by-install-method) for pinned-snapshot commands.

## Update / maintain

**Marketplace install** (the recommended path above):

- `/plugin marketplace update apache-magpie` then
  `/plugin update <plugin>@apache-magpie` — refresh the marketplace
  metadata, then bump the installed plugin(s) to its latest.
- Add or drop families by installing or uninstalling their plugin —
  there is no separate "pick families" step once you're on a
  marketplace install.

**Pinned-snapshot install** (the fallback):

- `/magpie-setup upgrade` — refresh the snapshot to a newer
  framework version + reconcile any overrides against the new
  framework structure.
- `/magpie-setup verify` — read-only health check (snapshot
  intact, symlinks live, `.gitignore` correct, etc.).
- `/magpie-setup override <framework-skill>` — open or
  scaffold an override file for a framework skill.

## Skill families

Marketplace installs select families by plugin; pinned-snapshot installs select them through `/magpie-setup`.
The `setup` and `utilities` families are included in the baseline.
The snapshot setup also offers optional MCP servers: `ponymail`, `apache-projects`, and `gmail-plaintext`.

The **Modes** column uses the [agent-assistance taxonomy](docs/modes.md).
Family guides document each skill's maturity and requirements.

| Family | Type | Modes | Purpose | Detail |
|---|---|---|---|---|
| [**setup**](docs/setup/README.md) | always-on | (infra) | Isolated agent setup, framework install + maintenance, shared-config sync. The prerequisite — at minimum the `setup` skill itself runs out of this family. | 10 skills, [`docs/setup/`](docs/setup/) |
| **utilities** | always-on | (meta) | Framework meta-skills: author skills (`write-skill`), restructure them (`optimize-skill`), reconcile skill state (`skill-reconciler`), report framework issues (`report-framework-issue`), and print a live index (`list-skills`). | 5 skills |
| [**security**](docs/security/README.md) | opt-in | Triage, Drafting | 16-step security-issue handling lifecycle — from `security@` import through CVE publication, including state sync — plus producing, verifying, and maintaining the project's own security model. Maintainer-only. | 15 skills, [`docs/security/`](docs/security/) |
| [**pr-management**](docs/pr-management/README.md) | opt-in | Triage | Maintainer-facing PR-queue management — triage, stats, deep code review, express-lane merge, stale-sweep, reviewer routing, and pre-first-PR checks. | 8 skills, [`docs/pr-management/`](docs/pr-management/README.md) |
| [**issue**](docs/issue-management/README.md) | opt-in | Triage, Drafting | General-issue lifecycle: triage, reproduction, fix drafting, reassess, stale-sweep, deduplication, and backlog reporting. | 8 skills, [`docs/issue-management/`](docs/issue-management/README.md) |
| [**release-management**](docs/release-management/README.md) | opt-in | Triage, Drafting | 14-step ASF release lifecycle, planning issue, RC cut + sign, `[VOTE]` thread, tally, promote, `[ANNOUNCE]`, archive, audit log. Agent never holds the RM's signing key and never publishes the release. **Experimental**, all 10 skills shipped. | 10 skills, [`docs/release-management/`](docs/release-management/) |
| [**repo-health**](docs/repo-health/README.md) | opt-in | Triage | Read-only repository-health audits: obsolete runner labels, Actions workflow security, dependency vulnerabilities, dependency licence review, license/NOTICE compliance, flaky-test patterns, plus audit-finding fixes. | 7 skills, [`docs/repo-health/`](docs/repo-health/) |
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

- [`MISSION.md`](MISSION.md) — founding mission of the established TLP: motivation, scope, design commitments, initial PMC composition target.
- [`docs/setup/agentic-overrides.md`](docs/setup/agentic-overrides.md) — the contract between adopters who write overrides and framework skills that read them.
- [`docs/prerequisites.md`](docs/quick-start/prerequisites.md) — what a maintainer needs installed before invoking any framework skill (Claude Code, Gmail MCP, GitHub auth, browser, `uv`, etc.).
- [`docs/source-release-contents.md`](docs/source-release-contents.md) — what ships in the signed `apache-magpie-<version>-source.zip` (and what is excluded), with the rationale for the repository-root metadata/config files it keeps.
- [`docs/release-management/manual-release-process.md`](docs/release-management/manual-release-process.md) — the concrete, as-executed runbook for cutting a Magpie release by hand on the current hybrid SVN-dist + ATR-vote backend (with the abstract per-backend runbooks and the 14-step lifecycle alongside it in [`docs/release-management/`](docs/release-management/README.md)).
- [`AGENTS.md`](AGENTS.md) — agent instructions, placeholder convention, framework conventions.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — for framework contributors.
