<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Labels and capabilities](#labels-and-capabilities)
  - [Label dimensions](#label-dimensions)
    - [1. `family:*` — subject](#1-family--subject)
    - [2. capability — two axes (skills vs tools)](#2-capability--two-axes-skills-vs-tools)
    - [Coverage qualifiers](#coverage-qualifiers)
    - [3. `kind:*` — change type (pre-existing)](#3-kind--change-type-pre-existing)
    - [4. `mode:*` — handling mode (pre-existing)](#4-mode--handling-mode-pre-existing)
    - [Standalone labels](#standalone-labels)
  - [Capability to skill map](#capability-to-skill-map)
  - [Capability to tool map](#capability-to-tool-map)
  - [MCP servers, classified by capability](#mcp-servers-classified-by-capability)
  - [The rule](#the-rule)
    - [A GitHub issue](#a-github-issue)
    - [A pull request](#a-pull-request)
    - [A new tool under `tools/`](#a-new-tool-under-tools)
    - [A new skill under `.claude/skills/`](#a-new-skill-under-claudeskills)
    - [A new doc under `docs/`](#a-new-doc-under-docs)
  - [Why this exists](#why-this-exists)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Labels and capabilities

This page is the canonical reference for the label taxonomy used on
issues and pull requests in this framework repository
(`apache/magpie`). It also defines the **capability** model
that classifies what each skill or tool in the framework actually
*does*, independent of which subject area it sits under.

Every issue and pull request opened against this repository should
carry at least one **`family:*`** label and at least one
**`capability:*`** label. New tools and new skills must declare their
capability up front (see [The rule](#the-rule)).

> **Scope caveat.** This taxonomy applies to *this framework
> repository*. Skills that create issues or PRs on an **adopter's
> tracker** (e.g. `security-issue-import`, `security-issue-fix`,
> `issue-fix-workflow`) use the adopter's own label scheme — adopters
> are free to mirror this taxonomy in their own repo but are not
> required to.

---

## Label dimensions

The repository's labels fall into four orthogonal dimensions. An issue
or PR typically carries one label from each dimension that applies.

### 1. `family:*` — subject

What part of the framework does this touch?

| Label | Covers |
|---|---|
| `family:pr-management` | `pr-management-*` skills |
| `family:security` | `security-*` skills, `security-tracker-stats-dashboard` |
| `family:setup` | `setup-*` skills, framework adoption, agent-sandbox setup |
| `family:issue` | `issue-*` skills (`issue-triage`, `issue-fix-workflow`, `issue-reassess`, `issue-reassess-stats`, `issue-reproducer`, `issue-stale-sweep`, `issue-deduplicate`, `issue-backlog-stats`) |
| `family:tools` | Substrate tools under `tools/*` (CLI bridges, agent-runtime adapters, mail-source backends) |
| `family:ci` | `.github/` workflows, prek, validators |
| `family:docs` | `docs/`, `MISSION.md`, READMEs |

### 2. capability — two axes (skills vs tools)

Per [RFC-AI-0005](rfcs/RFC-AI-0005.md), "capability" is **two orthogonal
vocabularies**, one per entity. A skill carries one or more **skill
capabilities** (`capability:*`); a tool carries one or more **tool
capabilities** (`contract:*` or `substrate:*`). List **all** that apply;
do not pick a single "primary".

**Axis 1 — skill capability** (`capability:*`) — the workflow-lifecycle
phase a skill performs:

| Label | Definition |
|---|---|
| `capability:triage` | Sweep a queue, classify candidates, propose dispositions for human confirmation. |
| `capability:review` | Deep per-item code review of a PR or local diff; also contributor mentoring (single-item teaching intervention). |
| `capability:fix` | Implement a code change against an upstream repo to resolve a triaged issue. |
| `capability:intake` | Import external signal (mailing list, scan report, public PR) into a tracker entry, or keep an existing entry reconciled with one of those sources. |
| `capability:reconciliation` | Compare tracker state against an external inventory (e.g. ASF security dashboard, organization-wide issue registry); surface drift; propose corrections. Does **not** write to either source. |
| `capability:resolve` | Close-out actions: invalidate, dedupe, CVE-allocate, post-announcement housekeeping. |
| `capability:reassess` | Re-run resolved or end-of-life issues against current code to verify still-fixed / still-broken. |
| `capability:stats` | Read-only dashboards, metrics, governance evidence, contributor nomination briefs. |
| `capability:platform` | Framework / agent substrate skills: install, verify, update, doctor, override-upstream, status, shared-config-sync, the `setup` bootstrap. |
| `capability:authoring` | Skills that author or maintain other skills: `write-skill`, `optimize-skill`. |

**Axis 2 — tool capability** (`contract:*` / `substrate:*`) — the
interface a tool/adapter provides. `contract:<name>` implements a
capability contract under `tools/<contract>/`; `substrate:<name>` is
framework substrate:

| Label | Kind | Definition |
|---|---|---|
| `contract:tracker` | contract | Issue / board / label backend. |
| `contract:source-control` | contract | Branch / commit / diff / push (VCS). |
| `contract:change-request` | contract | Proposed-change review + merge gate (pull request / merge request / Gerrit change). |

| `contract:mail-archive` | contract | Mailing-list / forum archive reads. |
| `contract:mail-source` | contract | Inbound-mail ingestion (mbox / IMAP / …). |
| `contract:mail-create` | contract | Outbound mail composition. Always produces an editable draft; sending is a separate human-approved step on that draft (draft mode = default and the only mode implemented today; send mode declared but unimplemented — no autonomous send). |
| `contract:cve-authority` | contract | CVE allocation / record management / publication. |
| `contract:report-relay` | contract | Inbound security-report relay detection. |
| `contract:scan-format` | contract | Security-scanner report parsing. |
| `contract:project-metadata` | contract | Governance rosters / people / releases. |
| `substrate:analytics` | substrate | Read-only metrics / dashboards / renderers. |
| `substrate:sandbox` | substrate | Agent isolation, egress control, settings audit. |
| `substrate:action-guard` | substrate | Deterministic pre-tool-use command guards. |
| `substrate:privacy` | substrate | PII redaction / approved-LLM gating. |
| `substrate:framework-dev` | substrate | Build / validate / eval the framework itself. |

### Coverage qualifiers

Some tool READMEs may declare a `Coverage:` qualifier next to a capability
when the tool intentionally implements only part of a contract.

`partial-read-only` means the tool implements a read-only subset of named
contract operations, but does not satisfy the complete contract and must not
be advertised as a complete/selectable backend.

Both capability axes are **orthogonal** to `family:*`. A single
query can answer "how is our triage stack doing across PR + issue +
security?" by filtering on `capability:triage` alone, without
enumerating per-area queries.

**Agent-harness support (substrate tools only).** A substrate tool that
integrates with the agent runtime (a hook, a settings file, a launcher)
declares a `**Harness:**` field naming the harness(es) it supports, or
`agnostic` when it depends on none. This is the *agent-harness* axis of
LLM-integration neutrality and is scored by
[`tools/vendor-neutrality-score`](../tools/vendor-neutrality-score/) —
distinct from a tool's `**Runtime:**` field, which is its *execution*
environment (e.g. "Python stdlib"). The recognised harnesses are: Claude
Code, Codex, Cursor, Gemini CLI, Copilot, OpenCode, Kiro. A tool is
harness-neutral when it is `agnostic` or supports two or more harnesses.

### 3. `kind:*` — change type (pre-existing)

| Label | Covers |
|---|---|
| `kind:dx` | Maintainer dev-loop / CLI UX |
| `kind:policy` | Rule changes (eligibility, thresholds, behaviour switches) |
| `kind:perf` | Token / latency / API-call budget |
| `kind:adopter-config` | Per-adopter knob |

### 4. `mode:*` — handling mode (pre-existing)

| Label | Covers |
|---|---|
| `mode:Triage` | Agentic Triage — spot, classify, route, surface duplicates |
| `mode:Mentoring` | Agentic Mentoring — teaching-register issue/PR interventions + good-first-issue authoring |
| `mode:Drafting` | Agentic Drafting — agent-authored fix, human-reviewed PR |
| `mode:Pairing` | Agentic Pairing — developer-side dev-cycle skills with mentorship intrinsic |
| `mode:Autonomous` | Agentic Autonomous — narrowly-scoped auto-merge (off until Triage/Mentoring/Drafting run 2 quarters) |
| `mode:cross-cutting` | Spans multiple modes |
| `mode:platform` | Substrate / infra — not a mode (sandbox, CI, validators) |

### Standalone labels

`marketing` (branding artefacts), `dependencies` (dependency-update
PRs), `python:uv` (Python uv-managed code), plus the default GitHub
labels (`bug`, `enhancement`, `documentation`, `good first issue`,
etc.).

---

## Capability to skill map

Capabilities for every skill currently in
[`.claude/skills/`](../skills/). Skills with two values
(separated by `+`) carry both labels.

| Skill | Capability / capabilities |
|---|---|
| `pr-management-triage` | `capability:triage` |
| `issue-triage` | `capability:triage` |
| `issue-stale-sweep` | `capability:triage` |
| `pr-stale-sweep` | `capability:triage` |
| `security-issue-triage` | `capability:triage` |
| `ci-runner-audit` | `capability:triage` |
| `dependency-audit` | `capability:triage` |
| `workflow-security-audit` | `capability:triage` |
| `license-compliance-audit` | `capability:triage` |
| `flaky-test-triage` | `capability:triage` |
| `reviewer-routing` | `capability:triage` *(scores the configured reviewer roster on area match, git-history familiarity, and open-review load; proposes a primary reviewer plus optional backup — read-only, propose-then-confirm)* |
| `pr-management-quick-merge` | `capability:triage` + `capability:review` *(screens the ready-for-review queue for trivial, all-gates-green PRs — triage; submits the maintainer's approve on per-PR confirmation — review)* |
| `pr-management-code-review` | `capability:review` |
| `pairing-self-review` | `capability:review` |
| `pairing-multi-agent-review` | `capability:review` |
| `pre-first-pr-check` | `capability:review` *(newcomer-facing pre-flight checklist: SPDX headers, commit shape, Generated-by trailer, placeholder convention — read-only)* |
| `pr-management-mentor` | `capability:review` |
| `good-first-issue-author` | `capability:review` *(authors a newcomer-ready good first issue — contributor mentoring on the supply side)* |
| `good-first-issue-sweep` | `capability:review` + `capability:triage` *(sweeps the open issue backlog for GFI candidates; scores each against the G1–G7 rubric and proposes the label on maintainer confirmation — a triage sweep in the mentoring family)* |
| `mentoring-welcome` | `capability:review` *(drafts a first-contact orientation comment for first-time contributors on issues and PRs)* |
| `onboarding-concierge` | `capability:review` *(answers newcomer "how do I contribute here" questions from the project's contributing guide; hands off design, security, and out-of-scope queries to a human)* |
| `newcomer-issue-explainer` | `capability:review` *(explains a good-first-issue in beginner terms and sketches an approach; read-only, never posts without confirmation)* |
| `issue-fix-workflow` | `capability:fix` |
| `audit-finding-fix` | `capability:fix` |
| `security-issue-fix` | `capability:fix` + `capability:resolve` *(opens the PR that closes the tracker — both phases)* |
| `security-issue-import` | `capability:intake` |
| `security-issue-import-from-md` | `capability:intake` |
| `security-issue-import-from-pr` | `capability:intake` |
| `security-issue-import-via-forwarder` | `capability:intake` |
| `security-issue-import-from-scan` | `capability:intake` |
| `security-issue-sync` | `capability:intake` *(+ `capability:reconciliation` once [#337](https://github.com/apache/magpie/issues/337) lands the ASF-dashboard step)* |
| `setup-shared-config-sync` | `capability:intake` + `capability:platform` *(reconciles user-scope config to a sync repo; the act is intake, the subject is setup)* |
| `release-vote-tally` | `capability:triage` + `capability:resolve` *(reads the vote thread / approval signal, classifies each reply as binding or non-binding, tallies the result — triage over the vote-thread queue — and drafts the `[RESULT] [VOTE]` close-out email for RM review — resolve)* |
| `release-prepare` | `capability:resolve` *(drafts the planning issue, prep PR, and post-release bump PR that open the release lifecycle)* |
| `release-announce-draft` | `capability:resolve` *(drafts the `[ANNOUNCE]` email and opens the site-bump PR that complete the release lifecycle)* |
| `release-verify-rc` | `capability:triage` *(read-only RC pre-flight: verifies GPG signatures, checksums, RAT licence headers, NOTICE/LICENSE presence, prohibited binaries, and version-string consistency; emits a PASS/PASS-WITH-WARNINGS/FAIL report)* |
| `release-promote` | `capability:resolve` *(emits the backend-shaped promotion command set that moves a passed-vote RC to the release distribution area; never runs the command itself)* |
| `release-keys-sync` | `capability:resolve` *(drafts the KEYS file diff and paste-ready `svn` command sequence to add the RM's public key; validates key strength against the ASF floor)* |
| `release-rc-cut` | `capability:resolve` *(emits the paste-ready tag, build, sign, checksum, and staging command sequences for an RC)* |
| `release-vote-draft` | `capability:resolve` *(drafts the `[VOTE]` email and planning-issue comment that advance the release to the vote stage)* |
| `release-archive-sweep` | `capability:resolve` + `capability:triage` *(scans the dist area, classifies each release against the retention rule — triage — and proposes the command set to move past-retention releases to the archive — resolve)* |
| `security-cve-allocate` | `capability:resolve` |
| `security-issue-invalidate` | `capability:resolve` |
| `security-issue-deduplicate` | `capability:resolve` |
| `issue-deduplicate` | `capability:resolve` *(closes a duplicate general-issue and posts cross-reference comments; maintainer confirms before any action is applied)* |
| `issue-reassess` | `capability:reassess` |
| `issue-reproducer` | `capability:reassess` |
| `pr-management-stats` | `capability:stats` |
| `issue-reassess-stats` | `capability:stats` |
| `issue-backlog-stats` | `capability:stats` |
| `security-tracker-stats-dashboard` | `capability:stats` |
| `contributor-nomination` | `capability:stats` |
| `contributor-to-committer` | `capability:stats` |
| `contributor-activity-sweep` | `capability:stats` |
| `contributor-sentiment` | `capability:stats` *(measures contributor-sentiment signals — thread tone, time-to-first-reply, first-PR retention, reviewer load — and produces the gate report for experimental→stable advancement)* |
| `committer-onboarding` | `capability:resolve` + `capability:triage` *(post-vote onboarding close-out — resolve — after validating the vote result in pre-flight — triage)* |
| `list-skills` | `capability:stats` |
| `release-audit-report` | `capability:stats` *(assembles the per-release audit record from the planning issue, vote thread, artefact list, and announce archive URL)* |
| `setup-status` | `capability:stats` + `capability:platform` *(reports the adoption configuration — stats — and delegates reconfiguration to the setup skill)* |
| `setup` | `capability:platform` |
| `setup-isolated-setup-install` | `capability:platform` |
| `setup-isolated-setup-verify` | `capability:platform` |
| `setup-isolated-setup-update` | `capability:platform` |
| `setup-isolated-setup-doctor` | `capability:platform` + `capability:reassess` *(re-checks an installed sandbox against current spec — the phase is reassess on subject setup)* |
| `setup-override-upstream` | `capability:platform` |
| `setup-upstream-fix` | `capability:platform` |
| `write-skill` | `capability:authoring` |
| `optimize-skill` | `capability:authoring` |
| `skill-reconciler` | `capability:reconciliation` *(compares two near-duplicate skill copies and classifies every difference as ALLOWED, DRIFT, or SAFETY-BASELINE; proposes convergence; never writes either copy)* |

## Capability to tool map

Tools under [`tools/`](../tools/). A tool's capability is the interface
it provides; a tool may carry more than one value (separated by `+`) when
it implements multiple contracts (e.g. `tools/gmail` provides both
`mail-source` and `mail-create`).

| Tool | Capability / capabilities | Role |
|---|---|---|
| [`tools/agent-guard`](../tools/agent-guard/) | `substrate:action-guard` | Deterministic pre-execution guard dispatcher (harness-neutral core behind a Claude Code `PreToolUse` hook and an OpenCode `tool.execute.before` plugin): blocks `gh`/`git` commands that would ping maintainers, carry a `Co-Authored-By` trailer, mark-ready prematurely, leak security language publicly, or empty a PR via force-push. Extensible — skills contribute guards via `guards.d` |
| [`tools/agent-isolation`](../tools/agent-isolation/) | `substrate:sandbox` | Secure-agent sandbox helpers |
| [`tools/apache-projects`](../tools/apache-projects/) | `contract:project-metadata` | ASF project-metadata substrate (`apache/comdev` `apache-projects-mcp`); read-only `projects.apache.org/json` rosters / people / releases. Backs `contributor-nomination` and the security roster-resolution paths; tracked at `main`, not pinned |
| [`tools/asf-svn`](../tools/asf-svn/) | `contract:source-control` | ASF SVN tool adapter: source-control binding for `svn.apache.org` working copies (centralized model), `svn` CLI operation catalogue, `dist.apache.org` release-distribution helpers (stage/promote/prune), ASF committer/PMC authorization, and optional svnpubsub site publishing. The SVN counterpart to `tools/github/` for ASF projects. Also the `land` delegate for the `jira-patch` and `mail-patch` change-request backends (`svn patch` + `svn commit`) |
| [`tools/change-request`](../tools/change-request/) | `contract:change-request` | Adapter contract for the proposed-change review + merge gate (pull request / merge request / patch). Pure interface spec; no executable code — backends under `tools/github/` (PR), `tools/jira-patch/`, and `tools/mail-patch/` implement it. The seam that lets `pr-management-*` skills run on non-GitHub backends |
| [`tools/cve-org`](../tools/cve-org/) | `contract:cve-authority` | CVE.org services adapter: publishes records to CVE.org and reads back the resulting CVE state. Implements the `tools/cve-tool/` contract for the CVE.org-direct backend |
| [`tools/cve-tool`](../tools/cve-tool/) | `contract:cve-authority` | Adapter contract for CNA backends (Vulnogram, MITRE form, CVE.org direct, GHSA). Pure interface spec; no executable code — adapters under sibling `tools/cve-tool-*/` directories implement it. |
| [`tools/cve-tool-vulnogram`](../tools/cve-tool-vulnogram/) | `contract:cve-authority` | ASF Vulnogram CVE-allocation adapter. Implements the `tools/cve-tool/` contract. Previously named `tools/vulnogram/`. |
| [`tools/dashboard-generator`](../tools/dashboard-generator/) | `substrate:analytics` | Self-contained HTML dashboard generator |
| [`tools/dev`](../tools/dev/) | `substrate:framework-dev` | Framework dev-loop helpers |
| [`tools/egress-gateway`](../tools/egress-gateway/) | `substrate:sandbox` | Egress-allowlist forward proxy (proxy.py plugin); host-level egress chokepoint — defence-in-depth for RFC-AI-0003 §4.4 |
| [`tools/forwarder-relay`](../tools/forwarder-relay/) | `contract:report-relay` | Adapter contract for inbound-relay backends (ASF Security relay, huntr.com, HackerOne triagers). Pure interface spec; adapters declare detection + credit-extraction + reporter-addressing rules. |
| [`tools/bitbucket`](../tools/bitbucket/) | `contract:change-request` | Coverage: `partial-read-only`. Bitbucket Cloud and Bitbucket Data Center bridge foundation for repository metadata context, pull-request discovery/fetching, read-only commit fetching, read-only diff fetching, comments-only discussion fetching, and read-only status fetching. The `partial-read-only` qualifier means this tool implements named read-only contract operations but does not satisfy the complete contract and must not be counted as a complete/selectable backend. `contract:tracker` remains absent until Bitbucket issue operations or linked Jira handoff coverage exist. |
| [`tools/fossil`](../tools/fossil/) | `contract:tracker` + `contract:source-control` | Fossil SCM forge bridge: integrates local SQLite-backed ticket tracking, wiki, and forum reads with the version-control shim |
| [`tools/github`](../tools/github/) | `contract:tracker` + `contract:source-control` + `contract:change-request` | GitHub REST / GraphQL tracker substrate (called by every lifecycle phase) plus the Git source-control binding documented in [`source-control.md`](../tools/github/source-control.md) (runnable backend in [`tools/vcs`](../tools/vcs/)) and the pull-request review/merge gate (`change-request`; the ASF default backend, alongside `tools/jira-patch/` and `tools/mail-patch/` for SVN-first projects) |
| [`tools/github-body-field`](../tools/github-body-field/) | `contract:tracker` | Read or rewrite one `### Field` section of a GitHub issue body without bringing the body into agent context — substrate helper for the security-sync skills |
| [`tools/github-rollup`](../tools/github-rollup/) | `contract:tracker` | Append to (or create) the status-rollup comment on a GitHub issue without bringing the rollup body into agent context — substrate helper for every status-update-emitting skill |
| [`tools/gmail`](../tools/gmail/) | `contract:mail-source` + `contract:mail-create` + `contract:mail-archive` | Gmail API substrate — inbound report intake (`mail-source`), thread / archive reads (`mail-archive`), plus outbound courtesy-reply drafting (`mail-create`); read + draft only, never sends |
| [`tools/jira`](../tools/jira/) | `contract:tracker` | JIRA REST substrate (read-only today; write subcommands tracked in [#301](https://github.com/apache/magpie/issues/301)) |
| [`tools/jira-patch`](../tools/jira-patch/) | `contract:change-request` | JIRA-patch change-request backend: patches attached to JIRA issues as the proposal, reviewed via JIRA comments, landed via `contract:source-control` (`svn patch` + `svn commit`). Composes `tools/jira/` (REST) + `tools/asf-svn/` (land). Implements the `tools/change-request/` contract |
| [`tools/mail-archive`](../tools/mail-archive/) | `contract:mail-archive` | Adapter contract for public mail-archive backends (PonyMail, Hyperkitty, Discourse, Google Groups, GitHub Discussions). Pure interface spec. |
| [`tools/mail-patch`](../tools/mail-patch/) | `contract:change-request` | `[PATCH]`-mail change-request backend: a `[PATCH]` thread on `dev@` as the proposal, reviewed via drafted replies (`contract:mail-create`), read via `contract:mail-archive`, landed via `contract:source-control` (`svn patch` + `svn commit`). Implements the `tools/change-request/` contract |
| [`tools/mail-source`](../tools/mail-source/) | `contract:mail-source` | Mail-source backend abstraction (mbox / IMAP / Mailman 3) feeding a uniform inbound thread/message view to the intake pipeline |
| [`tools/maildir`](../tools/maildir/) | `contract:mail-source` + `contract:mail-create` | Local **Maildir** backend (Vendor: Maildir) — the offline, credential-free counterpart of `tools/gmail`. Implements `mail-create` by filing editable outbound drafts into a local Maildir for any mail client to send (never sends itself); its `mail-source` side is the local mbox/Maildir archive reader (`tools/mail-source/mbox`). The second, non-Google `mail-create` backend — closes the outbound-mail vendor-neutrality gap |
| [`tools/ponymail`](../tools/ponymail/) | `contract:mail-archive` + `contract:mail-source` | PonyMail public mail-archive substrate (ASF `lists.apache.org`); implements the `tools/mail-archive/` contract for archive reads and the `tools/mail-source/` contract for inbound list-traffic ingestion |
| [`tools/scan-format`](../tools/scan-format/) | `contract:scan-format` | Adapter contract for security-scanner report formats (ASVS reference); reads a scan's finding index + per-finding evidence for the `security-issue-import-from-scan` pipeline. |
| [`tools/permission-audit`](../tools/permission-audit/) | `substrate:sandbox` | Audit + atomically edit Claude Code `permissions.allow[]` entries; backs `/magpie-setup verify --apply-permission-audit` (check 8d) |
| [`tools/pr-management-stats`](../tools/pr-management-stats/) | `substrate:analytics` | PR-backlog analytics engine |
| [`tools/preflight-audit`](../tools/preflight-audit/) | `substrate:analytics` | Dry-run the bulk-mode pre-flight classifier; measure skip-rate before / after any rule edit in the security-issue-sync skill |
| [`tools/privacy-llm`](../tools/privacy-llm/) | `substrate:privacy` | Privacy-LLM PII-scrubbing gate |
| [`tools/probe-templates`](../tools/probe-templates/) | `substrate:sandbox` | Sandbox-doctor probe templates |
| [`tools/sandbox-lint`](../tools/sandbox-lint/) | `substrate:sandbox` | Sandbox settings linter |
| [`tools/security-tracker-stats-dashboard`](../tools/security-tracker-stats-dashboard/) | `substrate:analytics` | Security-tracker analytics engine |
| [`tools/spec-loop`](../tools/spec-loop/) | `substrate:framework-dev` | Spec-driven build loop runner (Ralph-style) for framework development |
| [`tools/skill-evals`](../tools/skill-evals/) | `substrate:framework-dev` | Eval harness for skills; framework-dev infrastructure whose run output is governance evidence |
| [`tools/skill-and-tool-validator`](../tools/skill-and-tool-validator/) | `substrate:framework-dev` | Skill-frontmatter and convention validator |
| [`tools/spec-inventory`](../tools/spec-inventory/) | `substrate:framework-dev` + `substrate:analytics` | Compact routing inventory for spec-loop prompts — summarizes specs, skills, and tool metadata so agents can choose relevant files before direct verification |
| [`tools/spec-status-index`](../tools/spec-status-index/) | `substrate:framework-dev` + `substrate:analytics` | Index of spec / RFC implementation status — framework-dev substrate that also doubles as a governance/stats view (`analytics`) |
| [`tools/vendor-neutrality-score`](../tools/vendor-neutrality-score/) | `substrate:framework-dev` + `substrate:analytics` | Deterministic vendor-neutrality score — reads each contract tool's `**Kind:**` / `**Vendor:**` metadata and scores per-contract + per-skill neutrality (`analytics`); backs the score block in [`docs/vendor-neutrality.md`](vendor-neutrality.md) |
| [`tools/spec-validator`](../tools/spec-validator/) | `substrate:framework-dev` | Spec-frontmatter and body-section validator — counterpart to `skill-and-tool-validator` for `tools/spec-loop/specs/` |
| [`tools/symlink-lint`](../tools/symlink-lint/) | `substrate:framework-dev` | Self-adoption symlink hygiene — rejects cyclic symlinks and misdirected skill relays (canonical/relay target-correctness) |
| [`tools/pilot-report-validator`](../tools/pilot-report-validator/) | `substrate:framework-dev` | Adopter pilot-report validator — required frontmatter keys, no unfilled placeholders, valid profile, and required body sections; counterpart to `spec-validator` for `docs/pilot-report-template.md` |
| [`tools/skill-reconciler-diff`](../tools/skill-reconciler-diff/) | `substrate:framework-dev` | Deterministic structural diff between two skill trees — parses frontmatter, section headings, step inventory, placeholders, support files, and safety-baseline clauses into a JSON diff object for the `skill-reconciler` skill |
| [`tools/vcs`](../tools/vcs/) | `contract:source-control` | Backend-dispatching implementation of the source-control (VCS) capability ([`tools/github/source-control.md`](../tools/github/source-control.md)); complete Git and Mercurial (Hg) backends, plus detected extension point for SVN (#602) |
| [`tools/sourcehut`](../tools/sourcehut/) | `contract:tracker` + `contract:source-control` + `contract:mail-archive` | SourceHut (sr.ht) forge bridge: todo.sr.ht, lists.sr.ht, builds.sr.ht, and git/hg repository reads |

A tool's capability is the **interface it provides**, not which skills
happen to consume it (RFC-AI-0005). `tools/github` provides the
`contract:tracker` interface; `tools/cve-tool-vulnogram` provides
`contract:cve-authority`; `tools/privacy-llm` is `substrate:privacy`.
Use a `contract:<name>` value when the tool implements a capability
contract under `tools/<contract>/`, and a `substrate:<name>` value for
framework substrate. A tool may carry more than one (rare —
`tools/gmail` is the only one today).

## MCP servers, classified by capability

Several tools wrap a [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) server as their concrete backend. An MCP server is **not** a
separate axis — it is classified by the capability its *wrapping tool*
provides; the MCP is just the transport, interchangeable with a CLI or
REST backend behind the same contract. A skill never names an MCP
server — it targets the capability, and the tool routes to whichever
backend the adopter wired in. The framework consumes four:

| MCP server | Tool prefix | Wrapped by | Capability provided | Organization |
|---|---|---|---|---|
| GitHub MCP | `mcp__github__*` | [`tools/github`](../tools/github/) | `contract:tracker` + `contract:source-control` + `contract:change-request` | — |
| Gmail MCP (claude.ai) | `mcp__claude_ai_Gmail__*` | [`tools/gmail`](../tools/gmail/) | `contract:mail-source` + `contract:mail-create` + `contract:mail-archive` | — |
| PonyMail MCP (`apache/comdev`) | `mcp__ponymail__*` | [`tools/ponymail`](../tools/ponymail/) | `contract:mail-archive` + `contract:mail-source` | ASF |
| apache-projects MCP (`apache/comdev`) | `mcp__apache-projects__*` | [`tools/apache-projects`](../tools/apache-projects/) | `contract:project-metadata` | ASF |

Each wrapping tool declares this relationship in its own README with an
`**MCP:** <server> (mcp__<prefix>__*)` marker (see
[`tools/AGENTS.md`](../tools/AGENTS.md)) — that per-tool marker is the
source of truth; this table mirrors it for a one-glance overview.

Non-MCP backends fulfil the same contracts: JIRA is reached over REST
and `gh` is the CLI fallback, both `contract:tracker`. See
[`docs/prerequisites.md`](prerequisites.md) for connection setup.

**MCP servers are installed for the user, not the project.** They are
registered at **user scope** (`claude mcp add … -s user`), so a single
registration serves every repository on the machine. Consequently they
are usable by **any** agent session — not only Magpie-adopting projects
or Magpie-related work. Magpie surfaces the registration command and
verifies it during setup, but the server itself is a plain,
project-agnostic MCP: once registered it is available to any agentic
session the same way a globally-installed CLI would be. Nothing about
using one ties a session to Magpie.

---

## The rule

When you create any of the following on this repository, declare the
capability:

### A GitHub issue

Apply at least one `family:*` AND one capability label — a skill
capability (`capability:*`) for skill work, a tool capability
(`contract:*` / `substrate:*`) for tool work. If the issue genuinely
spans capabilities, apply all that apply.

### A pull request

Same: `family:*` AND the matching capability. Match the capability the
change is *implementing*, not the file paths it happens to touch. A PR
that adjusts the validator config to support a new triage rule is
`capability:triage` (the change's purpose), not `substrate:framework-dev`
(the file it edited).

### A new tool under `tools/`

Declare the tool's capability in the **first paragraph of its README**
using the line:

```markdown
**Capability:** contract:NAME
```

…or `substrate:NAME` for framework substrate. If the tool serves more
than one, list them (`contract:a + substrate:b`). Pick the
`contract:<name>` that matches the capability contract the tool
implements, or the `substrate:<name>` kind that fits.

### A new skill under `.claude/skills/`

Declare the capability in the skill's frontmatter:

```yaml
---
name: my-new-skill
description: |
  ...
capability: capability:NAME
---
```

The [`write-skill`](../skills/write-skill/SKILL.md) skill
prompts for this on every new-skill scaffold.

### A new doc under `docs/`

Capability-specific docs (e.g. a guide for a single skill family)
should link to this page and name the capability in their first
paragraph. Cross-cutting docs (`MISSION.md`, top-level READMEs) need
no capability marker.

---

## Why this exists

The original `family:*` labels split issues by subject — useful for
"what part of the codebase is this?" but unable to answer "what kind
of thing is this?". The `capability:*` dimension fills that gap and
is orthogonal: a triage-rule change in PR management
(`family:pr-management` + `capability:triage`) and a triage-rule change
in security (`family:security` + `capability:triage`) become trivially
findable as a cohort even though they live in different families.

Capability is also a forcing function for skill design: if a new skill
doesn't fit any of the ten skill-capability buckets cleanly, that's a
signal worth inspecting before the skill ships.
