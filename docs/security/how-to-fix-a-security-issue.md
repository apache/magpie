<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Fixing security issues](#fixing-security-issues)
  - [Process](#process)
  - [Best practices](#best-practices)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Fixing security issues

High-level overview of how the security team handles a vulnerability
report from inbound email through published CVE. This page is
project-agnostic; the concrete lists, repos, release trains, and
tooling for the adopting project live in
[`<project-config>/project.md`](<project-config>/project.md)
(adopters bootstrap from the
[`projects/_template/`](../../projects/_template/) scaffold).

The end-to-end 16-step lifecycle is in [`README.md`](../../README.md). This
page is the two-minute summary.

## Process

1. **Vulnerability identification.**
   The adopting project's community monitors the project's
   `<security-list>` (declared in
   `<project-config>/project.md → Mailing lists`) for inbound
   reports. Reports from elsewhere (GHSA, HackerOne, a foundation-
   wide security relay declared in
   `security_inbox.foundation_security_address`, or any other
   adapter declared in `forwarders.enabled`) are forwarded onto
   that list so the security team has a single inbox. (For the
   airflow-s adopter, the foundation-wide relay is
   `security@apache.org`.)

2. **Agentic Triage.**
   A rotating triager imports new reports into the private
   `<tracker>` repository (see the
   [`security-issue-import`](../../skills/security-issue-import/SKILL.md)
   skill), classifies each candidate, and drafts a
   receipt-of-confirmation reply to the reporter. The team then
   discusses CVE-worthiness in the issue comments and — once the
   report is assessed valid — applies a project-specific scope label
   (see `<project-config>/scope-labels.md`).

   For the rarer case where a security-relevant fix lands as a
   public PR on `<upstream>` without ever hitting `<security-list>`,
   the triager uses
   [`security-issue-import-from-pr`](../../skills/security-issue-import-from-pr/SKILL.md)
   instead. The skill creates the tracker directly with a scope
   label and the `Assessed` board column — the deliberate import
   implies the validity assessment has already happened informally,
   so the CVE-worthiness discussion is skipped and the tracker is
   ready for CVE allocation immediately.

   When the team's discussion lands a *consensus-invalid* decision,
   the triager applies that decision via the
   [`security-issue-invalidate`](../../skills/security-issue-invalidate/SKILL.md)
   skill: it adds the `invalid` label, posts a short closing
   comment, archives the project-board item, and — when the
   tracker has an inbound `<security-list>` thread — drafts a
   polite-but-firm reply to the reporter explaining the reasoning
   (mined verbatim from the tracker's discussion and combined with
   a fitting canned response from
   [`<project-config>/canned-responses.md`](<project-config>/canned-responses.md)).
   The draft is never sent — the triager reviews in Gmail before
   sending. The skill hard-stops if a CVE has already been
   allocated (a REJECT in the project's CVE tool — the adapter
   named in `cve_authority.tool` — is required first) or if the
   advisory has shipped (closing as invalid then is a public
   retraction that needs explicit team escalation).

3. **CVE allocation.**
   A governance-authorised member of the adopting project (per
   `governance.cve_allocation_gate` in
   `<project-config>/project.md`) allocates a CVE through the
   project's CVE tool (the adapter named in `cve_authority.tool`,
   with the allocation URL in `cve_authority.allocate_url`).
   Triagers who do not satisfy the gate use the
   [`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md) skill to
   produce a relay message for a gate-passing member to click
   through. (For the airflow-s adopter, the gate is PMC membership
   and the CVE tool is Vulnogram.)

4. **Remediation.**
   A security-team member writes the fix in the public `<upstream>`
   repository (see the
   [`security-issue-fix`](../../skills/security-issue-fix/SKILL.md)
   skill, which can draft the PR automatically). The public PR is
   scrubbed of CVE references, tracker-repo references, and any
   *"security fix"* signal — per the confidentiality rules in
   [`AGENTS.md`](../../AGENTS.md#confidentiality-of-the-tracker-repository).

5. **Release + advisory.**
   The release manager for the cut that carries the fix sends the
   public advisory to the project's users + announce lists, captures
   the archive URL (the page declared in
   `archive_system.advisory_publication_signal_url`), and promotes
   the CVE record from `publish-ready` to `public` in the project's
   CVE tool (the adapter named in `cve_authority.tool`; the
   generic state sequence is declared in `cve_authority.states`).

6. **Continuous improvement.**
   The security team encourages responsible vulnerability disclosure
   and continues to improve the project's security posture, security
   features, and handling process. The adopting project's security
   model — declared in
   [`<project-config>/security-model.md`](<project-config>/security-model.md)
   — is the authoritative reference for what counts as a vulnerability.

## Best practices

* **Avoid labelling low-severity fixes as "security fixes" in public
  commits.** When we implement low-severity security fixes —
  sometimes ones that are not even worthy of a CVE — we avoid
  describing them as security features in public commit messages,
  newsfragments, and release notes. This prevents automated scrapers
  from raising reports about issues they were not originally aware
  of. Such tools may themselves violate our security practices.
* **Keep the reporter informed at every status transition** — see
  the [*Keeping the reporter informed*](../security/roles.md#keeping-the-reporter-informed)
  section of `roles.md` for the full list of transitions and the
  drafting rules.
* **Confidentiality first.** Tracker URLs and `#NNN` identifiers
  are public-safe (they point at access-gated pages); tracker
  *contents* — comments, labels, rollup entries, body excerpts —
  must not appear on a public surface; and the *security framing*
  of a public PR (the words `CVE-`, *"vulnerability"*, *"security
  fix"*, *"advisory"*) stays embargoed until the advisory ships.
  See the
  [Confidentiality of the tracker repository](../../AGENTS.md#confidentiality-of-the-tracker-repository)
  section of `AGENTS.md` for the three-layer rule and the
  sharing-with-non-team-recipients pattern. The
  [threat model](threat-model.md) covers the adversaries (P1–P5) the
  rule defends against and the STRIDE rows for skill family D
  (public remediation).
