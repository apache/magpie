<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [What is Apache Magpie?](#what-is-apache-magpie)
  - [How it works](#how-it-works)
  - [Skill families](#skill-families)
  - [Who is this for?](#who-is-this-for)
    - [Anyone who wants agent help on a repo](#anyone-who-wants-agent-help-on-a-repo)
    - [Maintainers adopting Magpie for their project](#maintainers-adopting-magpie-for-their-project)
    - [Security team members](#security-team-members)
    - [Contributors to the Magpie framework itself](#contributors-to-the-magpie-framework-itself)
    - [People evaluating whether to adopt](#people-evaluating-whether-to-adopt)
    - [Security and privacy setup](#security-and-privacy-setup)
  - [Key concepts](#key-concepts)
  - [Where to go next](#where-to-go-next)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# What is Apache Magpie?

Apache Magpie is a set of skills for AI agents, used to triage issues, review pull requests, mentor contributors, handle security reports, and prepare releases.
Each skill defines a workflow and the points where a person must review or approve its output.
Shared-state changes, such as posting a comment or applying a label, require explicit confirmation.

Start with the [quick start](quick-start.md) to install Magpie and configure it for a repository.
The [prerequisites](quick-start/prerequisites.md) list access requirements, including GitHub authentication and mail backends for skills that use them.

## How it works

You install a skill family, configure the repository it will work against, and ask your agent to run a task.
The skill reads the relevant data and produces a report, draft, or proposed change.
You can correct the proposal, approve permitted actions, or stop without applying them.

For example, ask:

> Summarize this repository's open PR backlog. Do not post comments or change labels.

Use the summary to decide which PRs need review.
Request a review of a specific PR as a separate task.

Five [modes](modes.md) describe the kinds of assistance:

| Mode | What it does | Status |
|---|---|---|
| **Agentic Triage** | Classify issues/PRs, spot duplicates, propose labels | Stable |
| **Agentic Mentoring** | Help contributors with conventions, point to examples | Experimental |
| **Agentic Drafting** | Write a code fix or a PR for you to review | Stable (security) |
| **Agentic Pairing** | Self-review your own code before submitting | Experimental |
| **Agentic Autonomous** | Merge trivial changes without human review | Disabled |

Projects opt into the modes they need; using triage does not require enabling drafting or pairing.

<a id="need-help-with-one-of-these-adopt-a-family-of-skills"></a>

## Skill families

Install families by task.
Each family guide lists its skills, configuration requirements, and first-run examples.

Most families are organization-independent.
Families marked **ASF-specific** use Foundation processes by default; other organizations need configuration or adapters for their own release and governance processes.

| Task | Family | Scope |
|---|---|---|
| Installation, sandboxing, and privacy configuration | [setup](setup/README.md) | Any project |
| Security-report intake, triage, and disclosure | [security](security/README.md) | Any project |
| PR triage, code review, and queue reports | [pr-management](pr-management/README.md) | Any project |
| Local diff review before submitting a PR | [pairing](pairing/README.md) | Any project |
| Issue triage, reproduction, and backlog maintenance | [issue-management](issue-management/README.md) | Any project |
| CI, dependency, licence, and flaky-test audits | [repo-health](repo-health/README.md) | Any project |
| Release candidates, votes, and announcements | [release-management](release-management/README.md) | ASF-specific |
| Newcomer guidance and good-first-issue preparation | [mentoring](mentoring/README.md) | Any project |
| Contributor activity, nominations, and onboarding | [contributor-growth](contributor-growth/README.md) | ASF-specific |
| Skill discovery, authoring, and maintenance | [utilities](utilities/README.md) | Any project |

Install [`setup`](setup/README.md) first.
The [baseline plugins](quick-start/families.md#start-with-the-baseline) also include `magpie-agent-guard` and `magpie-utilities`.

## Who is this for?

### Anyone who wants agent help on a repo

Install Magpie for your own use without committing shared configuration.
See the [quick start](quick-start.md) and [individual use](setup/individual-use.md).
If your agent has no marketplace, use one of the [other installation methods](quick-start/other-install-methods.md).

### Maintainers adopting Magpie for their project

Commit a recommended plugin set and shared project configuration.
[Team adoption](setup/team-adoption.md) describes the files involved and how contributors receive updates.
Adoption does not require contributors to use Magpie.

### Security team members

Use the [security workflow overview](security/README.md) for the report-to-publication lifecycle.
[How the security team works](security/how-the-security-team-works.md) covers team responsibilities and onboarding.
Configure privacy controls before loading private reports.

### Contributors to the Magpie framework itself

Start with [CONTRIBUTING.md](../CONTRIBUTING.md) for repository layout, local setup, and requirements for patches.
The [spec-driven development](spec-driven-development.md) guide describes the specification workflow.

### People evaluating whether to adopt

Read [MISSION.md](../MISSION.md) for scope, [PRINCIPLES.md](../PRINCIPLES.md) for design requirements, and [mode economics](mode-economics.md) for token-cost estimates.

### Security and privacy setup

Use [secure agent setup](setup/secure-agent-setup.md) to configure filesystem access, network access, and command guards.
Use [privacy setup](setup/privacy-llm.md) to configure which models may receive private content and how third-party personal information is redacted.
Available isolation and guard mechanisms vary by [adapter](adapters/README.md).

## Key concepts

| Term | Meaning | Example |
|---|---|---|
| Skill | A Markdown workflow the agent follows. | Triage an open issue and propose a disposition. |
| Family | A group of related skills installed together. | `pr-management` includes triage, review, and queue statistics. |
| Mode | A category of assistance that a project opts into. | Drafting produces a proposed fix for review. |
| Project configuration | Repository-specific settings resolved through `<project-config>`. | The upstream repository, label scheme, and canned responses. |
| Sandbox | Restrictions on an agent process's filesystem and network access. | Preventing reads of home-directory credential files. |
| Human-in-the-loop | Explicit approval before a proposed shared-state change. | Reviewing a drafted comment before it is posted. |

## Where to go next

| I want to… | Read… |
|---|---|
| Understand the full vision | [MISSION.md](../MISSION.md) |
| Understand how it stays vendor-neutral | [vendor-neutrality.md](vendor-neutrality.md) |
| Find or author a backend adapter | [adapters/](adapters/README.md) |
| Pull a skill/family from a trusted external source | [skill-sources/README.md](skill-sources/README.md) |
| Extend Magpie (project / org / individual) | [extending.md](extending.md) |
| See what skills exist today | [modes.md](modes.md) |
| Install it right now | [quick-start.md](quick-start.md) |
| Check what a skill needs before it runs | [quick-start/prerequisites.md](quick-start/prerequisites.md) |
| Install in my project | [README → Install](../README.md#install) |
| Set up the secure agent sandbox | [setup/](setup/README.md) |
| Understand the security workflow | [security/](security/README.md) |
| Know what it costs to run | [mode-economics.md](mode-economics.md) |
| Read the design behind a change in flight | [designs/](designs/README.md) |
| Understand the privacy model | [rfcs/RFC-AI-0003.md](rfcs/RFC-AI-0003.md) |
| Read the RFCs behind the design | [rfcs/](rfcs/README.md) |
| Contribute to the framework | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Learn to build and extend skills | [education/](education/README.md) |
