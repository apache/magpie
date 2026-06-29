<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Labels and capabilities](#labels-and-capabilities)
  - [Label dimensions](#label-dimensions)
    - [1. `area:*` — subject](#1-area--subject)
    - [2. `capability:*` — what the tool does](#2-capability--what-the-tool-does)
    - [3. `kind:*` — change type (pre-existing)](#3-kind--change-type-pre-existing)
    - [4. `mode:*` — handling mode (pre-existing)](#4-mode--handling-mode-pre-existing)
    - [Standalone labels](#standalone-labels)
  - [Capability to skill map](#capability-to-skill-map)
  - [Capability to tool map](#capability-to-tool-map)
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
carry at least one **`area:*`** label and at least one
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

### 1. `area:*` — subject

What part of the framework does this touch?

| Label | Covers |
|---|---|
| `area:pr-management` | `pr-management-*` skills |
| `area:security` | `security-*` skills, `security-tracker-stats-dashboard` |
| `area:setup` | `setup-*` skills, framework adoption, agent-sandbox setup |
| `area:issue` | `issue-*` skills (`issue-triage`, `issue-fix-workflow`, `issue-reassess`, `issue-reassess-stats`, `issue-reproducer`, `issue-stale-sweep`, `issue-deduplicate`, `issue-backlog-stats`) |
| `area:tools` | Substrate tools under `tools/*` (CLI bridges, agent-runtime adapters, mail-source backends) |
| `area:ci` | `.github/` workflows, prek, validators |
| `area:docs` | `docs/`, `MISSION.md`, READMEs |

### 2. `capability:*` — what the tool does

Nine buckets. A tool or skill carries **one or more** `capability:*`
labels. Most map cleanly to a single bucket; dual-capability cases
are real and explicitly enumerated below. Issues and PRs follow the
same rule — apply every capability the change is implementing.

When a skill or tool spans multiple capabilities, list **all** of
them in its frontmatter / README. Do not pick a single "primary"
to be neat; that loses information the label system exists to
surface.

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
| `capability:setup` | Framework / agent / substrate infrastructure: install, verify, update, doctor, override-upstream, write-skill, optimize-skill, plus new tools under `tools/*`. |

The `capability:*` dimension is **orthogonal** to `area:*`. A single
query can answer "how is our triage stack doing across PR + issue +
security?" by filtering on `capability:triage` alone, without
enumerating per-area queries.

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
| `mode:A` | Mode A — triage |
| `mode:B` | Mode B — mentoring |
| `mode:C` | Mode C — agent-authored fix with human review |
| `mode:D` | Mode D — narrowly-scoped auto-merge (off until A/B/C run 2 quarters) |
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
| `security-issue-triage` | `capability:triage` |
| `ci-runner-audit` | `capability:triage` |
| `dependency-audit` | `capability:triage` |
| `workflow-security-audit` | `capability:triage` |
| `license-compliance-audit` | `capability:triage` |
| `flaky-test-triage` | `capability:triage` |
| `pr-management-quick-merge` | `capability:triage` + `capability:review` *(screens the ready-for-review queue for trivial, all-gates-green PRs — triage; submits the maintainer's approve on per-PR confirmation — review)* |
| `pr-management-code-review` | `capability:review` |
| `pairing-self-review` | `capability:review` |
| `pairing-multi-agent-review` | `capability:review` |
| `pr-management-mentor` | `capability:review` |
| `good-first-issue-author` | `capability:review` *(authors a newcomer-ready good first issue — contributor mentoring on the supply side)* |
| `mentoring-welcome` | `capability:review` *(drafts a first-contact orientation comment for first-time contributors on issues and PRs)* |
| `issue-fix-workflow` | `capability:fix` |
| `audit-finding-fix` | `capability:fix` |
| `security-issue-fix` | `capability:fix` + `capability:resolve` *(opens the PR that closes the tracker — both phases)* |
| `security-issue-import` | `capability:intake` |
| `security-issue-import-from-md` | `capability:intake` |
| `security-issue-import-from-pr` | `capability:intake` |
| `security-issue-import-via-forwarder` | `capability:intake` |
| `security-issue-import-from-scan` | `capability:intake` |
| `security-issue-sync` | `capability:intake` *(+ `capability:reconciliation` once [#337](https://github.com/apache/magpie/issues/337) lands the ASF-dashboard step)* |
| `setup-shared-config-sync` | `capability:intake` + `capability:setup` *(reconciles user-scope config to a sync repo; the act is intake, the subject is setup)* |
| `release-vote-tally` | `capability:triage` *(reads the vote thread / approval signal, classifies each reply as binding or non-binding, tallies the result, and drafts the `[RESULT] [VOTE]` email for RM review — triage over the vote-thread queue)* |
| `release-prepare` | `capability:resolve` *(drafts the planning issue, prep PR, and post-release bump PR that open the release lifecycle)* |
| `release-announce-draft` | `capability:resolve` *(drafts the `[ANNOUNCE]` email and opens the site-bump PR that complete the release lifecycle)* |
| `release-verify-rc` | `capability:triage` *(read-only RC pre-flight: verifies GPG signatures, checksums, RAT licence headers, NOTICE/LICENSE presence, prohibited binaries, and version-string consistency; emits a PASS/PASS-WITH-WARNINGS/FAIL report)* |
| `release-promote` | `capability:resolve` *(emits the backend-shaped promotion command set that moves a passed-vote RC to the release distribution area; never runs the command itself)* |
| `release-keys-sync` | `capability:resolve` *(drafts the KEYS file diff and paste-ready `svn` command sequence to add the RM's public key; validates key strength against the ASF floor)* |
| `release-rc-cut` | `capability:resolve` *(emits the paste-ready tag, build, sign, checksum, and staging command sequences for an RC)* |
| `release-vote-draft` | `capability:resolve` *(drafts the `[VOTE]` email and planning-issue comment that advance the release to the vote stage)* |
| `release-archive-sweep` | `capability:resolve` *(scans the dist area and proposes the command set to move past-retention releases to the archive)* |
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
| `committer-onboarding` | `capability:stats` |
| `list-skills` | `capability:stats` |
| `release-audit-report` | `capability:stats` *(assembles the per-release audit record from the planning issue, vote thread, artefact list, and announce archive URL)* |
| `setup-status` | `capability:stats` + `capability:setup` *(reports the adoption configuration — stats — and delegates reconfiguration to the setup skill)* |
| `setup` | `capability:setup` |
| `setup-isolated-setup-install` | `capability:setup` |
| `setup-isolated-setup-verify` | `capability:setup` |
| `setup-isolated-setup-update` | `capability:setup` |
| `setup-isolated-setup-doctor` | `capability:setup` + `capability:reassess` *(re-checks an installed sandbox against current spec — the phase is reassess on subject setup)* |
| `setup-override-upstream` | `capability:setup` |
| `write-skill` | `capability:setup` |
| `optimize-skill` | `capability:setup` |

## Capability to tool map

Tools under [`tools/`](../tools/). Tools with two values (separated by
`+`) carry both labels — the dual role is explained in each row.

| Tool | Capability / capabilities | Role |
|---|---|---|
| [`tools/agent-guard`](../tools/agent-guard/) | `capability:setup` | Deterministic `PreToolUse` guard dispatcher: blocks `gh`/`git` commands that would ping maintainers, carry a `Co-Authored-By` trailer, mark-ready prematurely, leak security language publicly, or empty a PR via force-push. Extensible — skills contribute guards via `guards.d` |
| [`tools/agent-isolation`](../tools/agent-isolation/) | `capability:setup` | Secure-agent sandbox helpers |
| [`tools/apache-projects`](../tools/apache-projects/) | `capability:stats` + `capability:intake` | ASF project-metadata substrate (`apache/comdev` `apache-projects-mcp`); read-only `projects.apache.org/json` rosters / people / releases. Backs `contributor-nomination` and the security roster-resolution paths; tracked at `main`, not pinned |
| [`tools/cve-org`](../tools/cve-org/) | `capability:resolve` + `capability:intake` | Publishes to CVE.org *(resolve)* and records the resulting CVE state back into the tracker *(intake)* |
| [`tools/cve-tool`](../tools/cve-tool/) | `capability:setup` | Adapter contract for CNA backends (Vulnogram, MITRE form, CVE.org direct, GHSA). Pure interface spec; no executable code — adapters under sibling `tools/cve-tool-*/` directories implement it. |
| [`tools/cve-tool-vulnogram`](../tools/cve-tool-vulnogram/) | `capability:resolve` | ASF Vulnogram CVE-allocation adapter. Implements the `tools/cve-tool/` contract. Previously named `tools/vulnogram/`. |
| [`tools/dashboard-generator`](../tools/dashboard-generator/) | `capability:stats` | Self-contained HTML dashboard generator |
| [`tools/dev`](../tools/dev/) | `capability:setup` | Framework dev-loop helpers |
| [`tools/egress-gateway`](../tools/egress-gateway/) | `capability:setup` | Egress-allowlist forward proxy (proxy.py plugin); host-level egress chokepoint — defence-in-depth for RFC-AI-0003 §4.4 |
| [`tools/forwarder-relay`](../tools/forwarder-relay/) | `capability:setup` | Adapter contract for inbound-relay backends (ASF Security relay, huntr.com, HackerOne triagers). Pure interface spec; adapters declare detection + credit-extraction + reporter-addressing rules. |
| [`tools/github`](../tools/github/) | `capability:setup` | GitHub REST / GraphQL substrate (called by every lifecycle phase — pure substrate, no single phase) |
| [`tools/github-body-field`](../tools/github-body-field/) | `capability:setup` | Read or rewrite one `### Field` section of a GitHub issue body without bringing the body into agent context — substrate helper for the security-sync skills |
| [`tools/github-rollup`](../tools/github-rollup/) | `capability:setup` | Append to (or create) the status-rollup comment on a GitHub issue without bringing the rollup body into agent context — substrate helper for every status-update-emitting skill |
| [`tools/gmail`](../tools/gmail/) | `capability:setup` | Gmail API substrate |
| [`tools/jira`](../tools/jira/) | `capability:setup` | JIRA REST substrate (read-only today; write subcommands tracked in [#301](https://github.com/apache/magpie/issues/301)) |
| [`tools/mail-archive`](../tools/mail-archive/) | `capability:setup` | Adapter contract for public mail-archive backends (PonyMail, Hyperkitty, Discourse, Google Groups, GitHub Discussions). Pure interface spec. |
| [`tools/mail-source`](../tools/mail-source/) | `capability:setup` + `capability:intake` | Mail-source backend abstraction (mbox / IMAP / Mailman 3); the abstraction is setup, every concrete read is part of the intake pipeline |
| [`tools/ponymail`](../tools/ponymail/) | `capability:setup` + `capability:intake` | PonyMail archive substrate; same dual role as `mail-source` — substrate plus an intake-pipeline component |
| [`tools/scan-format`](../tools/scan-format/) | `capability:intake` | Adapter contract for security-scanner report formats (ASVS reference); reads a scan's finding index + per-finding evidence for the `security-issue-import-from-scan` pipeline. |
| [`tools/permission-audit`](../tools/permission-audit/) | `capability:setup` | Audit + atomically edit Claude Code `permissions.allow[]` entries; backs `/magpie-setup verify --apply-permission-audit` (check 8d) |
| [`tools/pr-management-stats`](../tools/pr-management-stats/) | `capability:stats` | PR-backlog analytics engine |
| [`tools/preflight-audit`](../tools/preflight-audit/) | `capability:stats` | Dry-run the bulk-mode pre-flight classifier; measure skip-rate before / after any rule edit in the security-issue-sync skill |
| [`tools/privacy-llm`](../tools/privacy-llm/) | `capability:setup` | Privacy-LLM PII-scrubbing gate |
| [`tools/probe-templates`](../tools/probe-templates/) | `capability:setup` | Sandbox-doctor probe templates |
| [`tools/sandbox-lint`](../tools/sandbox-lint/) | `capability:setup` | Sandbox settings linter |
| [`tools/security-tracker-stats-dashboard`](../tools/security-tracker-stats-dashboard/) | `capability:stats` | Security-tracker analytics engine |
| [`tools/spec-loop`](../tools/spec-loop/) | `capability:setup` | Spec-driven build loop runner (Ralph-style) for framework development |
| [`tools/skill-evals`](../tools/skill-evals/) | `capability:setup` + `capability:stats` | Eval harness for skills; the harness is setup infrastructure, the run output is governance evidence |
| [`tools/skill-and-tool-validator`](../tools/skill-and-tool-validator/) | `capability:setup` | Skill-frontmatter and convention validator |
| [`tools/spec-status-index`](../tools/spec-status-index/) | `capability:setup` + `capability:stats` | Index of spec / RFC implementation status — substrate that also doubles as a governance/stats view |
| [`tools/spec-validator`](../tools/spec-validator/) | `capability:setup` | Spec-frontmatter and body-section validator — counterpart to `skill-and-tool-validator` for `tools/spec-loop/specs/` |
| [`tools/vcs`](../tools/vcs/) | `capability:setup` | Backend-dispatching implementation of the source-control (VCS) capability ([`tools/github/source-control.md`](../tools/github/source-control.md)); complete Git backend plus detected extension points for non-Git VCS bridges (#601 Hg, #602 SVN) |

A tool's capabilities are determined by its **use-case lifecycle
phases**, not by which skills happen to consume it. `tools/github` is
called by every triage / intake / fix / resolve skill but is tagged
only `capability:setup` because it doesn't encode any one lifecycle
phase — it is pure substrate. `tools/cve-org`, by contrast, exists
specifically to *do* CVE publication and to record that result; both
the resolve action and the intake of state into the tracker are
first-class jobs of the tool, so it carries both labels.

When a tool grows to serve a new lifecycle phase as a first-class
feature (rather than as generic substrate that other skills happen
to compose), add the new `capability:*` label to its README and to
the table above.

---

## The rule

When you create any of the following on this repository, declare the
capability:

### A GitHub issue

Apply at least one `area:*` AND one `capability:*` label. If the issue
genuinely spans capabilities, apply both — for example,
[#337](https://github.com/apache/magpie/issues/337) carries
both `capability:reconciliation` and `capability:setup` because it
covers a new substrate tool *and* a new sync-flow integration.

### A pull request

Same: `area:*` AND `capability:*`. Match the capability the change is
*implementing*, not the file paths it happens to touch. A PR that
adjusts the validator config to support a new triage rule is
`capability:triage` (the change's purpose), not `capability:setup`
(the file it edited).

### A new tool under `tools/`

Declare the tool's capability in the **first paragraph of its README**
using the line:

```markdown
**Capability:** capability:NAME
```

If the tool serves more than one capability, list both. Substrate
bridges (`tools/github`, `tools/gmail`, …) default to
`capability:setup` unless they encode a specific lifecycle capability.

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

The original `area:*` labels split issues by subject — useful for
"what part of the codebase is this?" but unable to answer "what kind
of thing is this?". The `capability:*` dimension fills that gap and
is orthogonal: a triage-rule change in PR management
(`area:pr-management` + `capability:triage`) and a triage-rule change
in security (`area:security` + `capability:triage`) become trivially
findable as a cohort even though they live in different families.

Capability is also a forcing function for skill design: if a new skill
doesn't fit any of the nine buckets cleanly, that's a signal worth
inspecting before the skill ships.
