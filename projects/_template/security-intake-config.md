<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — security-intake capability-flag vocabulary](#todo-project-name--security-intake-capability-flag-vocabulary)
  - [Intake channel quick-reference](#intake-channel-quick-reference)
    - [ASF forwarder relay](#asf-forwarder-relay)
  - [CVE allocation model quick-reference](#cve-allocation-model-quick-reference)
    - [CVE allocation gate](#cve-allocation-gate)
  - [Disclosure governance](#disclosure-governance)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — security-intake capability-flag vocabulary

**This file enumerates the capability-flag vocabulary for the
security-intake and CVE-allocation skill families.** It is the
security-team counterpart to `committer-onboarding-config.md`'s
intake-model vocabulary and `release-management-config.md`'s backend-flag
model: an adopter declares the intake channel, forwarder relay behaviour,
CVE allocation tool, and disclosure governance that suit their community,
and the skills emit steps shaped for that model, without any skill-body edit.

The *core* intake flags (`security_inbox`, `cve_authority`, `forwarders`,
`governance`, `mail_provider`, `archive_system`) are declared in
[`project.md`](project.md) under the **Security workflow configuration**
block — that block carries full per-field `#` comments and is the
authoritative home for those values.  This file does two things:

1. **Names every allowed value** for the key intake and allocation flags so
   an adopter can scan one document instead of hunting project.md comments.
2. **Introduces new disclosure-governance flags** (`disclosure_governance`)
   that live here, not in project.md, mirroring how the committer-onboarding
   flags live in their own companion file.

New adopters: copy this file into your own
`<project-config>/security-intake-config.md` and replace every `TODO`.
The ASF defaults reproduce the Apache Airflow security-team workflow
unchanged; override only the fields that differ for your project.

Related scaffolds in the same adopter directory:

- [`project.md`](project.md) — core manifest with `security_inbox`,
  `cve_authority`, `forwarders`, `governance`, and `mail_provider` blocks.
- [`security-model.md`](security-model.md) — Security-Model URL + anchors
  used in canned responses and validity assessments.
- [`canned-responses.md`](canned-responses.md) — reporter-facing reply
  templates whose wording is shaped by the intake channel and acknowledgement
  model declared here.

---

## Intake channel quick-reference

These values live in `project.md → security_inbox.kind`. Listed here with
non-ASF paths made explicit.

```yaml
security_inbox:
  # Inbound channel reports land on.
  # ASF default: mailing-list (project security@ SMTP address).
  # ghsa-inbox: GitHub Security Advisories private reporting — the skill
  #   reads draft advisories from the GHSA API instead of Gmail/IMAP;
  #   set `mail_provider.primary` to null and drop the Gmail backend.
  # hackerone: A managed HackerOne program inbox; the platform handles
  #   initial triage routing and the skill reads the HackerOne JSON feed.
  # chat-channel: A private Slack/Discord/Matrix channel used as an intake
  #   queue (unusual; prefer a structured form for volume > ~10 reports/year).
  # intake-form: A web form that posts structured reports into a tracker or
  #   inbox directly; useful when the project is too small for a dedicated
  #   security address.
  # Consumed by: security-issue-import, security-issue-sync.
  kind: mailing-list  # mailing-list | ghsa-inbox | hackerone | chat-channel | intake-form
```

### ASF forwarder relay

When `kind: mailing-list`, the ASF security team may relay reports onto
the project's `security@` list. Set these in `project.md → forwarders`:

```yaml
forwarders:
  # List of forwarder/relay adapters. Each name must match an adapter
  # directory under tools/ that conforms to tools/forwarder-relay/README.md.
  # ASF default: [asf-security] — the ASF security team relays reports
  #   with a known preamble and credit line.
  # Non-ASF adopters with no foundation-level relay: set to [].
  # Adopters with a custom relay (e.g. an internal SOC): add the relay
  #   adapter name here and implement tools/<name>/ per the contract.
  # Consumed by: security-issue-import, security-issue-import-via-forwarder.
  enabled: [asf-security]  # [asf-security] | [] | [<custom-relay-name>]
```

---

## CVE allocation model quick-reference

These values live in `project.md → cve_authority.tool`. Listed here with
non-ASF paths made explicit.

```yaml
cve_authority:
  # CNA tool the project uses to allocate, edit, and publish CVE records.
  # ASF default: vulnogram (ASF-hosted Vulnogram instance at
  #   cveprocess.apache.org). The skills print the allocation URL and
  #   wait for the operator to paste the allocated ID back.
  # mitre-form: MITRE CVE services web form (for projects not covered by
  #   any CNA). The skill links the MITRE form and skips Vulnogram-specific
  #   steps.
  # cve-org-direct: CVE.org CVE-services API direct submission
  #   (for projects that are their own CNA). The skill uses
  #   tools/cve-org/ to POST the CVE 5.x record.
  # ghsa: GitHub CNA / GHSA auto-CVE-assignment — GitHub allocates the
  #   CVE ID from the GHSA advisory; the skill publishes the GHSA advisory
  #   instead of submitting to a CNA tool.
  # none: The project does not allocate CVEs (no CNA relationship).
  #   The skill skips all CVE-ID steps and emits an advisory-only path.
  # Consumed by: security-cve-allocate, security-issue-sync,
  #   generate-cve-json.
  tool: vulnogram  # vulnogram | mitre-form | cve-org-direct | ghsa | none
```

### CVE allocation gate

Who has authority to allocate a CVE on behalf of the project. Set in
`project.md → governance.cve_allocation_gate`:

```yaml
governance:
  # pmc-member: An ASF-style governance committee membership gate; the
  #   skill refuses to proceed for non-PMC users and reshapes the steps
  #   into a relay message the user forwards to an authorised member.
  # security-team-member: Any member of the security team may allocate;
  #   looser than pmc-member, appropriate for projects that separate
  #   security triage from PMC governance.
  # maintainer: Any committer may allocate (open model).
  # none: No formal gate; the skill proceeds for any caller.
  # ASF default: pmc-member.
  # Consumed by: security-cve-allocate, security-issue-sync.
  cve_allocation_gate: pmc-member  # pmc-member | security-team-member | maintainer | none
```

---

## Disclosure governance

These flags are **new vocabulary** introduced by this file; they do not
exist in `project.md`. Declare them here in
`<project-config>/security-intake-config.md`.

**Currently the security skills default to the ASF disclosure conventions
(90-day window, 14-day grace period, manual acknowledgement).** This
block establishes the flag vocabulary so that a non-ASF adopter can
declare their disclosure model here; the skills will read these flags in
a follow-on update to replace the hard-coded ASF defaults.

```yaml
disclosure_governance:
  # Standard coordinated vulnerability disclosure (CVD) window in
  # calendar days, measured from the date the report is first received
  # and a tracker issue is opened.
  # During this window the team prepares a fix, coordinates a release,
  # and drafts the advisory before any public disclosure.
  # ASF default: 90 (follows the ASF security process guidelines; aligns
  #   with Google Project Zero's 90-day industry norm).
  # Override when:
  #   45 — Linux Foundation / CNCF norm for projects with fast release
  #         cadences and automated deployment paths.
  #   60 — CERT/CC guidance for resource-constrained maintainer teams.
  #   120 — Large, complex codebases where a safe backport takes longer
  #         (e.g. long-lived LTS branches, many distributions to notify).
  # Consumed by: security-issue-sync (stale-window checks),
  #   security-issue-import (acknowledgement draft deadline).
  window_days: 90  # TODO: adjust for your project's CVD policy

  # Grace period in calendar days added to the window when a patch is
  # ready but not yet shipped in a public release.  The extra days give
  # downstream consumers (OS packagers, cloud distributors) time to
  # prepare before the advisory goes public.
  # ASF default: 14.
  # Override when:
  #   7  — high-cadence projects that publish container images or packages
  #         within hours of a tag.
  #   21–30 — projects that coordinate formal notifications with major
  #            Linux distributors (oss-security@openwall.com process).
  #   0  — the project has no downstream distributors to notify and prefers
  #         to publish immediately once the fix ships.
  # Consumed by: security-issue-sync (release-gated disclosure check).
  grace_period_days: 14  # TODO: adjust for your distribution footprint

  # How the project acknowledges receipt to the reporter after a tracker
  # issue is opened.
  # ASF default: manual — the triager drafts a personal reply on the
  #   inbound mailing-list thread; the skill prepares a draft, the human
  #   reviews and sends.
  # auto — the skill emits a standard acknowledgement template
  #   immediately on import with no human review before sending.
  #   Suitable for high-volume programmes (> ~50 reports/year) where
  #   response latency is more important than personalisation.
  # none — no acknowledgement is sent.  Only for projects whose public
  #   SECURITY.md explicitly states that reports are received silently.
  # Consumed by: security-issue-import (acknowledgement step).
  reporter_acknowledgement_model: manual  # manual | auto | none

  # Whether an embargo notification is sent to a pre-agreed list of
  # downstream consumers (distributors, packagers, cloud vendors) before
  # the public advisory.
  # ASF default: false (ASF projects post-announce on oss-security@
  #   and the advisory list simultaneously; no pre-embargo distributor list
  #   is maintained centrally).
  # true — the project maintains a distributor embargo list and the skill
  #   drafts individual notification emails at the end of the grace period,
  #   before the advisory is posted publicly.
  # Consumed by: security-issue-sync (pre-announcement step).
  pre_announce_distributors: false  # false | true
```

---

## Cross-references

- [`project.md`](project.md) — primary manifest; `security_inbox`,
  `cve_authority`, `forwarders`, `governance`, `mail_provider`, and
  `archive_system` blocks carry the full flag vocabulary with per-field
  comments.
- [`security-model.md`](security-model.md) — Security-Model URL, severity
  rating reference, and public security policy URL.
- [`canned-responses.md`](canned-responses.md) — reporter-facing reply
  templates shaped by the `reporter_acknowledgement_model` declared here.
- [`security-issue-import`](../../.claude/skills/magpie-security-issue-import/SKILL.md)
  — reads `security_inbox.kind`, `forwarders.enabled`, and the
  `disclosure_governance` block for the acknowledgement step.
- [`security-cve-allocate`](../../.claude/skills/magpie-security-cve-allocate/SKILL.md)
  — reads `cve_authority.tool` and `governance.cve_allocation_gate`.
- [`security-issue-sync`](../../.claude/skills/magpie-security-issue-sync/SKILL.md)
  — reads `disclosure_governance.window_days`, `grace_period_days`, and
  `pre_announce_distributors` for stale-window and pre-announcement checks.
- [`security-issue-import-via-forwarder`](../../.claude/skills/magpie-security-issue-import-via-forwarder/SKILL.md)
  — reads `forwarders.enabled` and the per-adapter config in `project.md`.
