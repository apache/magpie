<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [How Magpie achieves vendor neutrality](#how-magpie-achieves-vendor-neutrality)
  - [Two questions that get conflated](#two-questions-that-get-conflated)
  - [The six axes of neutrality](#the-six-axes-of-neutrality)
  - [The mechanism: skills, tools, capabilities](#the-mechanism-skills-tools-capabilities)
    - [Skills target the abstraction, never a vendor's client](#skills-target-the-abstraction-never-a-vendors-client)
    - [Tools are the only place vendor-specific code lives](#tools-are-the-only-place-vendor-specific-code-lives)
    - [Capabilities are the contract between them](#capabilities-are-the-contract-between-them)
  - [Tool adapters](#tool-adapters)
  - [Organizations](#organizations)
  - [Authoring your own adapter](#authoring-your-own-adapter)
  - [How each axis is delivered](#how-each-axis-is-delivered)
    - [1. LLM backend](#1-llm-backend)
    - [2. Agentic runtime](#2-agentic-runtime)
    - [3. Forge and tracker](#3-forge-and-tracker)
    - [4. Communication channels](#4-communication-channels)
    - [5. Source control (VCS)](#5-source-control-vcs)
    - [6. Project governance](#6-project-governance)
  - [What keeps it neutral over time](#what-keeps-it-neutral-over-time)
  - [The contribution model — neutrality as an invitation](#the-contribution-model--neutrality-as-an-invitation)
  - [Status at a glance](#status-at-a-glance)
  - [Vendor-neutrality score](#vendor-neutrality-score)
    - [How the score is computed](#how-the-score-is-computed)
    - [What the number means](#what-the-number-means)
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

## The six axes of neutrality

"Vendor" is not one thing. Magpie is neutral across six independent
axes, and a backend choice on one axis never constrains the others:

| Axis | The "vendor" | Neutral by… |
|---|---|---|
| **LLM backend** | Anthropic, OpenAI, Google, Bedrock, local Ollama/vLLM, a future ASF endpoint | Skills written against a model *contract* (capability floor), not a client; a privacy gate that keys on endpoint identity, not on who hosts it |
| **Agentic runtime** | Claude Code, Codex, Cursor, Gemini CLI, Copilot, OpenCode, Kiro, … | Skills are [`AGENTS.md`](https://agents.md/)-standard markdown under a shared `.agents/skills/` home that every runtime reads |
| **Forge / tracker** | GitHub, GitLab, Gitea, Forgejo, Pagure, Bitbucket, Jira, Bugzilla | Per-interface **tools** behind capability contracts; many tools are pure adapter *specs* with pluggable backends |
| **Communication channels** | Mailing lists, GitHub Discussions, Discourse, Zulip, Matrix, IRC | Mail-archive / mail-source adapter contracts; chat and forum bridges as sibling tools |
| **Source control (VCS)** | Git, Mercurial, Subversion, Jujutsu, Fossil, Perforce, … | A single `VCSBackend` contract; skills call the abstract operation, the backend is detected from the working copy |
| **Project governance** | ASF PMC, foundation-hosted, single-vendor, informal maintainer group | Modes and thresholds are adopter config; non-ASF adopters are first-class ([`PRINCIPLES.md` §3](../PRINCIPLES.md#3-project-autonomy-is-the-structural-starting-point)) |

The rest of this page walks the mechanism that makes all six true,
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
| [`tools/mail-source`](../tools/mail-source/) | mbox, IMAP, Gmail API ([`tools/gmail`](../tools/gmail/)), Mailman 3 |
| [`tools/forwarder-relay`](../tools/forwarder-relay/) | ASF Security relay, huntr.com, HackerOne triagers |
| [`tools/scan-format`](../tools/scan-format/) | security-scanner report formats (ASVS reference) |
| [`tools/vcs`](../tools/vcs/) | Git (complete), Mercurial (complete), Subversion, … (extension points) |

The security-team surface follows the same pattern: CNA backends live
behind [`tools/cve-tool`](../tools/cve-tool/) (the ASF Vulnogram adapter
[`tools/cve-tool-vulnogram`](../tools/cve-tool-vulnogram/) is the landed
reference), inbound report relays behind
[`tools/forwarder-relay`](../tools/forwarder-relay/), scanner formats
behind [`tools/scan-format`](../tools/scan-format/), and an OSV.dev
vulnerability cross-reference bridge is the open extension point
([#311](https://github.com/apache/magpie/issues/311)).

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

## Tool adapters

The contract-plus-backend split above has a name. A **tool adapter** is
the unit that fulfils a capability for **one concrete backend**. A
capability *contract* — `tools/<contract>/`, a pure interface spec —
defines the verbs a workflow needs; a **tool adapter** implements that
contract for one vendor:

| Capability contract | Reference adapter(s) | Other backends (extension points) |
|---|---|---|
| [`tools/cve-tool`](../tools/cve-tool/) | [`tools/cve-tool-vulnogram`](../tools/cve-tool-vulnogram/) (ASF) | MITRE form, CVE.org direct, GHSA |
| [`tools/mail-archive`](../tools/mail-archive/) | [`tools/ponymail`](../tools/ponymail/) (ASF) | Hyperkitty, Discourse, Google Groups, GitHub Discussions |
| [`tools/mail-source`](../tools/mail-source/) | mbox, IMAP, Gmail API ([`tools/gmail`](../tools/gmail/)) | Mailman 3 |
| [`tools/forwarder-relay`](../tools/forwarder-relay/) | ASF-security ([`tools/gmail/asf-relay.md`](../tools/gmail/asf-relay.md)) | huntr.com, HackerOne |
| [`tools/scan-format`](../tools/scan-format/) | ASVS | other scanner formats |
| [`tools/vcs`](../tools/vcs/) | Git | Mercurial, Subversion, … |

A project selects an adapter per capability in its config
(`cve_authority.tool: vulnogram`, `archive_system.kind: ponymail`,
`forwarders.enabled: [asf-security]`); **skill bodies never branch on the
choice.** Tool adapters are exactly where vendor specificity is allowed
to live — and the reason adding a vendor is "write one adapter," not a
fork of the workflows.

## Organizations

Most adapter selections are identical for every project under one
governing organization: every ASF project allocates CVEs through the same
Vulnogram, reads the same `lists.apache.org` archive, and gates on PMC
membership. An **organization**
([`organizations/<org>/`](../organizations/)) groups those shared
defaults — the **governance vocabulary** (what the governing body is
called, how contributors are admitted, the lifecycle stages) plus the
**capability→adapter bundle and infrastructure values** — so they live
once instead of in every project.

A project names its organization (`organization: ASF`) and inherits the
rest; resolution is `project.md → organizations/<org>/ → framework
default`, first hit wins. The reference organization is
[`organizations/ASF/`](../organizations/ASF/);
[`organizations/independent/`](../organizations/independent/) is the
no-formal-organization baseline. This is what lets the *same skill* run
unchanged for an ASF project and a non-ASF one — the **organization**,
not the skill, carries the difference. See
[`organizations/README.md`](../organizations/README.md).

## Authoring your own adapter

Neutrality is only real if adopters can extend it. When Magpie ships no
adapter for your backend — a forge, a CNA, a chat system, or a whole
organization profile — you author one, and you have two supported paths:

- **Contribute it to Magpie.** Scaffold the adapter against the
  capability contract (or copy
  [`organizations/_template/`](../organizations/_template/) for an
  organization) and open a PR. Accepted adapters ship under
  Apache-2.0 like the rest of the framework
  ([`PRINCIPLES.md` §17](../PRINCIPLES.md#17-contributions-land-under-apache-license-20)),
  so every other adopter on that backend reuses your work. The
  [`write-skill`](../skills/write-skill/SKILL.md) flow and
  [`CONTRIBUTING.md`](../CONTRIBUTING.md) walk you through the conventions
  (a `**Capability:**` line, a `## Prerequisites` section, an eval); the
  step-by-step how-to is [`docs/adapters/authoring.md`](adapters/authoring.md).
- **Link to an adapter defined elsewhere.** You do not have to upstream
  it. Keep the adapter in your own repository and point your project or
  organization config at it. The framework curates a
  [discovery index](adapters/registry.md) of in-tree and
  community-maintained adapters — but, per
  [`PRINCIPLES.md` §13](../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies),
  the adapter index is **for discovery, never for installation**: nothing is
  auto-fetched, and you wire an external adapter in deliberately, exactly
  as you would a built-in one. (Trusted external *skill* sources are the
  one installable exception §13 carves out — pinned, verified, and
  adopter-vouched; see [`docs/skill-sources/`](skill-sources/README.md).)

Either way the skills stay agnostic: they target the capability, and your
adapter — wherever it lives — supplies the backend. The same three homes
(in-tree, your adopter repo, an external repo) apply to skills and whole
organizations too — see [`docs/extending.md`](extending.md) for the full
extension model (by project, organization, or individual).

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
for another runtime is an [`family:tools`](labels-and-capabilities.md#1-family--subject)
contribution, not a re-architecture — and the extension points are
already open, labelled `good first issue`:
[Codex](https://github.com/apache/magpie/issues/313),
[Gemini CLI](https://github.com/apache/magpie/issues/314),
[local LLM (Ollama / llama.cpp / vLLM)](https://github.com/apache/magpie/issues/315),
[Cursor](https://github.com/apache/magpie/issues/316),
[Aider](https://github.com/apache/magpie/issues/317),
[GitHub Copilot](https://github.com/apache/magpie/issues/318),
[Goose](https://github.com/apache/magpie/issues/319),
[Amazon Q](https://github.com/apache/magpie/issues/320),
[JetBrains Junie](https://github.com/apache/magpie/issues/321),
[OpenHands](https://github.com/apache/magpie/issues/322).
The step-by-step wiring recipe for any new runtime is
[`docs/adapters/add-a-harness.md`](adapters/add-a-harness.md).

### 3. Forge and tracker

Forge and tracker access is mediated entirely by the tool layer:
[`tools/github`](../tools/github/) and [`tools/jira`](../tools/jira/)
are substrate today, and the contract-plus-adapter tools above
(`mail-archive`, `mail-source`, `forwarder-relay`, `cve-tool`,
`scan-format`) already abstract the surfaces where more than one vendor
exists. Skills speak to the capability, so a forge/tracker backend plugs
in at the tool layer without the workflows knowing which forge answered
— the recipe is documented in
[`tools/github/tool.md` § When to replace this tool](../tools/github/tool.md#when-to-replace-this-tool-with-another)
(create a sibling `tools/<name>/` with the same capability files;
declare it under *Tools enabled*; no skill changes).

The forge/tracker extension points are open, labelled `good first
issue`, not hypothetical:
[GitLab](https://github.com/apache/magpie/issues/305),
[Codeberg / Gitea / Forgejo](https://github.com/apache/magpie/issues/310),
[Pagure](https://github.com/apache/magpie/issues/312) (Fedora /
`pagure.io`),
[Bitbucket](https://github.com/apache/magpie/issues/606) (initial
[`tools/bitbucket`](../tools/bitbucket/) `partial-read-only` bridge;
deeper Jira pairing, complete change-request coverage, and write
coverage tracked there), and
[SourceHut](https://github.com/apache/magpie/issues/607) (email-patch
review). Tracker-only surfaces are tracked the same way — e.g.
[Bugzilla](https://github.com/apache/magpie/issues/302) — alongside the
existing [`tools/jira`](../tools/jira/) bridge. The
tracker capability and the source-control capability are *separable*: a
project can pair, say, GitHub issues with a Subversion working copy, or
a Bitbucket forge over Git, because each is a distinct contract.

### 4. Communication channels

Project conversation does not all live on the forge. The intake and
mentoring skills read mailing-list archives, and a project may run its
discussion on a forum or chat system instead of (or alongside) a list.
Both surfaces sit behind adapter contracts:

- [`tools/mail-archive`](../tools/mail-archive/) — public archive reads
  across PonyMail, Hyperkitty, Discourse, Google Groups, GitHub
  Discussions.
- [`tools/mail-source`](../tools/mail-source/) — raw mail ingestion
  across mbox, IMAP, Mailman 3.

The open extension points are labelled `good first issue`:
mail-source backends —
[mbox](https://github.com/apache/magpie/issues/304),
[IMAP](https://github.com/apache/magpie/issues/303),
[Mailman 3 / Hyperkitty](https://github.com/apache/magpie/issues/306);
and chat / forum bridges —
[Discourse](https://github.com/apache/magpie/issues/307),
[Zulip](https://github.com/apache/magpie/issues/308),
[Matrix / Element](https://github.com/apache/magpie/issues/309). A
project on IRC, Slack, or any other channel plugs in the same way — a
sibling tool fulfilling the read capability the mentoring / intake
skills declare, with no skill change.

### 5. Source control (VCS)

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

Today: **Git and Mercurial are complete** (the Git and Mercurial bindings); Subversion
([#602](https://github.com/apache/magpie/issues/602)) is a real, detected
extension point that raises an actionable error naming its tracking
issue until the full binding lands. Adding a backend means replacing one
`_UnimplementedBackend` with a concrete `VCSBackend` subclass —
detection, dispatch, the CLI, and every skill that calls `magpie-vcs`
pick it up automatically. Nothing else changes.

The **ASF SVN** surface goes beyond the generic VCS binding: the
[`tools/asf-svn/`](../tools/asf-svn/) adapter packages the SVN
source-control binding together with ASF-specific capabilities that no
other tool covers — `dist.apache.org` release staging/promotion/pruning
and ASF committer/PMC authorization resolution. This means even a
GitHub-hosted ASF project that uses Git for source control needs
`tools/asf-svn` to steward its release flow through `dist.apache.org`.

Tracking issues exist, labelled `good first issue`, for the remaining
non-Git/non-Hg systems:
[Subversion](https://github.com/apache/magpie/issues/602) (generic VCS
binding; `tools/asf-svn` covers the full ASF SVN surface including
`dist.apache.org` and authorization),
[Jujutsu](https://github.com/apache/magpie/issues/603),
[Fossil](https://github.com/apache/magpie/issues/604), and
[Perforce](https://github.com/apache/magpie/issues/605) — so the
extension points are public and labelled, not hypothetical. (The
Bitbucket and SourceHut forges, which carry their own VCS surfaces, are tracked
under the forge axis above.)

### 6. Project governance

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
| Agentic runtime | ✅ by construction (`AGENTS.md` standard) | Claude Code; community use under Codex, Cursor, Gemini CLI, Copilot, OpenCode, Kiro | Runtime adapters [#313–#322](https://github.com/apache/magpie/issues?q=is%3Aissue+state%3Aopen+adapter+in%3Atitle) |
| Forge / tracker | ✅ by construction | GitHub, Jira, SourceHut; Bitbucket `partial-read-only` foundation excluded from complete-backend counts; CVE/scan/relay via adapter contracts | GitLab [#305](https://github.com/apache/magpie/issues/305), Forgejo/Gitea [#310](https://github.com/apache/magpie/issues/310), Pagure [#312](https://github.com/apache/magpie/issues/312), full Bitbucket tracker/change-request/Jira coverage [#606](https://github.com/apache/magpie/issues/606), Bugzilla [#302](https://github.com/apache/magpie/issues/302) |
| Communication channels | ✅ by construction | PonyMail / mail-archive reads | mbox [#304](https://github.com/apache/magpie/issues/304), IMAP [#303](https://github.com/apache/magpie/issues/303), Mailman 3 [#306](https://github.com/apache/magpie/issues/306); Discourse [#307](https://github.com/apache/magpie/issues/307), Zulip [#308](https://github.com/apache/magpie/issues/308), Matrix [#309](https://github.com/apache/magpie/issues/309) |
| Source control (VCS) | ✅ by construction | **Git (complete)**, **Mercurial (complete)**; ASF SVN surface ([`tools/asf-svn`](../tools/asf-svn/): source control + dist.apache.org + authorization) | Subversion generic VCS binding [\#602](https://github.com/apache/magpie/issues/602) (detected); Jujutsu [\#603](https://github.com/apache/magpie/issues/603), Fossil [\#604](https://github.com/apache/magpie/issues/604), Perforce [\#605](https://github.com/apache/magpie/issues/605) (tracked) |
| Project governance | ✅ by construction | ASF + non-ASF adopter profiles | Adopter config (modes, thresholds) |

✅ "by construction" means the workflows carry no vendor assumption;
adding a backend is an adapter against a documented contract, not a
change to any skill.

## Vendor-neutrality score

The six axes above are the *narrative*. This section is the
*measurement* — a deterministic score computed straight from repository
metadata by
[`tools/vendor-neutrality-score`](../tools/vendor-neutrality-score/), so
the number is reproducible from the source tree and cannot quietly drift
from the code.

### How the score is computed

Neutrality is measured per **capability contract** — the `contract:*`
verbs a skill depends on. Substrate tools (Magpie's own machinery:
sandboxing, analytics, framework-dev) are excluded, because they are not
a vendor choice.

Every contract tool declares three fields in its README: `**Capability:**`
(the contract it fulfils), `**Kind:**` (`interface` for a pure spec,
`implementation` for a concrete backend), and `**Vendor:**` (the backend
identity). The scorer reads them and applies one rule per contract
**class**:

- **vendor-backed** → GREEN once **two or more distinct backend vendors**
  implement it. One backend, however good, is a *default*, not
  neutrality. Interface specs do not count — only shipping backends do.
- **agnostic** → GREEN by construction: a single vendor-neutral spec
  serves every backend, so there is no vendor to be neutral *between*.
- **single-organisation** → GREEN by exemption: the capability is bound
  to one organisation's data model (e.g. ASF governance rosters); there
  is no vendor choice to make.

The overall score is `green contracts / total contracts` — a hard,
falsifiable number. It moves only on shipping backends: add a second
vendor for a contract and it flips to green on the next run; remove a
backend and its contract flips back. The same rule then classifies every
**skill**: *capability-pure*
if it names no backend, *portable* if every backend it invokes has an
alternative, and *vendor-coupled* only if it reaches for the sole
implementation of a capability.

The same tool also measures the **LLM-integration axis** on two fronts.
The *agent harness* (which runtime drives the skills): each substrate
tool — Magpie's own machinery — declares `**Harness:**`, the harness it
integrates with or `agnostic`, and a tool is harness-neutral when it is
agnostic or supports two or more harnesses. The *model endpoint* (which
LLM may receive data): the default-approved classes come straight from
the [`privacy-llm` registry](../tools/privacy-llm/models.md), which keys
approval on endpoint identity rather than vendor. Both appear in the
generated block below.

<!-- BEGIN vendor-neutrality-score — generated by `uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown`; do not edit by hand -->

**Overall vendor-neutrality score: 10/10 capability contracts (100%).** Generated by [`tools/vendor-neutrality-score`](../tools/vendor-neutrality-score/); re-run it to refresh this section.

| Capability contract | Neutral? | Class | Backends today | Basis |
|---|---|---|---|---|
| `contract:tracker` | ✅ | vendor-backed | Atlassian, Fossil, GitHub, SourceHut | 4 backend vendors: Atlassian, Fossil, GitHub, SourceHut |
| `contract:source-control` | ✅ | vendor-backed | Fossil, Git, GitHub, SourceHut, Subversion | 5 backend vendors: Fossil, Git, GitHub, SourceHut, Subversion |
| `contract:change-request` | ✅ | vendor-backed | Atlassian, GitHub, email | 3 backend vendors: Atlassian, GitHub, email |
| `contract:mail-archive` | ✅ | vendor-backed | ASF, Google, SourceHut | 3 backend vendors: ASF, Google, SourceHut |
| `contract:mail-source` | ✅ | vendor-backed | ASF, Google, Maildir | 3 backend vendors: ASF, Google, Maildir |
| `contract:mail-create` | ✅ | vendor-backed | Google, Maildir | 2 backend vendors: Google, Maildir |
| `contract:cve-authority` | ✅ | vendor-backed | CVE.org, Vulnogram | 2 backend vendors: CVE.org, Vulnogram |
| `contract:report-relay` | ✅ | agnostic | — | vendor-neutral by construction — one spec serves every backend |
| `contract:scan-format` | ✅ | agnostic | — | vendor-neutral by construction — one spec serves every backend |
| `contract:project-metadata` | ✅ | single-org | ASF | single-organisation capability (ASF); no vendor choice to make |

**Per-skill assessment: 69/69 skills carry no vendor lock-in.** A skill is *capability-pure* when it names no backend at all, *portable* when every backend it names has an alternative (its contract is green), and *vendor-coupled* only when it reaches for a backend that is the sole implementation of a capability.

| Skill neutrality | Count |
|---|---|
| capability-pure (names no backend) | 10 |
| portable (named backends are swappable) | 59 |
| vendor-coupled (sole-backend dependency) | 0 |

Organization scope (declared, orthogonal to vendor): ASF = 14, agnostic = 55.

**LLM / agent-integration neutrality**

**Agent harness: 22/22 substrate tools run under any harness unchanged (100%).** Substrate tools are Magpie's own machinery; each declares the agent harness it integrates with (`**Harness:**`), or `agnostic`. A tool is neutral when it is harness-agnostic or supports two or more harnesses; *coupled* when it targets a single harness.

| Substrate tool | Substrate | Harness support | Verdict |
|---|---|---|---|
| `agent-guard` | action-guard | Claude Code, OpenCode | ✅ portable |
| `agent-isolation` | sandbox | Claude Code, OpenCode | ✅ portable |
| `dashboard-generator` | analytics | any | ✅ agnostic |
| `dev` | framework-dev | any | ✅ agnostic |
| `egress-gateway` | sandbox | any | ✅ agnostic |
| `permission-audit` | sandbox | Claude Code, OpenCode | ✅ portable |
| `pilot-report-validator` | framework-dev | any | ✅ agnostic |
| `pr-management-stats` | analytics | any | ✅ agnostic |
| `preflight-audit` | analytics | any | ✅ agnostic |
| `privacy-llm` | privacy | any | ✅ agnostic |
| `probe-templates` | sandbox | any | ✅ agnostic |
| `sandbox-lint` | sandbox | Claude Code, OpenCode | ✅ portable |
| `security-tracker-stats-dashboard` | analytics | any | ✅ agnostic |
| `skill-and-tool-validator` | framework-dev | any | ✅ agnostic |
| `skill-evals` | framework-dev | any | ✅ agnostic |
| `skill-reconciler-diff` | framework-dev | any | ✅ agnostic |
| `spec-inventory` | framework-dev, analytics | any | ✅ agnostic |
| `spec-loop` | framework-dev | Claude Code, Codex, Cursor, Gemini CLI, OpenCode | ✅ portable |
| `spec-status-index` | framework-dev, analytics | any | ✅ agnostic |
| `spec-validator` | framework-dev | any | ✅ agnostic |
| `symlink-lint` | framework-dev | any | ✅ agnostic |
| `vendor-neutrality-score` | framework-dev, analytics | any | ✅ agnostic |

Harness → substrate tools it supports:

- **Claude Code** (5): `agent-guard`, `agent-isolation`, `permission-audit`, `sandbox-lint`, `spec-loop`
- **Codex** (1): `spec-loop`
- **Cursor** (1): `spec-loop`
- **Gemini CLI** (1): `spec-loop`
- **OpenCode** (5): `agent-guard`, `agent-isolation`, `permission-audit`, `sandbox-lint`, `spec-loop`
- **any harness** (17): `dashboard-generator`, `dev`, `egress-gateway`, `pilot-report-validator`, `pr-management-stats`, `preflight-audit`, `privacy-llm`, `probe-templates`, `security-tracker-stats-dashboard`, `skill-and-tool-validator`, `skill-evals`, `skill-reconciler-diff`, `spec-inventory`, `spec-status-index`, `spec-validator`, `symlink-lint`, `vendor-neutrality-score`

**Model endpoint: neutral by construction — 4 default-approved endpoint classes across independent trust domains, plus adopter opt-in.** From the [`privacy-llm` registry](../tools/privacy-llm/models.md): the framework keys approval on *endpoint identity*, not on who hosts the model, so no single LLM vendor is privileged.

| Default-approved endpoint class | Examples |
|---|---|
| Claude Code itself | The agent invoking the skill |
| *.apache.org-hosted endpoints | A future ASF-hosted inference endpoint at e.g. `inference.apache.org`; an in-tracker endpoint at `<project>.apache.org/llm/` |
| Local-only inference | Ollama serving a local model, vLLM on the user's workstation, llama.cpp embedded in a CLI helper |
| Air-gapped on-prem | A PMC-hosted inference appliance on a private VLAN |

Every other endpoint is **opt-in** — the adopting project's security team declares it in `<project-config>/privacy-llm.md` (endpoint URL, data-residency contract, approver), so the choice is local and audited.

<!-- END vendor-neutrality-score -->

### What the number means

100% reads as: **every one of the ten capabilities already works across
more than one vendor** — no axis of the architecture privileges a single
vendor, and none is a design that assumes one. The last red cell, outbound
mail composition (`mail-create`), closed when the local **Maildir** backend
([`tools/maildir/`](../tools/maildir/)) landed as the second, non-Google
implementation: an offline, credential-free writer that files editable
drafts into a local Maildir for any mail client to send. A project that
cannot or will not depend on Gmail can now drive every draft-producing
skill. The number is not a finish line — new vendors keep arriving, and each
must clear the same two-backend bar — but it does mean there is no
vendor-locked capability left in the framework today.

The `change-request` gate — the pull-request review/merge contract that
every skill driving `gh pr` resolves through — went green in
[#669](https://github.com/apache/magpie/issues/669). `contract:tracker`
is green because Jira also handles issues, but Jira has no pull-request
model; so `change-request` is a *separate* contract, and it now ships
three backends across three vendors: GitHub pull requests
([`tools/github/`](../tools/github/)), patches on JIRA issues landed via
SVN ([`tools/jira-patch/`](../tools/jira-patch/)), and `[PATCH]` threads
on `dev@` landed via SVN ([`tools/mail-patch/`](../tools/mail-patch/)).
The two SVN-first backends delegate their terminal `land` to
`contract:source-control` and own only the proposal lifecycle. Every
skill that drives `gh pr` is now *portable* without a line of skill code
changing — the seam is the contract
([`tools/change-request/`](../tools/change-request/)), not the workflow.

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
