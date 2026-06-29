<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How Magpie achieves vendor neutrality](#how-magpie-achieves-vendor-neutrality)
  - [Two questions that get conflated](#two-questions-that-get-conflated)
  - [The five axes of neutrality](#the-five-axes-of-neutrality)
  - [The mechanism: skills, tools, capabilities](#the-mechanism-skills-tools-capabilities)
    - [Skills target the abstraction, never a vendor's client](#skills-target-the-abstraction-never-a-vendors-client)
    - [Tools are the only place vendor-specific code lives](#tools-are-the-only-place-vendor-specific-code-lives)
    - [Capabilities are the contract between them](#capabilities-are-the-contract-between-them)
  - [How each axis is delivered](#how-each-axis-is-delivered)
    - [1. LLM backend](#1-llm-backend)
    - [2. Agentic runtime](#2-agentic-runtime)
    - [3. Forge and tracker](#3-forge-and-tracker)
    - [4. Source control (VCS)](#4-source-control-vcs)
    - [5. Project governance](#5-project-governance)
  - [What keeps it neutral over time](#what-keeps-it-neutral-over-time)
  - [The contribution model — neutrality as an invitation](#the-contribution-model--neutrality-as-an-invitation)
  - [Status at a glance](#status-at-a-glance)
  - [What "vendor neutral" does and does not claim](#what-vendor-neutral-does-and-does-not-claim)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# How Magpie achieves vendor neutrality

Vendor neutrality is one of Magpie's non-negotiable design principles
([`PRINCIPLES.md` §9](../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable),
[§3](../PRINCIPLES.md#3-project-autonomy-is-the-structural-starting-point))
and a top-to-bottom mission commitment
([`MISSION.md` § Affordability and vendor neutrality](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment)).
Those documents state *that* the framework is vendor-neutral and *why*.
This page explains **how** — the architecture that delivers it, what is
neutral by construction today, and where the extension points are for
backends that do not yet have a reference implementation.

It is the answer to the recurring question *"is Magpie really vendor
neutral?"* The honest answer starts with a distinction.

## Two questions that get conflated

"Is X vendor neutral?" almost always collapses two very different
questions into one:

- **(a) Is the architecture vendor-neutral?** — i.e. can a new vendor
  be supported without rewriting the workflows, and does anything in
  the design privilege one vendor or lock the rest out?
- **(b) Is every possible vendor already implemented and tested
  today?** — i.e. does the box ship with a finished, hardened backend
  for every LLM, every forge, every tracker, every VCS in existence?

These have different answers, and only the first is a meaningful test
of neutrality:

- **(a) is 100% true and is the whole point of the skills + tools
  architecture below.** No workflow is written against a vendor; every
  vendor binding lives behind a capability contract that a contributor
  can implement without touching a single skill.
- **(b) is impossible *by definition* — for everyone.** No framework
  in this space ships a complete, tested implementation of every
  backend, because the set is open-ended and grows faster than anyone
  can implement it. If "vendor neutral" is defined as "has 100% of all
  possible vendor implementations," then no solution that has ever
  existed is vendor neutral, and the term means nothing.

So Magpie's claim is precise: **the architecture is vendor-neutral, a
range of backends already work end-to-end, nothing in the design
prevents adding more, and adding one is a contribution against a
documented contract — not a fork of the workflows.** That is what
"vendor neutral" means here, and it is the only definition that is both
achievable and useful.

## The five axes of neutrality

"Vendor" is not one thing. Magpie is neutral across five independent
axes, and a backend choice on one axis never constrains the others:

| Axis | The "vendor" | Neutral by… |
|---|---|---|
| **LLM backend** | Anthropic, OpenAI, Google, Bedrock, local Ollama/vLLM, a future ASF endpoint | Skills written against a model *contract* (capability floor), not a client; a privacy gate that keys on endpoint identity, not on who hosts it |
| **Agentic runtime** | Claude Code, Codex, Cursor, Gemini CLI, Copilot, OpenCode, Kiro, … | Skills are [`AGENTS.md`](https://agents.md/)-standard markdown under a shared `.agents/skills/` home that every runtime reads |
| **Forge / tracker** | GitHub, GitLab, Gitea, Forgejo, Pagure, Bitbucket, Jira, mailing lists | Per-interface **tools** behind capability contracts; many tools are pure adapter *specs* with pluggable backends |
| **Source control (VCS)** | Git, Mercurial, Subversion, Jujutsu, Fossil, Perforce, … | A single `VCSBackend` contract; skills call the abstract operation, the backend is detected from the working copy |
| **Project governance** | ASF PMC, foundation-hosted, single-vendor, informal maintainer group | Modes and thresholds are adopter config; non-ASF adopters are first-class ([`PRINCIPLES.md` §3](../PRINCIPLES.md#3-project-autonomy-is-the-structural-starting-point)) |

The rest of this page walks the mechanism that makes all five true,
then states exactly where each axis stands today.

## The mechanism: skills, tools, capabilities

Magpie's neutrality is not a promise bolted onto the side — it falls
out of a three-layer architecture. The same three layers explain the
[label taxonomy](labels-and-capabilities.md); here they are read as the
neutrality mechanism.

```text
  SKILLS  ── generic workflows, written in English, zero vendor names
    │  declare the capabilities they need
    ▼
  CAPABILITIES  ── the contract: "source-control", "CVE allocation",
    │             "mail archive read", "tracker write", …
    ▼
  TOOLS  ── the only layer that knows a vendor exists; one tool (or
            one adapter) per concrete backend, fulfilling a capability
```

### Skills target the abstraction, never a vendor's client

A skill is a step-by-step workflow in markdown. By
[`PRINCIPLES.md` §9](../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable),
**a skill hard-coded to one vendor or model family is broken, not
specialized.** Skills name *capabilities* they need ("read the mail
archive", "open a change for review", "allocate a CVE"), never a
vendor's API. A concrete name (`apache/airflow`, a real CVE ID, a
mailing-list address, `git push`) inside a skill is a refactor bug, not
a shortcut ([`PRINCIPLES.md` §12](../PRINCIPLES.md#12-the-framework-is-project-agnostic-concrete-names-live-in-adopter-config)).

This is also why the workflows are portable across *runtimes*: a skill
is plain English with a tool contract, which is exactly what the
[`AGENTS.md`](https://agents.md/) standard describes. It is not a
Claude artefact — it is a markdown file any capable agent can follow.

The framework is still finishing the migration of a few early skills
that inlined vendor calls; that cleanup is tracked openly (search the
repo's PRs for `agnostic`) and is a maintenance task, not an
architectural gap.

### Tools are the only place vendor-specific code lives

Everything that knows a specific vendor exists is a **tool** under
[`tools/`](../tools/). Two shapes:

- **Generic MCP tools** — reusable substrate (e.g. the Comdev
  `apache-projects` project-metadata MCP, a PonyMail MCP).
- **Specialised, discoverable tools** — non-MCP CLIs a workflow
  invokes for a unified interface (GitHub access, Jira access, Gmail
  OAuth, the VCS dispatcher).

Crucially, a large fraction of the tool layer is *deliberately split
into a contract plus interchangeable adapters*, so adding a vendor is
"write one adapter," not "patch the framework." Pure interface specs
with pluggable backends already include:

| Contract tool | What plugs in behind it |
|---|---|
| [`tools/cve-tool`](../tools/cve-tool/) | CNA backends — Vulnogram, MITRE form, CVE.org direct, GHSA |
| [`tools/mail-archive`](../tools/mail-archive/) | PonyMail, Hyperkitty, Discourse, Google Groups, GitHub Discussions |
| [`tools/mail-source`](../tools/mail-source/) | mbox, IMAP, Mailman 3 |
| [`tools/forwarder-relay`](../tools/forwarder-relay/) | ASF Security relay, huntr.com, HackerOne triagers |
| [`tools/scan-format`](../tools/scan-format/) | security-scanner report formats (ASVS reference) |
| [`tools/vcs`](../tools/vcs/) | Git (complete), Mercurial, Subversion, … (extension points) |

The distinction Magpie enforces: **vendor-specific *integrations* are
expected and welcome; vendor-specific *workflows* are forbidden.** A
GitHub tool is fine. A skill that only works because it assumes GitHub
is a bug.

### Capabilities are the contract between them

A **capability** is what a tool exposes to a skill — the stable verb a
workflow depends on, independent of which vendor fulfils it. Every
skill declares the capabilities it needs in its frontmatter; every tool
declares the capabilities it provides in its README. The
[capability taxonomy](labels-and-capabilities.md) is the canonical map
of which skill needs what and which tool provides it.

Because the skill ↔ tool coupling is the capability and nothing else,
swapping a backend is a config change, never a code change to the
workflow. An adopter picks, under *Tools enabled*, which tool fulfils a
capability; the same skill code runs on top.

## How each axis is delivered

### 1. LLM backend

Skills are written against a declared **capability floor** (context
window, tool use, vision, sustained reasoning) — never against a
provider's SDK. Any backend that meets the floor is a valid backend,
and the floor itself must be justified and minimised so it cannot
become a vendor lock-in by proxy
([`PRINCIPLES.md` §9](../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable)).

The privacy-aware routing layer is the concrete proof: it ships
end-to-end recipes for six LLM-stack variants and keys approval on the
*endpoint's identity*, not on who hosts it
([`docs/setup/privacy-llm.md`](setup/privacy-llm.md),
[RFC-AI-0003](rfcs/RFC-AI-0003.md)):

1. Claude Code only (default)
2. Local Ollama
3. Local vLLM
4. Apache-hosted endpoint (`*.apache.org`, default-approved)
5. AWS Bedrock (region-bounded, opt-in)
6. Direct Anthropic API (opt-in)

Affordability is part of neutrality, not separate from it: **every
release ships at least one configuration that runs end-to-end on a
single developer machine** (variants 2 and 3), even if individual
skills run at reduced quality there. A maintainer for whom a frontier
subscription is out of reach still gets the full skill catalogue.

### 2. Agentic runtime

Magpie skills are not a Claude Code feature. They are
[`AGENTS.md`](https://agents.md/)-standard markdown, installed under a
single canonical home — `.agents/skills/` — which is the path shared by
Codex, Cursor, Gemini CLI, Copilot and others, with thin relay symlinks
giving every other agent directory (`.claude/skills/`,
`.github/skills/`, …) a pointer to the same entry
([`README.md` § snapshot + override](../README.md)). Users already run
Magpie under several different agentic CLIs. Adding first-class features
for another runtime is an [`area:tools`](labels-and-capabilities.md#1-area--subject)
contribution, not a re-architecture.

### 3. Forge and tracker

Forge and tracker access is mediated entirely by the tool layer:
[`tools/github`](../tools/github/) and [`tools/jira`](../tools/jira/)
are substrate today, and the contract-plus-adapter tools above
(`mail-archive`, `mail-source`, `forwarder-relay`, `cve-tool`,
`scan-format`) already abstract the surfaces where more than one vendor
exists. Skills speak to the capability, so a Git-forge backend
(GitLab, Gitea, Forgejo, Pagure, Bitbucket) plugs in at the tool layer
without the workflows knowing which forge answered.

### 4. Source control (VCS)

The newest axis to be abstracted, and a good worked example of the
mechanism. Earlier, dev-loop skills inlined `git …` calls. Two changes
fixed that:

- A **capability contract** — [`tools/github/source-control.md`](../tools/github/source-control.md)
  defines the abstract operations skills are allowed to assume (branch,
  stage, commit, diff, log, fetch, push, working-tree reset), and every
  git-using skill was pointed at it.
- A **backend-dispatching implementation** — [`tools/vcs`](../tools/vcs/)
  (`magpie-vcs`) runs the *abstract* operation and detects the active
  backend from the working copy.

Today: **Git is complete** (the default binding); Mercurial and
Subversion are real, detected extension points that raise an actionable
error naming their tracking issue until the full binding lands. Adding
a backend means replacing one `_UnimplementedBackend` with a concrete
`VCSBackend` subclass — detection, dispatch, the CLI, and every skill
that calls `magpie-vcs` pick it up automatically. Nothing else changes.

Tracking issues exist for the non-Git systems — Mercurial, Subversion
(ASF-critical: `svn.apache.org` and the release `dist.apache.org` area
are SVN), Jujutsu, Fossil, Perforce, Bitbucket, SourceHut — so the
extension points are public and labelled, not hypothetical.

### 5. Project governance

Vendor neutrality extends to *how a project is run*, not just to its
tooling. Each adopting project picks which modes run and how much
automation fits its culture, whatever its governance — ASF PMC,
foundation-hosted, single-vendor, or an informal maintainer group. The
framework offers a range, never mandates a level, and **non-ASF
adopters are first-class adopters, not a compatibility afterthought**
([`PRINCIPLES.md` §3](../PRINCIPLES.md#3-project-autonomy-is-the-structural-starting-point)).

## What keeps it neutral over time

Neutrality is enforced, not just intended:

- **No vendor-specific workflows, ever.** A skill that only works
  against one vendor is blockable on principle grounds
  ([`PRINCIPLES.md` §9](../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable))
  — any committer may block it and the block holds until it complies.
- **Capability floors are justified and minimised** so the floor does
  not become a back-door lock-in.
- **Eval is a release-blocking discipline**
  ([`PRINCIPLES.md` §8](../PRINCIPLES.md#8-eval-is-a-release-blocking-discipline)).
  Skill behaviour is graded against eval cases, including the
  abstraction layer it targets, so a regression toward a vendor-coupled
  shortcut is caught before release.
- **Ongoing "agnostic" cleanup** of any early skill that inlined a
  vendor call is tracked in the open as normal maintenance.

## The contribution model — neutrality as an invitation

The final piece is structural, and it is deliberately the ASF model:
the framework's job is not to implement *every* backend — it is to
provide a vendor-neutral architecture plus working reference
implementations, and to make filling a gap an easy contribution.

- Each skill lists the capabilities it needs; each capability has a
  documented contract. A contributor who wants their backend supported
  implements **one adapter** against that contract — they never touch
  the workflows.
- The [`write-skill`](../skills/write-skill/SKILL.md) meta-skill and
  the contributor guidelines walk a newcomer through authoring a new
  tool or skill against the contracts.
- The built-in [eval harness](../tools/skill-evals/) lets a contributor
  test their backend the same way the core team tests theirs.
- With any capable agentic runtime, the practical path to a new backend
  is a conversation: point an agent at the tracking issue
  ("implement the SVN source-control backend") and iterate, test, and
  submit. Every tool and skill in Magpie was authored this way.

Where the core team spends its own effort is a Pareto call, surfaced on
the dev list and backed by usage data: jump-start the high-usage
backends, leave the long tail to contributors who need them. That is
not a neutrality gap — it is how an open-source framework scales
coverage without pretending one team can implement an open-ended set.

## Status at a glance

| Axis | Architecture neutral? | Reference backends working today | Extension points |
|---|---|---|---|
| LLM backend | ✅ by construction | Claude Code, Ollama, vLLM, Apache-hosted, Bedrock, direct Anthropic | Any endpoint meeting the capability floor + privacy gate |
| Agentic runtime | ✅ by construction (`AGENTS.md` standard) | Claude Code; community use under Codex, Cursor, Gemini CLI, Copilot, OpenCode, Kiro | `area:tools` features per runtime |
| Forge / tracker | ✅ by construction | GitHub, Jira; mail/CVE/scan/relay via adapter contracts | Git-forge + tracker adapters at the tool layer |
| Source control (VCS) | ✅ by construction | **Git (complete)** | Mercurial, Subversion (detected); Jujutsu, Fossil, Perforce, Bitbucket, SourceHut (tracked) |
| Project governance | ✅ by construction | ASF + non-ASF adopter profiles | Adopter config (modes, thresholds) |

✅ "by construction" means the workflows carry no vendor assumption;
adding a backend is an adapter against a documented contract, not a
change to any skill.

## What "vendor neutral" does and does not claim

To keep the marketing honest and the engineering claim precise:

- **It does claim:** the architecture privileges no vendor; a range of
  backends work end-to-end on every axis today; nothing in the design
  blocks adding more; adding one is a contribution against a contract,
  not a fork.
- **It does not claim:** that every conceivable backend is already
  implemented and hardened. That is impossible for anyone and is not
  what neutrality means.

Where a single axis has exactly one reference backend working today
(e.g. VCS = Git), the precise status is documented above rather than
papered over — the neutrality is in the architecture and the open
extension point, and the roadmap to more backends is public and
labelled.

## See also

- [`PRINCIPLES.md` §9 — Vendor neutrality is non-negotiable](../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable)
- [`PRINCIPLES.md` §3 — Project autonomy is the structural starting point](../PRINCIPLES.md#3-project-autonomy-is-the-structural-starting-point)
- [`MISSION.md` § Affordability and vendor neutrality](../MISSION.md#affordability-and-vendor-neutrality--the-public-good-commitment)
- [`docs/labels-and-capabilities.md`](labels-and-capabilities.md) — the skill / tool / capability taxonomy this page reads as the neutrality mechanism
- [`docs/setup/privacy-llm.md`](setup/privacy-llm.md) — the six LLM-stack variants
- [`docs/rfcs/RFC-AI-0004.md` § Principle 3](rfcs/RFC-AI-0004.md#principle-3--vendor-neutrality) — vendor neutrality as a baseline ethics principle
- [`tools/vcs/`](../tools/vcs/) and [`tools/github/source-control.md`](../tools/github/source-control.md) — the VCS abstraction worked example
- [`docs/mode-economics.md`](mode-economics.md) — what each mode costs to run, per model class
