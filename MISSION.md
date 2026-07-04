<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie](#apache-magpie)
  - [Mission](#mission)
  - [Abstract](#abstract)
  - [Proposal](#proposal)
  - [Name](#name)
  - [Rationale](#rationale)
  - [Scope boundaries — what Magpie is, and the non-goals](#scope-boundaries--what-magpie-is-and-the-non-goals)
  - [Initial Goals](#initial-goals)
  - [Technical scope](#technical-scope)
  - [Maintainer education — building agentic projects is a different craft](#maintainer-education--building-agentic-projects-is-a-different-craft)
  - [Privacy, security, and supply-chain integrity — the top-most priority](#privacy-security-and-supply-chain-integrity--the-top-most-priority)
  - [Affordability and vendor neutrality — the public-good commitment](#affordability-and-vendor-neutrality--the-public-good-commitment)
  - [Initial PMC composition (target)](#initial-pmc-composition-target)
  - [Required resources](#required-resources)
  - [Source and IP](#source-and-ip)
  - [External dependencies](#external-dependencies)
  - [Cryptography](#cryptography)
  - [Particular care](#particular-care)
  - [Ask of the Board](#ask-of-the-board)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Apache Magpie

> [!IMPORTANT]
> **Motto:** *"Give maintainers time back, so they can do what matters."*

## Mission

Apache Magpie is responsible for the creation and maintenance of software
related to agent-assisted repository maintainership and development,
including issue and pull-request triage, contributor mentoring,
agent-drafted remediation, developer-side development-cycle skills, and
narrowly-scoped fix-and-merge automation

## Abstract

Apache Magpie is platform infrastructure for **agent-assisted repository maintainership and development** — across the ASF and equally for any open-source project that wants in. Four streams of day-to-day work:

- **Security-issue handling** end-to-end — inbound triage, deduplication, agent-drafted reporter replies under human review, CVE allocation hand-off, audit-logged status tracking through publication.
- **Issue and PR triage and management** — including audit-tool findings (from a scanner such as Apache Verum, Apache Caer, or any equivalent) ingested as actionable issues. *(Apache Verum and Apache Caer are illustrative placeholder names, not real or planned ASF projects.)*
- **Conversational contributor mentoring** — meeting new contributors where they are.
- **Development-cycle skills for committers and contributors, mentorship built in** — multi-agent development workflows, self-review and pre-flight patterns, scoped agent-drafted patches under the developer's own driver's seat. Mentorship is intrinsic, not a separate mode: the agent handles implementation-detail review (formatting, conventions, lint-grade nits) so the human conversation between contributor and maintainer — and between peer maintainers — stays on design, reasoning, and the path that turns contributors into committers and committers into PMC members. Machine-to-machine traffic absorbs the mechanical work; the human relationship is what the platform protects.

One conviction underneath: each project picks how much automation actually fits. The platform makes a range of automation levels possible without picking one for you, and "project" means both an ASF PMC and any non-ASF community — neither is a second-class citizen.

## Proposal

The Apache Software Foundation establishes the Apache Magpie Project as a Top-Level Project by Board resolution, scope: agent-assisted repository **maintainership and development** infrastructure under the Apache License, Version 2.0.

## Name

The project's name is **Apache Magpie**. It was selected by the founding PMC during the naming bikeshed (8–12 May 2026) and confirmed available via **PODLINGSEARCH**.

For the historical record, three alternates were carried as priority-ordered backups during the bikeshed in case the primary failed the name search — **Apache Beacon**, **Apache Guild**, and **Apache Lichen**. Magpie cleared PODLINGSEARCH, so it is the final name and the alternates are no longer under consideration. The Board resolution carries the Apache Magpie name.

## Rationale

Open-source projects share the same shape of problem: contributors keep arriving, reviewers don't scale to match, and the highest-stakes work — security-issue handling — is the *most* manual, the *most* reviewer-intensive, and the *most* embarrassing to get wrong. The two complaints heard most loudly — **onboarding latency** and **review-cycle latency** — are the priorities the ASF Responsible AI Initiative names. Magpie is the operational layer for those goals: not a position paper, working tools that PMCs and non-ASF projects can adopt today.

Four design choices set the project apart from "just bolt a code-review bot on it":

**Project autonomy is the structural starting point — and "project" includes non-ASF.** Five modes — **Agentic Triage**, **Agentic Mentoring**, **Agentic Drafting** (agent-authored fix with human review), **Agentic Pairing** (developer-side development-cycle skills with mentorship intrinsic), and **Agentic Autonomous** (narrowly-scoped fix-and-merge) — ship as separate, independently-toggleable skills. Each project picks the modes that match its culture and risk tolerance. ASF integrations (private lists, Vulnogram CVE flows, PMC roles, ASF release process) live behind clean configuration boundaries; non-ASF adopters swap them for whatever fits — a private GitHub repo, GitHub Security Advisories, a maintainer roster, their own release process. The platform is project-governance-agnostic by design — no foundation-mandated automation level survives contact with project culture, and we're not trying to make it.

**Security-issue handling is a load-bearing use case, not a footnote on triage.** The work that became Magpie started as a framework for handling ASF security reports — high-stakes, high-procedure, every-step-needs-an-audit-trail flows that turn out to be exactly what agent-assisted-with-human-gates is good at. Every mode has to clear the security-flow bar (private content stays private, every outbound draft has a human signature, every state change is logged) before it ships. Projects without a security process get a path to adopt one; projects that have one get tooling that respects the ceremony.

**Agentic Mentoring is a first-class mode, not a side-effect of triage.** The lever the ASF — and the wider open-source world — actually needs and the one off-the-shelf agent tooling skips. Meets new contributors where they are, explains conventions, points at the relevant prior PR, asks the clarifying question *before* a reviewer burns time on it. This is where the Responsible AI Initiative's contributor-empowerment goal gets operationalised: the mode that produces the outcomes RAI is trying to measure, in the projects that volunteer for the eval.

**Development-cycle skills sit alongside maintainership skills, with mentorship intrinsic to them.** Maintainers also write code; contributors live the development side of every project. The same agentic primitives that triage an inbound report or mentor a new contributor compose into a committer's or contributor's own development cycle: multi-agent review pipelines that catch issues before submission, self-review patterns that pre-flight a PR against project conventions, scoped agent-drafted patches a contributor reviews against their own taste before opening. The shape of these skills is deliberate: **agents handle implementation-detail review** (formatting, conventions, lint-grade comments) **so the human conversation stays on the things that build relationships** — design choices, ideas, the trade-offs the project cares about, the *why* behind a review comment. Machine-to-machine traffic is fine where the work is mechanical. **What the platform actively protects is the path that turns contributors into committers and committers into PMC members** — the standard ASF progression — **and the parallel path that lets maintainers learn from contributors and from peer maintainers.** This is the same skill shape as an Agentic Triage skill, with the developer themselves as the human in the loop, and it lands on the platform's existing security and privacy posture without modification.

## Scope boundaries — what Magpie is, and the non-goals

Magpie's scope is broad on *capability* and deliberately narrow on *authority*. A platform this wide invites a fair question: does it overlap ComDev, the Incubator, the Security team, Tooling, or the Responsible AI Initiative, and where does the line actually sit? It is easy to misread Magpie as another foundation-level body in that mould. It is not, and the line is clean:

**Magpie serves any project, ASF or not — that is the distinguishing line.** Cross-foundation reach is a founding principle, not a later expansion. ComDev, the Incubator, the Security team, Tooling, and the Responsible AI Initiative are ASF-internal bodies that serve ASF projects. Magpie is not one of them and does not aspire to be — a community that has never heard of the ASF is a first-class adopter.

**Magpie is an independent PMC like any other — all it does is release software.** It does not set Foundation-wide policy. It does not decide what ASF projects should or must do — on automation level or anything else. Telling projects how to govern themselves is an explicit **non-goal**. The platform makes a range of automation levels possible without picking one; each project opts in, mode by mode.

**Magpie works with the ASF bodies it overlaps — it does not absorb them.** Where ComDev, the Incubator, Security, Infrastructure, or Tooling have relevant skills, Magpie either helps implement them or *proxies* them. Those teams choose whether to contribute a skill into Magpie or keep it in their own repository and let Magpie install it by reference — Magpie does not reach into another team's domain on its own initiative. Other foundations (e.g. Eclipse, the Python Software Foundation) can do the same: contribute, proxy, layer their own integration on top, or simply take inspiration.

**The data layer is shared; the skills on top are free to diverge.** This is the boundary rule that makes the above work in practice. Shared MCPs and data tools — PonyMail, Apache Projects, Trademark, and the like — stay centralized, typically in ComDev or the Incubator, because divergence there means *wrong data*, with no governance opinion to fight over. The skills built on top are free to diverge by scope, tier, and teaching voice. DRY pays on the data tools; it does not pay on the skills. Skills carry a `source` tag (e.g. `asf-comdev`, `asf-incubator`) so Magpie can proxy and install the right set per project, and so the split is a registry query rather than tribal knowledge.

**Duplication is embraced where it buys decoupling.** Working across distributed, independent PMCs — and across foundations — makes some duplication inevitable, and agentic tooling makes it cheap: an agent can reconcile two near-identical skills on demand, so the price of keeping them separate is low and the coupling avoided is real. Magpie does not chase DRY across organisational boundaries. The one place divergence is *not* tolerated is the **safety baseline** — the untrusted-content-is-never-instructions rule, identity-resolution caveats, and confidentiality posture — which every skill stays eventually-consistent on, wherever it lives.

**On mentoring specifically:** Magpie ships mentoring *skills* — reusable, machine-assisted tooling any project can adopt — it does not own the community-development mentoring function, which remains ComDev's (and, for podlings, the Incubator's) for ASF projects. The Agentic Mentoring mode is a tool in the box, not a claim on the role. The same framing applies to every mode: Magpie supplies the agentic capability; the project, and where relevant the responsible ASF body, keeps the policy.

## Initial Goals

- Stand up `github.com/apache/magpie` with project skeleton, CI, and contributor docs.
- Provision standard ASF infrastructure: `private@`, `dev@`, `commits@`; GitHub Issues; site at `magpie.apache.org`.
- Get **Agentic Triage**, **Agentic Mentoring**, and **Agentic Drafting** running against **3–4 friendly pilots within 3 months** — at least one ASF PMC running the full security-issue flow (Airflow, given the project's lineage), one ASF PMC running just Agentic Triage + Agentic Mentoring (Arrow or ATR), and **at least one non-ASF project from day one** (Python core has folks interested). Non-ASF in the first cohort, not later — the project-governance-agnosticism claim is only worth what it can prove.
- Cut a first Apache release through the standard process within 3 months of resolution adoption, with artefacts usable directly by non-ASF adopters (no ASF-only assumption baked into the install path).
- Wire **Agentic Triage**, **Agentic Mentoring**, and **Agentic Drafting** up to audit-tool findings (from a scanner such as Apache Verum or Apache Caer) and to at least one non-ASF audit-tool equivalent (a CodeQL output stream is the likely first non-ASF case).
- **Ship at least one Agentic Pairing skill family** in v1, with mentorship hooks intrinsic — multi-agent review or pre-flight self-review — demonstrated against a friendly-pilot project's contributor development cycle, so the maintainership-and-development scope claim and the human-relationship-preservation claim both have working code to point at.
- Settle on a contributor-sentiment evaluation methodology (an eval framework such as Apache Plumb, likewise an illustrative placeholder name, not a real or planned ASF project). Eval covers both ASF and non-ASF cohorts so the data isn't an internal-ASF artefact.
- **Ship the privacy and security posture** as a release-blocking part of v1 — sandbox setup, clean-env wrapper, privacy-LLM gate, PII redactor, signed releases, pinned-tools manifest. Not a follow-up.
- **Ship the maintainer-education stream** alongside v1 — pattern catalogue, "your first skill" path, first scheduled workshops. The platform is only as adoptable as the docs that go with it.
- **Validate vendor-neutrality** in v1 pilots: at least one project running Agentic Triage, Agentic Mentoring, and Agentic Drafting against a frontier-model backend, one against fully-local inference (Ollama / vLLM), one against an Apache-hosted or Apache-aligned endpoint as it becomes available.

## Technical scope

A platform substrate — issue and PR ingestion, GitHub API write-back, conversation threading, audit logging, integration with adjacent systems (Gmail, PonyMail, Vulnogram, generic CVE submission, an extensible adapter layer so non-ASF adopters plug in their own equivalents) — with five modes built on top.

[`docs/modes.md`](docs/modes.md) is the honest snapshot mapping each mode below to the skills currently shipped, with a `stable / experimental / proposed / off` status legend.

**Agentic Triage** — for issues, security reports, and PRs. *On the security side:* spots inbound reports, classifies against prior triaged cases, surfaces likely duplicates, identifies anything that should not have been filed publicly, proposes initial routing to the security team. *On the regular side:* suggests labels, spots duplicates, links related discussions, proposes routing. Every output is a suggestion the human signs off on; nothing lands without review. Lowest risk surface.

**Agentic Mentoring** — conversational. Joins issue and PR threads in a deliberately teaching register: clarifying questions, pointers to project conventions and docs, an explanation of *why* a change is being asked for, paired examples from similar prior PRs, clean hand-off to a human reviewer when the question exceeds what an agent should answer. The differentiator and the highest-value project-side mode — where the Responsible AI Initiative's empowerment outcome lives.

**Agentic Drafting** — agent-authored fixes with human review. The agent drafts a fix for a well-scoped problem (a tracked issue, a triaged security report with team consensus on scope, a finding from an audit tool such as Apache Verum, Apache Caer, or any equivalent, a failing test with an obvious cause, a documentation hole) and opens a PR. Every PR is reviewed and merged by a human committer; the agent never merges its own work. For security PRs the public surface strips CVE / private context per the project's disclosure policy, so the public surface stays clean until the embargo lifts.

**Agentic Pairing** — developer-side development-cycle skills, mentorship intrinsic. Beyond the project-side modes above — which describe the project's agent presence on its own infrastructure — the platform also ships skills that maintainers and contributors run in their *own* development cycle: multi-agent review pipelines, self-review and pre-flight patterns, scoped fix drafting under the developer's driver's seat. Agentic Pairing skills don't make state changes on behalf of the project; they're the developer's individual agentic toolkit, sharing the same skill format and security posture as the project-side modes. **Mentorship is built into them by design:** the agent handles implementation-detail review (formatting, lint-grade nits, convention checks) so the human conversation between contributor and maintainer — and between peer maintainers — stays on design, reasoning, and the trade-offs the project cares about. The aim is that machine-to-machine traffic absorbs mechanical work while the **human relationship** — the path that turns contributors into committers and committers into PMC members, and the parallel path that lets maintainers learn from contributors and peers — is what the platform actively protects. **Agentic Pairing ships before Agentic Autonomous in the project's automation roadmap:** full auto-merge of maintainer-driven changes follows only after Agentic Pairing has established that human reasoning and relationships, not implementation chatter, are the load-bearing parts of the workflow.

**Agentic Autonomous** — narrowly-scoped fix-and-merge. Agentic Autonomous restricted to objectively boring change classes — lint fixes, dependency bumps inside an allow-list, license-header insertion, formatting, broken-link repair. Per-project AND per-class opt-in; every auto-merged change is reversibly logged. **Not turned on** until Agentic Triage, Agentic Mentoring, Agentic Drafting, **and Agentic Pairing** have been running for two quarters and contributor-sentiment data says the project is healthier, not just faster. Security-class changes are explicitly *out* of Agentic Autonomous — no auto-merge ever touches anything embargoed or CVE-tagged.

The substrate also handles per-project config (which modes are on, eligible change classes, who reviews, how disputes route, where security reports come from, where audit findings come from, what the release process expects), full audit logging and rollback for every agent-authored change — security and non-security alike — and an integration hook for an eval framework such as Apache Plumb (or any eval tool that fills that role) so the contributor-empowerment claim has measurable data behind it.

## Maintainer education — building agentic projects is a different craft

Most maintainers have never built an agentic application before. The mental model is genuinely different from what twenty years of writing services and CLIs trained us for: behaviour is **probabilistic, not deterministic**; prompts and skill files **are code** in every meaningful sense; **evaluating output is harder than testing a function**; the unit of authorship shifts from "a function in a file" to "a skill the agent invokes". The instincts that keep regular code reliable — strict types, tight tests, short functions, exhaustive branching — don't go away, but they're not enough on their own.

Magpie runs a maintainer-facing education stream as a **first-class part of the project**, not an afterthought wiki page:

- **Pattern catalogue** — copy-pasteable skill / prompt / tool-use patterns with notes on what worked, what didn't, and why. The same way the early days of Python testing or distributed systems were taught: war stories with code attached.
- **Eval-driven development examples** — how to think about correctness when "correct" is a distribution. Worked examples from real Magpie modes; integration with an eval framework such as Apache Plumb so the eval methodology is shared, not reinvented per-project.
- **Workshops and pairing sessions** — scheduled office-hour sessions where maintainers from any project (ASF or not) can show up with their use case and pair with the Magpie team. Recordings published.
- **A "your first skill" path** — equivalent of "your first PR" docs, but for landing a working skill in your project. Aim: any motivated maintainer can take a working agentic skill from zero to merged in a weekend, without first having to learn LLM internals.

Every Magpie release ships with the docs and patterns the maintainers using it actually need. The steepness of this learning curve is currently one of the larger barriers to broader agentic adoption in open source; lowering it is part of the platform's job.

## Privacy, security, and supply-chain integrity — the top-most priority

Most maintainers asked about agentic tooling lead with the same fears, in roughly this order:

- *Will my credentials end up in some model provider's training data?*
- *Will pre-disclosure CVE content leak out of the agent's context?*
- *What does the agent's dependency tree look like, and who controls it?*
- *Can a malicious issue or PR comment talk the agent into running something I didn't authorise?*
- *Can the agent quietly exfiltrate code or contributor data?*
- *If something goes wrong, can I see what happened and undo it?*

Not theoretical — the actual reason a lot of capable maintainers are *not* using agentic tools today, even when those tools would help. Magpie's response, baked into the project's foundation rather than retrofitted later:

- **Clean-environment wrapper** around every agent invocation — no envvars from the surrounding shell unless explicitly allow-listed; no silent leakage of API keys, tokens, paths.
- **Layered sandbox by default** — filesystem, network, and tool-permission rules enforced at the harness layer; sandbox bypasses surface a loud, visible warning before they run, never silently.
- **Privacy-aware LLM routing** — private content (security reports, embargoed CVE detail, PMC-private mail) flows only to LLMs the project's PMC has explicitly approved, with a recorded data-residency contract. The framework refuses to route private bytes through a non-approved model. *Already implemented in the upstreamed framework that became Magpie.*
- **PII redaction at the boundary** — reporter identity flows where operationally needed (CVE credit, reply threads); third-party PII gets redacted to stable identifiers before any LLM context.
- **Pinned, reviewed, signed dependencies** — every system tool (`bubblewrap`, `socat`, agent CLI) pinned to a version aged through a documented cooldown window. Bumps are PRs, not silent updates. Supply-chain risk treated like code change.
- **Audit log every agent-authored action** — comments, labels, drafts, issues, PRs. Reversible where possible; flagged where not.
- **Hard rule: external content is data, never instructions** — reporter mail, PR comments, GHSA forwards, attachments. Documented at the framework level, enforced at the skill level.

The choice to land Magpie at the ASF — rather than as an independent project or vendor offering — is load-bearing for this. **The ASF is a trust layer.** Maintainers who would (reasonably) hesitate to install a vendor's agent framework on their dev machine, or grant it access to their security mailing list, will more readily install one that comes through the same release process as the rest of their toolchain, signed by the same KEYS, governed by a PMC, held to the same software-grant and release-policy bar the foundation has been holding software to for a quarter-century. That trust extends to non-ASF adopters too: a community that trusts the ASF's release process inherits Magpie's privacy and supply-chain posture without having to audit it from scratch.

This is the **first** priority — not the first among many. If a feature has to slow to keep this story honest, it slows.

## Affordability and vendor neutrality — the public-good commitment

Current state of agentic tooling for open source: maintainers doing the most agent-assisted work tend to have **expensive personal subscriptions** to one or more frontier-model providers, or **complimentary access** a vendor handed them. Both work, neither is sustainable, neither is fair. A maintainer in a country where a $200/month subscription is six weeks of pay does not get to participate. A project whose lead maintainer happens to have a vendor relationship gets capabilities its peer projects don't.

The gap Magpie exists to close, with an uncompromising long-term commitment:

- **Vendor neutrality is non-negotiable, top to bottom.** Every mode runs against the project's chosen LLM, not a hard-coded one. The platform's contract with the model is well-defined enough that Claude, OpenAI, Anthropic-via-Bedrock, Google, locally-hosted Llama / Qwen / DeepSeek (Ollama, vLLM), and a future ASF-hosted endpoint are all valid backends with the same skill code on top. Skills are written against the contract, not the vendor.
- **Local and self-hosted paths are first-class, not fallback.** A maintainer running Ollama gets the same skill catalogue as one running a frontier-model subscription. Local-only inference is also the simplest answer to most of the privacy concerns above — it never leaves the machine.
- **An ASF-hosted inference endpoint is on the long-term roadmap** — `inference.apache.org` (name TBD): a community-affordable, foundation-governed, audit-logged inference layer any open-source maintainer (ASF or not) can use to participate in agentic development without paying a vendor or accepting a vendor's gift. The long-term shape of "release software for the public good" in the agentic era.
- **Economics get documented honestly.** Magpie's docs include a "what does each mode actually cost to run" page — token counts per typical invocation, per mode, per model class — so a maintainer evaluating adoption can make an informed call instead of guessing. The same data informs the case for the ASF-hosted endpoint when the community is ready to ask the question.

The ASF mission line — *"to provide software for the public good"* — has always meant the *running* software, not just the source code. For agentic tooling, the running software increasingly *is* the model, and the public-good commitment has to extend that far. **If Magpie ends up being a thing only well-resourced maintainers can run, it has failed its core mission, regardless of how good the code is.**

## Initial PMC composition (target)

PMC composition matters more than most because the project's social stakes are higher than its technical stakes. The PMC will be filled from existing ASF members, and potentially Apache Airflow PMC members where implementation of Agentic Triage, Agentic Mentoring, and Agentic Drafting is already live and used — coordinated with Membership before the resolution is adopted.

- **Size:** 7 or more members.
- **Diversity:** at least three distinct organisational affiliations; no single employer holding a majority.
- **Coverage:** PMC members drawn from a diverse set of ASF projects rather than concentrated in one or two, with preference for PMCs whose own work centres on developer experience (build tools, language ecosystems, community development, contributor-facing workflows); a majority of members are actively working on developer experience in their home project; ASF Privacy and ASF Legal engaged from project start, given the contributor-data surface.
- **Chair:** Jarek Potiuk, subject to PMC vote per Bylaws.

ASF members for the roster:

- Jarek Potiuk (potiuk) — Airflow PMC
- Piotr Karwasz (pkarwasz) — Log4J PMC
- Elad Kalif (eladkal) — Airflow PMC
- Matthew Topol (zeroshade) — Arrow PMC, Iceberg PMC
- Pavan Kumar Gopidesu (gopidesu) — Airflow PMC
- Amogh Desai (amoghdesai) — Airflow PMC
- Andrew Musselman (akm) — Mahout PMC
- Justin Mclean (jmclean) — Incubator PMC, Training PMC
- Jean-Baptiste Onofré (jbonofre) — Incubator PMC, Polaris PMC, …
- Paul King (paulk) — Groovy PMC, Grails PMC, Incubator PMC
- Evan Rusackas (rusackas) — Superset PMC
- Russell Spitzer (russellspitzer) — Incubator PMC, Polaris PMC, Iceberg PMC
- Ismael Mejia (iemejia) — Beam PMC, Incubator PMC
- Zili Chen / tison (tison) — Pulsar PMC, Curator PMC, ZooKeeper PMC, …
- James Fredley (jamesfredley) — Grails PMC
- Calvin Kirs (kirs) — Doris PMC, Geode PMC
- Rich Bowen (rbowen) — Incubator PMC, ComDev PMC, …
- Mike Drob (mdrob) — Accumulo PMC, Curator PMC, HBase PMC, Lucene PMC, Solr PMC
- Craig L Russell (clr) — Security Team, Incubator PMC, ComDev PMC, …
- Coty Sutherland (csutherl) — Tomcat PMC
- Rémy Maucherat (remm) — Tomcat PMC
- Richard Zowalla (rzo1) — Logging Services PMC, Hop PMC

The named PMC roster will accompany the resolution at the time of vote.

There are collaborators who are **not** ASF members yet *(wink)* but
who have already contributed and will be involved as collaborators
on the project from day one:

- André Ahlert Junior — [@andreahlert](https://github.com/andreahlert)
- Bartosz Sławecki — [@johnslavik](https://github.com/johnslavik)
- Yeonguk Choo — [@choo121600](https://github.com/choo121600)
- Shahar Epstein — [@shahar1](https://github.com/shahar1)
- Vincent Beck — [@vincbeck](https://github.com/vincbeck)
- Buğra Öztürk — [@bugraoz93](https://github.com/bugraoz93)

## Required resources

- **Mailing lists:** `private@magpie.apache.org`, `dev@magpie.apache.org`, `commits@magpie.apache.org`.
- **Source control:** `github.com/apache/magpie`.
- **Issue tracking:** GitHub Issues.
- **Website:** `magpie.apache.org`.
- **Release infrastructure:** `dist.apache.org` per standard ASF process.

## Source and IP

Green-field project, with substantial project-agnostic code being moved over from existing ASF projects — Apache Airflow (where the security-issue handling, PR triage, mentoring, and drafting framework that became Magpie was first developed and proven; already structured under Apache-2.0 for reuse inside and outside the ASF), Apache Groovy, and other ASF projects whose maintainers have been early adopters. All transferred code is already Apache-2.0 licensed and ASF-owned; the moves go through the standard ASF IP Clearance process, with no Software Grant Agreements needed (those apply only to code originating outside the ASF).

## External dependencies

A current SKILL-based implementation already covers PR triaging, security-issue management, and the maintainer review process — language-independent, since SKILLs are English. Standard Python ecosystem dependencies for the deterministic-output scripts. No AI SDK integration needed; the solution is pure agentic SKILL implementation understood by most AI CLIs. Apache-license compatibility verified.

## Cryptography

Standard TLS for HTTPS API calls. No novel cryptography. ECCN classification reviewed as not applicable.

## Particular care

The contributor experience is the most sensitive surface in any open-source project. Getting the tone wrong, mishandling a junior contributor, or letting an agent gatekeep where a human should is more damaging than any technical bug the project might ship — and the failure mode is not reversible by patch: a contributor who feels condescended-to by an agent and leaves does not get re-recruited.

The project commits to:

- **Agentic Mentoring-first sequencing** — Agentic Triage and Agentic Mentoring before Agentic Drafting and Agentic Pairing; Agentic Autonomous last.
- **ASF Privacy and Legal involvement from project start**, not retrospectively.
- **Contributor-sentiment evidence as a graduation criterion** for new automation modes alongside the standard technical-maturity criteria.
- **Tight feedback loop** — the SKILL-based approach with human oversight lets agentic skills self-update from maintainer / triager feedback and contributor responses; mistakes get corrected and message tone is tuned to the communication style the PMC selects.

## Ask of the Board

Adopt the accompanying resolution establishing the Apache Magpie Project as a Top-Level Project, with initial PMC roster as filed at the time of vote.
