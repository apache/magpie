<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [RFC-AI-0004: Principles of agentic interaction for open-source maintainers](#rfc-ai-0004-principles-of-agentic-interaction-for-open-source-maintainers)
  - [Abstract](#abstract)
  - [Status of this document](#status-of-this-document)
  - [Motivation](#motivation)
  - [Definitions](#definitions)
  - [Principle 1 — Human-in-the-Loop on every state change](#principle-1--human-in-the-loop-on-every-state-change)
    - [Normative statement](#normative-statement)
    - [Why this is the load-bearing principle](#why-this-is-the-load-bearing-principle)
    - [Five concrete consequences](#five-concrete-consequences)
    - [Narrow auto-merge carve-out](#narrow-auto-merge-carve-out)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid)
  - [Principle 2 — Secure sandbox by default](#principle-2--secure-sandbox-by-default)
    - [Normative statement](#normative-statement-1)
    - [Why this is necessary](#why-this-is-necessary)
    - [Architecture: three layers, layered](#architecture-three-layers-layered)
    - [Five concrete consequences](#five-concrete-consequences-1)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid-1)
  - [Principle 3 — Vendor neutrality](#principle-3--vendor-neutrality)
    - [Normative statement](#normative-statement-2)
    - [Two axes of neutrality](#two-axes-of-neutrality)
    - [Five concrete consequences](#five-concrete-consequences-2)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid-2)
  - [Principle 4 — Conversational, correctable agentic skills](#principle-4--conversational-correctable-agentic-skills)
    - [Normative statement](#normative-statement-3)
    - [Why this is structurally different](#why-this-is-structurally-different)
    - [Five concrete consequences](#five-concrete-consequences-3)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid-3)
  - [Principle 5 — Write access and outbound messages require human review](#principle-5--write-access-and-outbound-messages-require-human-review)
    - [Normative statement](#normative-statement-4)
    - [Why the dedicated principle](#why-the-dedicated-principle)
    - [Five concrete consequences](#five-concrete-consequences-4)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid-4)
    - [Cross-references](#cross-references)
  - [Principle 6 — Privacy by design](#principle-6--privacy-by-design)
    - [Normative statement](#normative-statement-5)
    - [Why this is its own principle](#why-this-is-its-own-principle)
    - [Five concrete consequences](#five-concrete-consequences-5)
    - [Vendor-neutrality of the privacy gate](#vendor-neutrality-of-the-privacy-gate)
    - [Anti-patterns to avoid](#anti-patterns-to-avoid-5)
    - [References to the broader privacy posture](#references-to-the-broader-privacy-posture)
  - [How the six principles compose](#how-the-six-principles-compose)
  - [Adoption guidance for non-Magpie projects](#adoption-guidance-for-non-magpie-projects)
  - [What this RFC does NOT specify](#what-this-rfc-does-not-specify)
  - [References](#references)
    - [Internal (this repository)](#internal-this-repository)
    - [External](#external)
  - [Acknowledgements](#acknowledgements)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Source: ASF Confluence wiki (RFCs space). Public-safe re-export:
     wiki-internal links and members-only references have been stripped
     per the Apache Magpie project's RFC-AI-0004 § Privacy-by-Design
     principle (no exposing of SSO-gated URLs in public artefacts).
     The authoritative source remains the Confluence page; this file
     is a public mirror for review by adopters who do not have ASF SSO. -->

# RFC-AI-0004: Principles of agentic interaction for open-source maintainers

| Field | Value |
|---|---|
| **RFC** | AI-0004 |
| **Title** | Principles of agentic interaction for open-source maintainers |
| **Status** | Draft |
| **Authors** | The Apache Magpie project (see [`MISSION.md`](https://github.com/apache/magpie/blob/main/MISSION.md) for roster) |
| **Initial draft** | 2026-05-07 |
| **Supersedes** | None |
| **Superseded by** | None |
| **Reference implementation** | [`apache/magpie`](https://github.com/apache/magpie) |
| **License** | Apache License 2.0 |

---

## Abstract

This RFC describes six principles that govern how AI agents should interact with open-source projects when **the human in the interaction is a project maintainer** — committer, PMC member, release manager, security-team member, triager. The six principles — **(1) human-in-the-loop on every state change**, **(2) secure sandbox by default**, **(3) vendor neutrality across LLM backends and project governance**, **(4) conversational, correctable agentic skills**, **(5) write access and outbound messages require human review**, and **(6) privacy by design** — are framed as *a baseline*. They define the minimum trust posture under which agentic tooling can be ethically deployed against the public artefacts of a community-governed project (issues, PRs, mailing lists, releases, security reports, contributor data).

The RFC is normative for the Apache Magpie framework ([`apache/magpie`](https://github.com/apache/magpie), the working draft of which is summarised in [`MISSION.md`](https://github.com/apache/magpie/blob/main/MISSION.md)) and is offered as a **pattern other projects can adopt or adapt** when integrating agentic tooling into their own maintainership workflow.

It is **not** a specification of any particular implementation detail (LLM choice, prompt format, model size, scaffolding library). The principles are independent of those choices.

---

## Status of this document

This is a **Draft**. The Apache Magpie project's reference implementation operationalises every principle in this RFC, but the RFC itself is the project's first attempt to extract the principles from the implementation and frame them as a portable contract. The next two milestones are:

1. **Public review** — comments solicited from ASF Members, non-ASF maintainers running similar agentic frameworks, and the ASF Responsible AI Initiative working group.
2. **Pilot validation** — the four principles tested against the Apache Magpie pilot cohort (one ASF PMC running the full security-issue flow, one ASF PMC running just triage + mentoring, at least one non-ASF project) before promotion from `Draft` to `Stable`.

---

## Motivation

Maintainers of open-source projects increasingly find themselves at the receiving end of agent-shaped tooling — bots that triage, auto-mergers that touch their default branch, scanners that file issues, AI-suggested PRs that propose code. The volume of such tooling is growing faster than the conventions for **how that tooling should behave**. The result, today, is a stack of implicit choices made by individual tool authors that vary across projects in ways that erode trust:

- A maintainer cannot tell, from a tool's surface alone, whether it operates **autonomously** or **with confirmation**, where the boundary lies, and what the rollback story is.
- Sandbox posture varies wildly. Some agents read everything in `~`; some read nothing. Some can `gh pr create`; some can silently push to the default branch. The maintainer is on the hook for figuring this out.
- Vendor lock-in is largely silent. A skill that "uses Claude" is a skill that *requires* Claude — not a skill that happens to use Claude today and would work on a local model tomorrow. The lock-in is rarely surfaced as a choice.
- "How do I correct this?" has become an afterthought. The maintainer who notices the agent is doing the wrong thing often has no path to fix it short of opening an upstream PR to the tool author.

This RFC names the four shifts that, taken together, make agentic tooling acceptable on a maintainer-governed project. Each shift is independently necessary; the combination is sufficient.

---

## Definitions

| Term | Definition |
|---|---|
| **Agent** | A program that selects and executes actions to advance a maintainer-stated goal, where at least one of those actions is mediated by an LLM and where action selection is conditioned on natural-language conversation rather than a pre-coded flow chart. |
| **Skill** | A package of agent-readable text (typically a markdown file with YAML frontmatter and bundled scripts/references) that scopes the agent to a single workflow. The Apache Magpie framework's skills (`security-issue-import`, `pr-management-triage`, etc.) are reference instances. |
| **Maintainer** | A human with write access (or comparable governance authority) on the target project. PMC members, committers, triagers, release managers all qualify; bots and agents do not. |
| **State change** | Any operation observable by parties outside the maintainer's local machine: posted comment, edited issue body, applied label, merged PR, sent email, written file under the repo's tracked path, etc. Operations that touch only the maintainer's `/tmp` or `~/.config/<framework>/` cache are **not** state changes. |
| **Confirmation** | An explicit, in-session, reversible-only-by-history act by the maintainer that authorises one specific state change. Standing approvals, "yes to all", and pre-approved-via-config are explicitly **not** confirmations. |
| **Sandbox** | An OS-level isolation boundary (filesystem namespacing, network filtering, syscall mediation) plus a tool-permissions layer plus a clean-environment wrapper, applied to every agent-launched subprocess. |

---

## Principle 1 — Human-in-the-Loop on every state change

### Normative statement

> Every state change an agent proposes against project artefacts MUST be presented to a maintainer as a *proposal*, and MUST NOT be applied until the maintainer issues an explicit per-proposal confirmation. The agent never confirms on the maintainer's behalf, never persists "always yes" approvals across sessions, and never bundles multiple state changes under one confirmation in a way that hides any single one from review.

### Why this is the load-bearing principle

A skill that triages 200 PRs in 10 minutes is doing 200 state changes. If the maintainer is not in the loop on each one, what they are doing is **delegating their committer authority to a program**. That is not what "AI-assisted maintainership" should mean. The committer's signature on every artefact is the entire basis of the project's trust model; the agent does not own that signature.

### Five concrete consequences

1. **Propose-then-apply, always.** The agent's natural unit of work is "here is the proposal, will you confirm?". The "apply" pass that follows confirmation is mechanical — no reasoning, no surprises, no second proposal hidden inside.
2. **Per-proposal confirmation, no batch yes.** Multiple state changes in the same response require a confirmation surface that lets the maintainer say "1, 3, 4 yes; 2 no". `all` as a one-keystroke shortcut is acceptable; the agent must still surface every item before honouring it.
3. **No standing pre-approvals.** A skill MUST NOT support a config switch that says "auto-approve every X-class proposal". The boundary between Agentic Drafting (agent-authored fix with human review) and Agentic Autonomous (narrowly-scoped auto-merge) is exactly this; Agentic Autonomous is governed by a separate, much stricter contract (see Principle 1, *narrow auto-merge carve-out* below).
4. **Drafts, never sends.** Outbound communication (email, chat) is **drafted** by the agent and stored in the communication system's drafts folder. The maintainer reviews and presses Send. The framework MUST NOT have a "yes, send the draft" path that bypasses the human read.
5. **Audit log of every confirmation.** Every applied state change writes a structured audit-log entry: timestamp, maintainer identity, proposal text, applied diff, triggering skill. Open-source maintenance is a public-trust activity; the trail makes future review possible.

### Narrow auto-merge carve-out

Agentic Autonomous ("limited fix-and-merge", in Apache Magpie's terminology) is the explicit exception. It permits auto-merge, but only after **all** of the following gate conditions hold:

- The change class is on a per-project, per-class allow-list (lint fixes, dependency bumps within an allow-list, license headers, formatting, broken-link repair). Security-class changes are explicitly out.
- The project has been running Agentic Triage, Agentic Mentoring, and Agentic Drafting with HITL confirmation for at least two release cycles, and a contributor-sentiment evaluation says the project is healthier, not just faster. See [`docs/contributor-sentiment.md`](../contributor-sentiment.md) for the evaluation methodology and the four signal dimensions (thread tone, time-to-first-reply, first-PR retention, reviewer load) that constitute this gate.
- Every auto-merged change is reversibly logged; reverts are one keystroke away.

The carve-out exists because lint-rebase-format has marginal human value and should not require a human in the loop forever. It is **off by default** in the reference implementation. A project that turns it on without first running the manual loop has skipped the proof.

### Anti-patterns to avoid

- **Standing "always-yes" tokens.** "Auto-approve all my agent's proposals for the next week" is a delegation, not a confirmation.
- **Implicit confirmation via inactivity.** "Will apply in 10 seconds unless cancelled" is not a confirmation; it is a default-yes that survives interruption.
- **Bundling.** "I'll apply changes A, B, C, D, E now" with one confirmation hides four of those changes from per-item review.
- **Server-side approval.** A web endpoint that accepts a pre-signed approval token bypasses the in-session boundary. The approval lives in the maintainer's terminal, not in the framework.

---

## Principle 2 — Secure sandbox by default

### Normative statement

> The agent's executing process MUST run inside an OS-level sandbox at all times. The sandbox MUST default-deny filesystem reads outside the project working tree and a small set of explicitly-permitted user-config paths, default-deny network egress to all hosts not on a project-declared allow-list, and default-deny invocation of binaries that the project's permission policy has not explicitly allowed. The sandbox is in addition to — not in replacement of — Principle 1's human-in-the-loop confirmation gate.

### Why this is necessary

LLM-driven agents read attacker-controlled text every time they run. Email subjects, PR titles, scanner findings, public commit messages, mailing-list archives, third-party PR comments — all of these are content the agent treats as input and that an attacker can shape. **No prompt-engineering technique neutralises this surface.** The fallback when prompt engineering fails has to be the operating system telling the agent's subprocess "no, you cannot read `~/.aws/credentials`" or "no, you cannot connect to `attacker.example.com`".

### Architecture: three layers, layered

The reference implementation (see [`docs/setup/secure-agent-internals.md`](https://github.com/apache/magpie/blob/main/docs/setup/secure-agent-internals.md)) uses a three-layer model. Other implementations MAY choose different mechanisms; the layering MUST be preserved:

| Layer | What it stops | Mechanism (reference) |
|---|---|---|
| **0. Clean environment** | Inherited credential-shaped env vars (`$AWS_*`, `$GH_TOKEN`, `$ANTHROPIC_API_KEY`, …). | A shell wrapper (`claude-iso`) that strips the agent's process env to a project-declared whitelist before exec. |
| **1. Filesystem + network sandbox** | Bash subprocess reads outside the project tree; outbound HTTPS to non-allowed hosts. | Linux: `bubblewrap` user-namespace + `socat` SNI proxy. macOS: `sandbox-exec`. |
| **2. Tool permissions** | The agent's own Read/Edit/Write/Bash tools touching denied paths or binaries. | The agent host's permission system (e.g., Claude Code's `permissions.deny`). |
| **3. Forced confirmation** | Visible-to-others writes that haven't been seen by a human. | `permissions.ask` for every state-mutating shell call (e.g., `gh pr create`, `gh issue edit`, `gh gist *`, `gh secret *`). Implements Principle 1 at the OS layer. |

### Five concrete consequences

1. **Default deny, allow-list opt-in.** New paths and new hosts require an explicit project-policy edit, surfaced in code review on the framework's `settings.json` (or equivalent). "I'll just allow `~/`" is not an answer.
2. **Permission patterns are advisory; the OS layer is the enforcement.** The deny list (`Bash(curl *)`, `Bash(wget *)`) is a friction layer that catches sloppy injection. The network allow-list is the actual control. Document this honestly; do not pretend the permission layer is the boundary.
3. **The clean-env wrapper is not optional.** A maintainer who typed `export GITHUB_TOKEN=…` in their shell once should not have that token visible to every agent subprocess thereafter. The wrapper is the only reason the agent's child `gh` call does not see your personal access token by accident.
4. **Tempfile + `printf '%s'` for attacker-controlled text** — any string that originated outside the framework (email subject, PR title, scanner finding, reporter-supplied free text) MUST NOT be inlined into a single- or double-quoted shell argument. Write it to a tempfile via `printf '%s' "$value" > /tmp/x` (no expansion) and pass via `gh api ... -F field=@/tmp/x` (verbatim from disk).
5. **Wrap untrusted bodies as inert text** when persisting them to project-visible artefacts. A four-backtick fenced code block defangs tracking pixels and markdown directives so future re-reads in fresh agent contexts see them as data, not instructions.

### Anti-patterns to avoid

- **`Bash(*)` and pray.** A blanket allow-bash with a long deny-list misses every wrapper-interpreter trick (`python3 -c`, `node -e`, `bash -c '…'`, `c''url …`, `/usr/bin/curl …`, chained pipelines on macOS). The deny-list is *advisory*; the control is the network allow-list.
- **`--body "$x"` interpolation.** Shell expansion of attacker-controlled text inside double quotes is the most common shell-breakout vector and the prek hooks do not catch it. Use `--body-file <path>` instead, always.
- **Implicit network egress.** Allowing `github.com` silently authorises `gh gist create` / `gh repo create --public`. Confirmation prompts (`permissions.ask`) on every state-mutating `gh` call are how Principle 1 meets Principle 2 at the OS layer.

---

## Principle 3 — Vendor neutrality

### Normative statement

> The framework MUST NOT bind a maintainer's workflow to any single LLM vendor, model size class, hosting provider, or project-governance model. A skill that "works with Claude" MUST be expressible in a form that other LLM agents can consume; a workflow that integrates an ASF release process MUST work, with config substitution only, against a non-ASF project's release process.

### Two axes of neutrality

**Axis A — LLM backend neutrality.** Skills are markdown-with-YAML, not vendor-specific prompts. The agentic host (Claude Code, Codex, Gemini CLI, a local-Ollama wrapper, a future Apache-aligned agent runtime) consumes the same skill file and behaves comparably. The reference implementation documents this explicitly: skills are "language-independent, since SKILLs are English; standard Python ecosystem dependencies for the deterministic-output scripts; no AI SDK integration needed".

**Axis B — Project-governance neutrality.** ASF integrations (private mailing lists, Vulnogram CVE flows, PMC roles, ASF release process) are configurable, not hardcoded. A non-ASF adopter swaps in a private GitHub repo, GitHub Security Advisories, a maintainer roster, their own release process — and the same skill executes. The reference implementation's placeholder convention (`<tracker>`, `<upstream>`, `<security-list>`, `<private-list>`) and the `<project-config>/` adapter dir are how this is operationalised.

### Five concrete consequences

1. **Pluggable backend.** The framework's skills cite no model name in their flow logic. "Use the strongest model available" / "use a fast model for this lookup step" are acceptable hints; "must be Claude Sonnet 4.5" is not.
2. **Pluggable adapters.** Private-mailing-list, CVE-tool, release-process, and audit-finding ingest MUST live behind adapter modules. The reference implementation's `tools/<adapter>/` directories (`tools/cve-tool-vulnogram/`, `tools/gmail/`, `tools/ponymail/`) are this pattern.
3. **Pilot diversity.** Validation runs (per the Apache Magpie [MISSION.md](https://github.com/apache/magpie/blob/main/MISSION.md)) cover at least one frontier-model backend, at least one fully-local inference setup (Ollama / vLLM / equivalent), and at least one Apache-hosted or Apache-aligned endpoint. A framework that only validates against one vendor is a vendor-locked framework that has not noticed yet.
4. **Privacy-LLM gating is vendor-neutral by construction.** Private content (security reports, embargoed CVE detail, PMC-private mail) flows only to LLMs the project's PMC has explicitly approved. "Approved" is per-PMC, not per-framework — the framework's contribution is the gate check, not the policy. See [`tools/privacy-llm/`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/) for the reference gate.
5. **License + IP posture.** Framework code AL2.0 / MIT. Skills AL2.0. Generated artefacts (commit messages, PR bodies, advisory drafts) inherit the maintainer's commit licence; the framework MUST NOT introduce a vendor's model-output licence by reference.

### Anti-patterns to avoid

- **"Cloud-only"-shaped skills.** A skill whose flow assumes a remote model with internet round-trip is a skill that locks the project to a vendor *and* breaks for offline / sovereign / air-gapped pilots. Skill flows assume the agent runtime exists; they do not assume what's behind it.
- **Vendor-named tools.** A skill called `claude-pr-review` is a skill that ages out the day a maintainer wants to use another agent. Tools are named for what they do, not what runs them.
- **Hardcoded ASF assumptions.** `apache/<project>` strings hardcoded into a skill make the skill ASF-only by accident. Placeholder discipline (`<upstream>`, `<tracker>`, `<security-list>`) is the cheapest way to keep the option open.

---

## Principle 4 — Conversational, correctable agentic skills

### Normative statement

> The agent's behaviour MUST be expressed as **agent-readable markdown** (skill files) that the maintainer can read, understand, override locally, and contribute back upstream through the normal patch workflow. The conversation between maintainer and agent — including the corrections the maintainer makes when the agent gets it wrong — MUST be the primary mechanism by which the framework's skills evolve.

### Why this is structurally different

The instinct from twenty years of writing services is to encode behaviour in code, configuration files, or YAML. **An agent's prompts and skill files are code in every meaningful sense, but their "compile" step is the conversation that follows.** The maintainer notices the agent is using the wrong tone in mentor replies, edits the skill's tone block, the next invocation behaves differently, and (after a stabilisation period) the edit is upstreamed.

The shift the maintainer makes is from "this tool needs a code change" to "this skill needs a markdown edit". The shift the framework makes is from "user-of-tool" to "co-author-of-tool".

### Five concrete consequences

1. **Skills are markdown.** Not YAML. Not JSON. Not a DSL. Markdown with YAML frontmatter and inline code blocks. The maintainer reads them like documentation; the agent reads them like instructions; the diff between two revisions is reviewable in the normal PR review surface.
2. **Local override before upstream PR.** The reference implementation's `.apache-magpie-overrides/<skill>.md` convention lets a maintainer encode "for this project, do X differently" without forking the framework. The override file is committed in the adopter's repo; the framework reads it at runtime and merges agent-readable modifications before executing the default behaviour.
3. **Upstream loop is first-class.** When an override has stabilised — typically after a few weeks of running — the `setup-override-upstream` skill (or equivalent) walks the maintainer through promoting the override into a framework PR. Some overrides stay local forever (project-specific policy); some belong upstream (general improvement). The framework MUST surface the choice explicitly.
4. **Correction is in-conversation.** The maintainer says "stop using `--repo` argument; my project uses `--repository`" and the agent acknowledges, applies the change in this session, and surfaces the override-file path so the correction persists across sessions. The maintainer is not expected to know the framework's source layout to make a behaviour change stick.
5. **Skills carry their own provenance.** Every skill cites what it does, what it does **not** do, the placeholders it uses, the adapter-config knobs it consults, and (where applicable) the upstream commit it was derived from. The maintainer who reads the skill knows what they are trusting.

### Anti-patterns to avoid

- **Black-box agents.** "The agent does what the agent does" is the worst possible posture. The maintainer must be able to read *why* the agent is doing X and *change* the governing instruction.
- **Forks as the correction mechanism.** "Fork the framework, fix the skill, run your fork" makes everyone the maintainer of their own framework. The local-override path keeps the maintainer in their lane.
- **Hidden state.** A skill whose behaviour depends on conversation history that is not surfaced in the skill file cannot be corrected. State that lives only in the LLM's context window is invisible to git; it cannot be reviewed, cannot be diff'd, cannot be tested.
- **Implicit "training".** A framework that quietly fine-tunes on the maintainer's corrections without surfacing the resulting drift is making model changes the maintainer did not consent to. Corrections live in the skill files (visible, version-controlled), not in the model weights (invisible, opaque).

---

## Principle 5 — Write access and outbound messages require human review

### Normative statement

> Every operation that mutates state visible to parties outside the maintainer's local machine — every `git push`, every `gh issue create / edit / close / merge`, every label add / remove, every label-driven workflow trigger, every outbound email, every Slack / IRC / Matrix / mailing-list post, every release artefact upload — MUST be reviewed by the maintainer in its **final, post-render form** before it is sent. The agent's role on the outbound path ends at "draft prepared". The press of Enter / Send / Submit is the maintainer's, on a surface where the maintainer can inspect the literal bytes that will land.

This principle is the operational specialisation of [Principle 1](#principle-1--human-in-the-loop-on-every-state-change) for the two highest-blast-radius surfaces: **write access to the project's source-of-truth** (the git repo, the issue tracker, the project board, the release surface) and **outbound communication on the project's behalf** (email to mailing lists, replies to security reporters, comments tagged with the maintainer's handle).

### Why the dedicated principle

The general HITL principle catches "the agent is mutating state". The two surfaces below need their own callout because they share three properties that make them especially unforgiving:

1. **Public, attributed, and durable.** A merged PR carries the maintainer's signature in the git history forever. A reply on a public mailing list shows in the archive forever. There is no quiet rollback; only a louder correction.
2. **Asymmetric reach.** A push to `main` propagates to every downstream user; an email to `users@<project>` reaches every subscriber. The cost of a wrong byte is multiplied by the audience size.
3. **Trust-load-bearing.** Maintainership is a trust relationship. An outbound message in the maintainer's voice that the maintainer did not author, and would not have phrased that way, erodes that trust at exactly the surface it lives on.

### Five concrete consequences

1. **Drafts, never sends.** Outbound messages (email, mailing-list post, security-team relay, contributor reply) are **drafted by the agent and saved in the communication system's drafts folder**. The maintainer opens the draft in the actual mail / IRC / chat client, reads it as the recipient would, and presses Send.

- The framework's drafting backend writes a draft. It does not — and the contract MUST explicitly forbid this — call the *send* method on the same backend.
- "Send after timeout" / "auto-send unless cancelled" is a send, not a draft. Forbidden.

1. **`gh pr create --web` over `gh pr create`.** When opening a public pull request, the framework's flow ends at *"opening the browser at the PR-create page with the body pre-populated"*. The maintainer reviews in the browser and clicks the *Create pull request* button themselves. Same for `gh issue create --web` and equivalent flows.
2. **`--body-file` over `--body`** for any `gh issue comment / gh pr comment / gh issue create / gh pr review` invocation that *is* automated. The body must be a file the maintainer reads before the call runs. String-form `--body "$x"` re-introduces shell expansion at the wrong layer and is forbidden — see [Principle 2 — anti-patterns](#anti-patterns-to-avoid-1).
3. **Confirmation surface shows the rendered output, not the plan.** Before posting a PR review, the agent renders the final review body (with all variable substitutions resolved, markdown applied, line-numbered code references inlined) and shows that to the maintainer for confirmation — not "I plan to post a review with N comments". The maintainer reads what GitHub will show, not what the agent intends.
4. **Write tokens are clean-env injected, not shell-inherited.** The agent's `gh` token, `git` push credentials, mailing-list submission key, etc. are visible to the agent's subprocess *only* because the project's clean-env wrapper deliberately passes them through (see [Principle 2 layer 0](#architecture-three-layers-layered)). They are **not** inherited from the maintainer's interactive shell. The framework's permission policy MUST forbid the agent from reading the on-disk credential file directly (`Read(~/.config/gh/**)`, `Read(~/.netrc)`, etc.); the credential surface is **only** what the parent process already negotiated and forwarded.

### Anti-patterns to avoid

- **"Auto-send drafts older than N hours."** A timer is not a human review. Forbidden.
- **CLI tools with both `draft` and `send` modes the agent can pick from.** The framework's drafting tool MUST NOT expose a send action at all; only the human's mail client can send.
- **Posting to mailing lists from the agent.** Mailing lists are write-once, archive-forever surfaces. Drafts go to the maintainer's outbox; the maintainer presses Send.
- **Bots that comment on issues with the maintainer's handle.** A bot that operates as `@maintainer-handle` is indistinguishable to readers from the maintainer. If the comment has to be attributed to a human, a human writes it (or signs off on a draft and posts it under their own handle).
- **Server-side approval tokens.** A pre-signed "yes-go-ahead-and-send" token from a bot framework is a delegation of the press-Send moment, not a confirmation. Forbidden.

### Cross-references

- Principle 1's *Drafts, never sends* sub-rule and the *audit-log of every confirmation* requirement.
- Principle 2's `permissions.ask` layer for state-mutating `gh` calls — that is how this principle is enforced at the OS layer.
- Principle 6 below — outbound messages can carry private content; the privacy gate fires *before* the draft, this principle fires *at the draft → send boundary*.

---

## Principle 6 — Privacy by design

### Normative statement

> Private content — security-issue reports, embargoed CVE detail, PMC-private mail, contributor PII (full names, email addresses, IPs), reporter-supplied test artefacts — MUST be handled by the framework as if it had a chain-of-custody requirement. Specifically: **(a) only LLMs the project's PMC has explicitly approved may receive private content**; **(b) PII MUST be redacted before any LLM read where the content is not strictly needed for the task**; **(c) the framework MUST provide a per-skill gate that verifies the LLM-of-the-moment is approved before any private read happens**; **(d) every outbound public artefact (CVE record, public advisory, public-PR description) MUST be mechanically checked for private content leakage** before it leaves the framework's control.

### Why this is its own principle

Privacy and security overlap but are not identical. Security (Principle 2) defends against the agent doing the wrong thing. Privacy defends against the agent doing the *right* thing *with the wrong audience*. A correctly-functioning agent that forwards a security report's reporter-PII to a non-approved external LLM has not been compromised — it has been used as designed against a privacy boundary the framework should have enforced.

The reference implementation operationalises this principle in [`tools/privacy-llm/`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/) — see [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md) for the adopter-facing setup and [`tools/privacy-llm/wiring.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/wiring.md) for the *redact-after-fetch* protocol that every skill reading Gmail private mail follows.

### Five concrete consequences

1. **Approved-LLM gate.** The project's PMC declares the set of LLMs that may receive private content. The list is per-PMC, not per-framework — Apache Magpie's gate-check tool (`tools/privacy-llm/checker/`) enforces the gate but the *policy* is the project's. The reference list defaults to "Claude Code trusted; `*.apache.org` auto-approved; `localhost` for local-inference setups; everything else requires explicit opt-in."
2. **Redact-before-read.** When a skill fetches Gmail or PonyMail private content, it pipes the fetched bytes through the framework's PII redactor (`tools/privacy-llm/redactor/`) *before* the LLM sees them. Reporter names → `N-<hash>`, email addresses → `E-<hash>`, IPs → `IP-<hash>`. The skill operates on the hash-prefixed identifiers; the reverse map lives only on the maintainer's local disk (mode 0600, never committed), and the *reveal* step happens at draft-write time inside the maintainer's own process, not inside an LLM call.
3. **Reporter-PII is redacted, but reporter *credit* is not.** The redaction is for in-context PII — the reporter's name and email when the agent is reasoning about routing, triage, deduplication. The reporter's *publicly-credited* identity (e.g., "Reported by Jane Smith" in the CVE record's `credits[]` field) is a deliberate output and passes through unredacted, only after the maintainer confirms the credit shape with the reporter on the inbound thread.
4. **Confidentiality scrub before public emission.** Every skill that emits a public artefact (advisory email, public PR body, public CVE-record JSON, GitHub Security Advisory) MUST run a confidentiality scrub against the draft body: regex match for `CVE-\d{4}-\d{4,7}` (forbidden in pre-disclosure public PRs), reporter names from the private mapping table, mailing-list addresses, and any string the project's policy file enumerates as private. The scrub fires before the draft is shown to the maintainer; failures stop the flow with a specific message.
5. **Audit log is privacy-aware.** The audit log of agent actions (Principle 1, consequence 5) MUST NOT contain un-redacted PII or private content. Logs reference redactor identifiers (`N-<hash>`) and the local mapping resolves them only when a maintainer opens a specific audit entry on their own machine.

### Vendor-neutrality of the privacy gate

The privacy gate's *policy* is set by the project's PMC; the gate's *implementation* is vendor-neutral by construction (Principle 3). A frontier-model backend, a local Ollama instance, and an Apache-aligned endpoint all pass through the same gate-check. The gate accepts or rejects based on the endpoint's hostname / identity, not on which company hosts it.

### Anti-patterns to avoid

- **Logging full email bodies for "debugging".** Audit logs with un-redacted private content are a privacy incident waiting for a backup tape to be misplaced. Redacted identifiers only.
- **"Just this once" approved-LLM bypasses.** A one-off "let me run this through GPT-5 to see what it thinks" is a policy violation. The PMC sets the list; the maintainer does not have a personal exception.
- **Reverse-mapping in LLM calls.** The redactor's reverse map (hash → real PII) MUST stay in the maintainer's local process. Sending it to an LLM defeats the redaction.
- **PII in commit messages.** Public commit messages and PR bodies are durable public records. The confidentiality scrub catches the obvious cases; skill authors must avoid the non-obvious ones (the pattern catalogue at `tools/privacy-llm/pii.md` enumerates them).

### References to the broader privacy posture

- The reference implementation: [`tools/privacy-llm/`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/) (the gate
- the redactor + the wiring contract).
- The adopter-facing privacy setup: [`docs/setup/privacy-llm.md`](https://github.com/apache/magpie/blob/main/docs/setup/privacy-llm.md).
- The PII pattern catalogue: [`tools/privacy-llm/pii.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/pii.md).
- The redact-after-fetch protocol every Gmail-reading skill follows: [`tools/privacy-llm/wiring.md`](https://github.com/apache/magpie/blob/main/tools/privacy-llm/wiring.md).
- **Cross-cutting privacy AIP** —
- The [ASF Privacy Policy](https://privacy.apache.org/policies/privacy-policy-public.html) — foundation-level baseline every ASF project inherits; this RFC layers agentic-specific obligations on top.

---

## How the six principles compose

The six principles are independently necessary; together they form a cycle the maintainer can repeatedly apply:

```text
   ┌──────────────────────────────────────────────────────┐
   │                                                      │
   ▼                                                      │
[Skill]  ─── proposes ──▶  [Maintainer]  ─── confirms ──▶ │
 ▲                              │                         │
 │                              │ corrects                │
 │                              ▼                         │
 │                        [Override file]  ─── upstream ──┘
 │                              │
 └────── reads at runtime ──────┘

         Sandbox is under everything.                    (2)
         Vendor neutrality means any LLM
         can play the [Skill] role.                     (3)
         Write / send is a maintainer click,
         never the agent's.                             (5)
         Private content stops at the
         approved-LLM gate.                             (6)
```

- **(1)** says the [Maintainer → confirms] arrow is mandatory.
- **(2)** says the [Skill] runs in a fenced room.
- **(3)** says the [Skill] is portable across the agentic hosts — Claude Code today, a different host tomorrow.
- **(4)** says the [Maintainer → corrects → Override → Skill] loop is how the framework gets better.
- **(5)** says the *write* and *send* points on the [Maintainer → confirms] arrow are non-delegable.
- **(6)** says private content sees only LLMs the PMC has approved, redacted before read, scrubbed before emission.

Drop any one of the six and the system regresses to a recognisable bad pattern: drop (1) and you have an autonomous agent the maintainer is on the hook for; drop (2) and one prompt injection ruins the day; drop (3) and the project becomes a vendor's cost centre; drop (4) and the skill is a black box only the framework's authors can fix; drop (5) and the agent is sending mail in the maintainer's voice; drop (6) and a security reporter's PII ends up in a vendor's training corpus.

---

## Adoption guidance for non-Magpie projects

A project that wants to adopt these principles without adopting Apache Magpie as a whole has the following minimum bar:

1. **Pick an agent host with HITL primitives.** Claude Code, Cursor's Composer, and Aider all support per-action confirmation. Avoid hosts that default to "auto-apply suggested changes".
2. **Wrap the host in an OS sandbox.** On Linux, `bubblewrap` + a network-allow-list HTTP proxy is one day's work. On macOS, a `sandbox-exec` profile is similar. The agent's parent shell runs in the sandbox; every subprocess inherits.
3. **Treat skill files as code.** Land them in a `skills/` directory under your project's main repo or a sibling `<project>-magpie` repo. PR them. Review them. Diff them. Don't hand-edit them on production machines without committing.
4. **Document the adapter boundaries.** What is project-specific (your release process, your CVE flow, your private mailing list)? Move those into a `<project-config>/` directory with documented placeholders and let the skills consult them.
5. **Pilot before scale.** Run the agent against your project's own backlog for a release cycle before letting it touch contributor-facing artefacts at full speed. The contributor-sentiment data you collect during the pilot is the only honest signal that the framework is helping, not just speeding up the harm.

The Apache Magpie project is happy to consult on the lift — see [`MISSION.md`](https://github.com/apache/magpie/blob/main/MISSION.md) for the maintainer- education stream.

---

## What this RFC does NOT specify

- **Specific LLM choice.** The principles are independent of the model. Pick the model that meets the project's privacy / cost / latency / sovereignty constraints.
- **Specific UI.** A terminal-based CLI, a CI bot, an IDE extension, a web dashboard — all are valid surfaces. The principles apply identically.
- **Specific scaffolding library.** LangGraph, BAML, raw Anthropic SDK, raw OpenAI SDK, ollama-cli, llamafile — pick one. The skills are the contract; the runtime is an implementation detail.
- **Pricing or hosting.** The project is the buyer; the vendor is the seller. The framework declines to express a preference on either.
- **Mandatory model evaluation.** Per-skill eval is recommended but not required by this RFC. A separate RFC may cover evaluation methodology — see the Apache Plumb collaboration in [`MISSION.md`](https://github.com/apache/magpie/blob/main/MISSION.md).

---

## References

### Internal (this repository)

### External

- [Apache Software Foundation Responsible AI Initiative](https://news.apache.org/foundation/entry/the-apache-software-foundation-launches-10m-responsible-ai-initiative-with-initial-1-75m-donation) — the broader policy context this RFC participates in.
- [ASF Generative-Tooling Policy](https://www.apache.org/legal/generative-tooling.html) — the licence and contribution-attribution baseline every agentic-tooling RFC under the ASF umbrella inherits.
- [Anthropic Responsible Scaling Policy](https://www.anthropic.com/responsible-scaling-policy) — vendor-side counterpart to the maintainer-side principles in this RFC. The two are complementary; neither substitutes the other.

---

## Acknowledgements

This RFC distils principles operationalised in the Apache Magpie reference implementation. The PMC roster and collaborator list (see [`MISSION.md`](https://github.com/apache/magpie/blob/main/MISSION.md)) includes the people whose discussion, code, and incident-review work shaped these principles. The framing of the principles here owes a particular debt to the 2026-05 prompt-injection audit ([gist](https://gist.github.com/andrew/0bc8bdaac6902656ccf3b1400ad160f0)) that surfaced the Principle 2 specifics, and to the Agentic Triage/Agentic Mentoring/Agentic Drafting/Agentic Autonomous swimlane discussion that surfaced the carve-out structure of Principle 1.
