<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Security workflow skill family](#security-workflow-skill-family)
  - [Install & first runs](#install--first-runs)
    - [Before the first run](#before-the-first-run)
    - [Try these first](#try-these-first)
  - [Skills](#skills)
    - [Lifecycle skills](#lifecycle-skills)
    - [Security-model skills](#security-model-skills)
    - [Supporting tools](#supporting-tools)
  - [Deep documentation](#deep-documentation)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security workflow skill family

> **Scope.** Works on any project, ASF or not. The ASF intake
> path (`security@`, Vulnogram CVE flow) is the default profile; non-ASF
> adopters swap it for GitHub Security Advisories / a MITRE CNA through the
> adapter/config layer.

End-to-end automation for an ASF project's security-issue handling
process — from inbound report on the project's `security@` mailing
list through to a published CVE record on `cve.org`. Eleven skills
that compose into the canonical 16-step lifecycle, three that produce,
verify, and maintain the project's own security model, plus one
read-only supporting skill for tracker-stats dashboards (fifteen skills
total).

Why a framework skill family? The 16-step process exists across
the foundation; every project's security team runs essentially
the same workflow with project-specific scope labels, mailing-list
addresses, milestone formats, and canned-response wording. Lifting
the workflow into a project-agnostic framework lets each adopter
plug their specifics into [`<project-config>/`](../../projects/_template/)
and reuse the skills verbatim.

> [!TIP]
> **Why this family**
> - Every report that lands on security@ becomes a tracked issue, with a receipt drafted to the reporter
> - The whole lifecycle in one place — triage, CVE allocation, the fix PR that does not leak the embargo, and the advisory
> - Read-only until you confirm: no label flips, no closes, and no CVE allocated without you saying so

## Install & first runs

Install just this family — one plugin, 15 skills. The security-report lifecycle, from intake through CVE publication.

Once you have [added the marketplace](../setup/marketplace-install.md):

```text
/plugin install magpie-security@apache-magpie
```

New to Magpie? The [quick start](../quick-start.md) walks the whole path in
one place — install, the first `/magpie-setup` run, and a recording of it
happening — plus the other agents and the secure-isolation setup to run next.

### Before the first run

<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->

Every skill here resolves project-specific values from the adopter's
[`<project-config>/`](../../projects/_template/) directory.
[`/magpie-setup adopt`](../setup/team-adoption.md) scaffolds all of them from
templates; you fill in the `TODO` fields for the skills you use.

**Required.** Without these a skill would act on a guess, so it stops and
says which file is missing.

| File | What it carries | Read by |
|---|---|---|
| [`fix-workflow.md`](../../projects/_template/fix-workflow.md) | Fork / clone / toolchain specifics, backport-label policy, commit-trailer wording, PR scrubbing, private-PR fallback. | `issue-fix` |
| [`milestones.md`](../../projects/_template/milestones.md) | Milestone naming conventions + create-and-assign recipe. | `issue-sync` |
| [`project.md`](../../projects/_template/project.md) | Project manifest. Identity, repositories, mailing lists, tools enabled, CVE tooling, GitHub project-board + issue-template field declarations. The single file every skill reads to resolve project-scoped references. | `cve-allocate`, `issue-deduplicate`, `issue-fix`, `issue-import`, `issue-import-from-pr`, `issue-import-from-scan`, `issue-import-via-forwarder`, `issue-invalidate`, `issue-triage`, `model-verify`, `tracker-stats-dashboard` |
| [`scanner-products.md`](../../projects/_template/scanner-products.md) | Private scanner product names, and the finder-anonymisation rule applied before anything is quoted publicly. | `issue-sync` |
| [`scope-labels.md`](../../projects/_template/scope-labels.md) | Scope label → CVE product / `packageName` / collection-URL mapping. Exactly one scope label per tracker. | `issue-deduplicate`, `issue-import-from-md`, `issue-import-from-pr`, `issue-triage`, `tracker-stats-dashboard` |
| [`security-intake-config.md`](../../projects/_template/security-intake-config.md) | Capability-flag vocabulary for the intake path: how reports arrive, what counts as in scope, and what a receipt says. | `issue-import` |
| [`security-model.md`](../../projects/_template/security-model.md) | Authoritative URL for the project's Security Model + known-useful anchors + drafting rule. | `issue-triage`, `model-prepare`, `model-verify` |
| [`security-tracker-stats.md`](../../projects/_template/security-tracker-stats.md) | Which tracker fields and windows the stats dashboard reads, and what it publishes. | `tracker-stats-dashboard` |
| [`title-normalization.md`](../../projects/_template/title-normalization.md) | Regex cascade the `security-cve-allocate` skill applies to tracker titles before pasting them into the CVE-tool allocation form. | `cve-allocate` |

**Optional.** Each has a documented fallback; absent, the skill still runs.

| File | What it carries | Read by |
|---|---|---|
| [`canned-responses.md`](../../projects/_template/canned-responses.md) | Reusable reporter-facing reply templates. | `issue-import`, `issue-import-from-scan`, `issue-invalidate`, `issue-sync`, `issue-triage`, `model-update` |
| [`distributor-list.md`](../../projects/_template/distributor-list.md) | The embargo distributor list a pre-announcement goes to, and what it may contain. Absent, no pre-announcement is proposed. | `issue-sync` |
| [`privacy-llm.md`](../../projects/_template/privacy-llm.md) | Which model tier may see which class of content, for projects routing foundation-private information away from third-party models. | `issue-import` |
| [`release-trains.md`](../../projects/_template/release-trains.md) | Active release branches, release-manager attribution per cut, rotation rosters, security-team roster. | `cve-allocate`, `issue-fix`, `issue-import`, `issue-import-from-pr`, `issue-sync`, `issue-triage` |

<!-- END generated: skill-config -->

### Try these first

*Illustrative shapes, not real transcripts — your output will differ. Nothing
below sends, merges, or posts anything without you confirming it.*

**Pull new reports out of the mailbox.**

```text
/magpie-security:issue-import
```

![An issue-import run: two security@ threads with no tracker yet, each becoming a Needs-triage issue with a receipt drafted to the reporter, pending confirmation](../../assets/quickstart/families/security/issue-import.svg)

**Triage what came in.**

```text
/magpie-security:issue-triage
```

![An issue-triage run classifying four trackers as valid, defence-in-depth, info-only and a probable duplicate, with every disposition still a proposal](../../assets/quickstart/families/security/issue-triage.svg)

**Check the security model still matches reality.**

```text
/magpie-security:model-verify
```

![A model-verify run: two green checks that the threat model and the code agree, and one failure where the model still names a surface no route serves](../../assets/quickstart/families/security/model-verify.svg)

## Skills

### Lifecycle skills

| Skill | Purpose |
|---|---|
| [`security-issue-import`](../../skills/security-issue-import/SKILL.md) | Import new reports from `<security-list>` into `<tracker>`. |
| [`security-issue-import-from-pr`](../../skills/security-issue-import-from-pr/SKILL.md) | Open a tracker for a security-relevant fix opened as a public PR. |
| [`security-issue-import-from-md`](../../skills/security-issue-import-from-md/SKILL.md) | Bulk-import findings from a markdown report. |
| [`security-issue-import-from-scan`](../../skills/security-issue-import-from-scan/SKILL.md) | Import findings from a security scanner output (Trivy, Grype, etc.) into `<tracker>`. |
| [`security-issue-import-via-forwarder`](../../skills/security-issue-import-via-forwarder/SKILL.md) | Import reports relayed through the ASF security forwarder when no direct reporter contact exists. |
| [`security-issue-triage`](../../skills/security-issue-triage/SKILL.md) | Propose an initial-triage disposition (VALID / DEFENSE-IN-DEPTH / INFO-ONLY / INVALID / PROBABLE-DUP / FIX-ALREADY-PUBLIC) for each tracker still in `Needs triage`; opens a discussion comment, never flips the label. |
| [`security-issue-sync`](../../skills/security-issue-sync/SKILL.md) | Reconcile a tracker against its mail thread, fix PR, release train, and archives. |
| [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) | Allocate a CVE for a tracker (Vulnogram URL + paste-ready JSON). |
| [`security-issue-fix`](../../skills/security-issue-fix/SKILL.md) | Implement the fix as a public PR in `<upstream>`. |
| [`security-issue-deduplicate`](../../skills/security-issue-deduplicate/SKILL.md) | Merge two trackers describing the same root-cause vulnerability. |
| [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md) | Close a tracker as invalid with a polite-but-firm reporter reply. |

### Security-model skills

The lifecycle skills above route **one report**. These three maintain the
document they route it against — the project's security model — so that
routing has something to cite. See
[**`security-model-preparation.md`**](security-model-preparation.md) for
the lifecycle and the rationale.

| Skill | Purpose |
|---|---|
| [`security-model-prepare`](../../skills/security-model-prepare/SKILL.md) | Produce a first model for a project that has none, in draft-first mode, and land it with its discoverability chain as one PR per repository. |
| [`security-model-verify`](../../skills/security-model-verify/SKILL.md) | Pre-flight an existing model: can an agent mechanically reach it, and does it cover the minimum bar a triager depends on. Discoverability is the only hard gate. |
| [`security-model-update`](../../skills/security-model-update/SKILL.md) | Read the decision history back into the model — new known-non-finding entries and a model-gap list, regression-checked against past valid reports. |

The rubric these skills measure against is maintained externally by
Alpha-Omega (<https://github.com/alpha-omega-security/threat-model>) and
referenced by URL; Magpie keeps no local copy.

### Supporting tools

| Skill | Purpose |
|---|---|
| [`security-tracker-stats-dashboard`](../../skills/security-tracker-stats-dashboard/SKILL.md) | Generate a self-contained HTML dashboard of `<tracker>` repo statistics (lifecycle bands, opened-vs-untriaged backlog, mean time to triage / first response / fix). Read-only — never modifies tracker state. |

## Deep documentation

- [**`poc-handling-policy.md`**](poc-handling-policy.md) — what an
  agent may do with reporter-supplied proof-of-concept code: static
  review by default, isolated container only on explicit approval,
  never on the host.
- [**`security-model-preparation.md`**](security-model-preparation.md) —
  the produce / verify / update lifecycle for the project's own
  security model: the external Alpha-Omega rubric, the
  `AGENTS.md` → `SECURITY.md` discoverability chain and why it is the
  only hard gate, why substantive findings go to the private list
  rather than a public issue, the provenance tags that make a
  draft-first model safe, and the fence around the known-non-findings
  section.
- [**`process.md`**](process.md) — the 16-step lifecycle with
  Mermaid diagram + per-step description; the label lifecycle
  state diagram + label reference table. The authoritative
  process reference.
- [**`roles.md`**](roles.md) — who owns which steps (issue
  triager / remediation developer / release manager), the shared
  conventions every role observes (keeping the reporter informed,
  recording status transitions, confidentiality), and the
  role-by-role workflow walkthroughs.
- [**`fixing-security-issues.md`**](fixing-security-issues.md) —
  hands-on guide for a remediation developer picking up a
  CVE-allocated tracker and shipping the fix.
- [**`how-the-security-team-works.md`**](how-the-security-team-works.md) —
  how the team operates and how a new member lands: the triager
  rotation that runs the skills and delegates, tracker access, mail
  list subscription, expected reading, first triage shadow.
- [**`threat-model.md`**](threat-model.md) — release-blocking
  threat model for the security skill family: trust boundaries,
  adversary personas, STRIDE matrix per skill, mitigation cross-
  reference, residual risk, and the re-audit cadence.
- [**`forwarder-routing-policy.md`**](forwarder-routing-policy.md) —
  when a tracker has no direct reporter contact (ASF-relay,
  read-only GHSA, anonymous tip), the skills route reporter-facing
  communication through the forwarder. The policy defines when
  that mode applies, the milestone list (events that **do** get
  relayed), and the negative list (events that don't — including
  credit-confirmation questions and regular workflow status).

## Cross-references

- [Top-level README — Install](../../README.md#install) — 3-step bootstrap.
- [`docs/prerequisites.md`](../quick-start/prerequisites.md) — what a security
  triager / remediation developer / release manager needs
  installed before invoking any skill.
