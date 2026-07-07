<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [What is Apache Magpie?](#what-is-apache-magpie)
  - [How it works](#how-it-works)
  - [Need help with one of these? Adopt a family of skills](#need-help-with-one-of-these-adopt-a-family-of-skills)
  - [Who is this for?](#who-is-this-for)
    - [Maintainers wanting to adopt Magpie in their project](#maintainers-wanting-to-adopt-magpie-in-their-project)
    - [Security team members](#security-team-members)
    - [Contributors to the Magpie framework itself](#contributors-to-the-magpie-framework-itself)
    - [People evaluating whether to adopt](#people-evaluating-whether-to-adopt)
    - [People who are concerned for security and privacy when using their agents](#people-who-are-concerned-for-security-and-privacy-when-using-their-agents)
  - [Key concepts in 60 seconds](#key-concepts-in-60-seconds)
  - [Where to go next](#where-to-go-next)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# What is Apache Magpie?

Apache Magpie is an AI assistant for open-source project maintainers. It handles the repetitive parts of running a project — triaging issues, reviewing PRs, onboarding contributors, managing security reports, cutting releases — so maintainers can spend their time on design, relationships, and the work that actually requires a human.

**The agent proposes. The human decides.** Magpie never merges, never pushes, never sends mail, never flips a label without a maintainer confirming first.

---

## How it works

Magpie provides **skills** — step-by-step workflows an AI agent follows. You pick which skills your project uses. The agent reads your issues, PRs, or security reports, does the analysis, and drafts a response. You review it and hit "go" (or don't).

Five **modes** describe what the agent can do, from low-risk to high:

| Mode | What it does | Status |
|---|---|---|
| **Agentic Triage** | Classify issues/PRs, spot duplicates, propose labels | Stable |
| **Agentic Mentoring** | Help contributors with conventions, point to examples | Experimental |
| **Agentic Drafting** | Write a code fix or a PR for you to review | Stable (security) |
| **Agentic Pairing** | Self-review your own code before submitting | Experimental |
| **Agentic Autonomous** | Merge trivial changes without human review | Off (deliberately) |

Each project picks the modes that fit. You can run just Agentic Triage and nothing else.

---

## Need help with one of these? Adopt a family of skills

Magpie's skills ship in **families**. You don't adopt all of them — you pick the ones that match a problem you actually have today. Each family page explains what it does, which skills it includes, and how to turn it on.

Most families work on **any** project, inside or outside the Apache Software
Foundation. The ones marked **🪶 ASF-specific** encode Foundation processes —
the release lifecycle and the contributor-to-committer path — and assume an ASF
adopter profile by default; a non-ASF project can still adopt them through the
adapter/config layer, but they carry ASF assumptions the generic families do not.

| If you're dealing with… | Adopt the family | Scope |
|---|---|---|
| Setting up agents safely — sandbox, clean environment, privacy routing | [setup](setup/README.md) | Any project |
| Security reports that need careful, audited handling | [security](security/README.md) | Any project |
| A pull-request queue that's out of control | [pr-management](pr-management/README.md) | Any project |
| An issue backlog full of duplicates and stale reports | [issue-management](issue-management/README.md) | Any project |
| Repo hygiene slipping — CI runners, dependencies, licenses, flaky tests | [repo-health](repo-health/README.md) | Any project |
| Releases that are a manual, error-prone slog | [release-management](release-management/README.md) | 🪶 ASF-specific |
| New contributors getting stuck and drifting away | [mentoring](mentoring/README.md) | Any project |
| Growing contributors into committers | [contributor-growth](contributor-growth/README.md) | 🪶 ASF-specific |
| Building or maintaining your own skills | [utilities](utilities/README.md) | Any project |

Start with [`setup`](setup/README.md) regardless — it is the prerequisite every adopter installs first — then add the families above as you need them.

---

## Who is this for?

### Maintainers wanting to adopt Magpie in their project

You have an open-source project with an issue tracker and/or PR queue, and you want agent assistance with the mechanical parts.

→ Start with the [README](../README.md#adopting-the-framework) (adoption steps) and [install recipes](setup/install-recipes.md).

### Security team members

You handle CVE reports and want agent help with the 16-step lifecycle — import, triage, fix, allocate, publish.

→ Start with [security workflow overview](security/README.md), then [new member onboarding](security/new-members-onboarding.md).

### Contributors to the Magpie framework itself

You want to improve the skills, add tools, or fix bugs in the framework.

→ Start with [CONTRIBUTING.md](../CONTRIBUTING.md) and the [spec-driven development](spec-driven-development.md) loop.

### People evaluating whether to adopt

You want to understand the trust model, cost, and governance commitments before deciding.

→ Read [MISSION.md](../MISSION.md) (the why), [PRINCIPLES.md](../PRINCIPLES.md) (the rules), and [mode economics](mode-economics.md) (what it costs in tokens).

### People who are concerned for security and privacy when using their agents

You would like to use agentic AI but you are concerned about security and privacy - when LLMs / Agent
might get access to your credentials and poison your workstation, or have access to private information
from mailing lists, slack etc.

→ When you setup Magpie, it will setup your workstation with security guardrail layers that will run your agents in containerized sandbox, and it will setup privacy gateways for the tools your agentic setup will use. Read more details in [Secure agent setup RFC](../docs/rfcs/RFC-AI-0002.md) and [Privacy-aware LLM routing for foundation private information](../docs/rfcs/RFC-AI-0003.md).

---

## Key concepts in 60 seconds

- **Skill** — A markdown file describing one workflow (e.g., "triage a PR"). The agent reads it and follows the steps.
- **Mode** — A risk level (Agentic Triage → Agentic Mentoring → Agentic Drafting → Agentic Pairing → Agentic Autonomous). Projects opt in per-mode.
- **Adopter config** — Your project-specific settings (mailing lists, label schemes, canned responses) in a `<project-config>/` directory.
- **Sandbox** — The agent runs in a locked-down environment. It can't read your credentials, can't access the network freely, and can't push code.
- **Human-in-the-loop** — Every action visible to others requires explicit maintainer confirmation. No exceptions until Agentic Autonomous (which is off).

---

## Where to go next

| I want to… | Read… |
|---|---|
| Understand the full vision | [MISSION.md](../MISSION.md) |
| Understand how it stays vendor-neutral | [vendor-neutrality.md](vendor-neutrality.md) |
| Find or author a backend adapter | [adapters/registry.md](adapters/registry.md) |
| Pull a skill/family from a trusted external source | [skill-sources/README.md](skill-sources/README.md) |
| Extend Magpie (project / org / individual) | [extending.md](extending.md) |
| See what skills exist today | [modes.md](modes.md) |
| Adopt in my project | [README → Adopting](../README.md#adopting-the-framework) |
| Set up the secure agent sandbox | [setup/](setup/README.md) |
| Understand the security workflow | [security/](security/README.md) |
| Know what it costs to run | [mode-economics.md](mode-economics.md) |
| Understand the privacy model | [rfcs/RFC-AI-0003.md](rfcs/RFC-AI-0003.md) |
| Contribute to the framework | [CONTRIBUTING.md](../CONTRIBUTING.md) |
| Learn to build and extend skills | [education/](education/README.md) |
