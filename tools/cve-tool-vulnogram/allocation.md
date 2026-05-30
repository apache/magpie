<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Vulnogram — CVE allocation](#vulnogram--cve-allocation)
  - [Allocation URL](#allocation-url)
  - [PMC-gated access](#pmc-gated-access)
  - [Form fields and where the skill sources them](#form-fields-and-where-the-skill-sources-them)
  - [After the CVE is allocated](#after-the-cve-is-allocated)
  - [Fatal mis-allocation — wrong product](#fatal-mis-allocation--wrong-product)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Vulnogram — CVE allocation

The Vulnogram-side mechanics of CVE allocation (step 6 of the generic
handling process in [`../../README.md`](../../README.md)). The generic
flow of *"walk the triager through an allocation, capture the ID,
wire it into the tracker"* lives in the
[`security-cve-allocate`](../../.claude/skills/security-cve-allocate/SKILL.md) skill;
this file documents the **Vulnogram-specific** parts that skill reads.

Per-project configuration (allocation URL, record URL template, org
ID) lives in
[`../../<project-config>/project.md`](../../<project-config>/project.md#cve-tooling).

## Allocation URL

```text
https://cveprocess.apache.org/allocatecve
```

Opens an ASF-OAuth-protected form. The CVE ID is minted immediately
on successful submission and written back onto Vulnogram's
`cveprocess.apache.org/cve5/<CVE-ID>` record page with the state
`DRAFT`.

## PMC-gated access

The submit button on the Vulnogram allocation form is **PMC-gated on
the server side**: the form loads for any ASF-authenticated user,
but submission is rejected unless the user is a PMC member of the
project the allocation is against. This is not something the skill
can work around — a non-PMC user who clicks *Allocate* sees the
button grey out.

**Practical consequence.** The `security-cve-allocate` skill asks up front
*"are you a PMC member?"*:

- **PMC** — recipe is self-service: click the URL, paste the title,
  fill the form, hit *Allocate*, paste the `CVE-YYYY-NNNNN` back.
- **Non-PMC** — recipe becomes a **relay message** the user posts as
  a comment on the tracker (`@`-mentioning a PMC member) or sends
  on the project's `security_list`. The PMC member reads the relay,
  clicks through, allocates, and posts the ID back. The original
  triager (or the PMC member) can then re-invoke `security-cve-allocate` with
  the CVE ID as an override to resume from the wire-back step.

Concrete PMC-member handles live in the project's roster file at
`<project-config>/release-trains.md`; the canonical live source is
the ASF project page,
`https://projects.apache.org/committee.html?<project>`.

## Form fields and where the skill sources them

| Vulnogram form field | Source in the tracker |
|---|---|
| **Title** | Tracker title, passed through the project's title-normalisation cascade in [`<project-config>/title-normalization.md`](<project-config>/title-normalization.md). The CNA container already scopes the title to the product, so any project prefix (`<vendor>: <product>:`) must be stripped before pasting. |
| **Product** | Derived from the tracker's scope label via the per-project scope → product mapping in [`<project-config>/scope-labels.md`](<project-config>/scope-labels.md). |
| **CWE** | Tracker body's *cwe* field (role-name — `<project-config>/project.md` declares the concrete GitHub heading for this project). `_No response_` → the allocator fills it at form time. |
| **Affected versions** | Tracker body's *affected-versions* field. |
| **Summary** | Tracker body's *public-summary* field. |
| **Reporter credits** | Tracker body's *reporter-credit* field. |

The `security-cve-allocate` skill renders this mapping as a numbered recipe
the user copy-pastes into the form in one pass.

## After the CVE is allocated

Once the PMC member has reported the `CVE-YYYY-NNNNN` back, the
`security-cve-allocate` skill wires it into the tracker in one coordinated
pass — the generic steps (populate the *cve-tool-link* body field,
add the `cve allocated` label, post a status-change comment,
regenerate the CVE JSON attachment, draft a reporter status update)
are tool-agnostic; the Vulnogram-specific output is:

- The *cve-tool-link* body field gets the concrete URL built from
  the project manifest's `cve_tool_record_url_template` —
  `https://cveprocess.apache.org/cve5/<CVE-ID>` for ASF projects.
- The regenerated CVE JSON attachment carries the allocated CVE ID
  inside a `CNA_private` envelope with `state: "DRAFT"`; the
  subsequent release-manager workflow (see [`record.md`](record.md))
  moves it through `REVIEW` → `PUBLIC`.

## Fatal mis-allocation — wrong product

Allocating a CVE against the wrong product within a multi-package
project family (e.g. against the project's umbrella package when
the fix actually lives in a satellite / plugin / subproject
package) is a multi-hour cleanup involving Vulnogram support and
the release manager. The `security-cve-allocate` skill's Step 1 blocker checks refuse to
proceed without a scope label precisely because of this — see the
skill file for the hard-check details.
