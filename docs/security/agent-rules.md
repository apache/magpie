<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Security-tracker rules for agents](#security-tracker-rules-for-agents)
  - [Other ASF projects — never name or describe their vulnerabilities](#other-asf-projects--never-name-or-describe-their-vulnerabilities)
  - [Privacy-LLM — what data goes through which model](#privacy-llm--what-data-goes-through-which-model)
  - [Reporter-supplied CVSS scores are informational only — never propagate them](#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them)
  - [CVE references must never point at non-public mailing-list threads](#cve-references-must-never-point-at-non-public-mailing-list-threads)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Security-tracker rules for agents

Rules an agent follows while handling security reports: triaging, importing, syncing or fixing one, proposing tracker field values, building a CVE record, or editing a security skill.
[`AGENTS.md`](../../AGENTS.md#security-tracker-work) sends agents here before that work; its rules on external content and tracker confidentiality apply as well.

## Other ASF projects — never name or describe their vulnerabilities

While triaging a report, you may learn about vulnerabilities in **other ASF projects** through the channels that surface our own reports:
a reporter's thread mentioning a similar issue filed against another project, a cross-project digest on `<foundation-security-list>`, a Gmail search that returns other projects' threads, or your own correlation of a reporter's prior disclosures.
**None of that content may appear in the tracker.** Specifically, these surfaces must not name, reference, describe, or hint at another ASF project's vulnerability:

- **Tracker issue bodies**, rollup comment entries, status comments,
  labels, milestone descriptions, per-field values (*Short public
  summary for publish*, *Reporter credited as* notes, *Security
  mailing list thread*, etc.).
- **The CVE JSON attachment** and every other artefact the
  `generate-cve-json` tool emits — the `descriptions[]`, `credits[]`,
  `references[]`, and `cpeApplicability[]` fields are all
  world-readable once the record reaches PUBLIC.
- **Public `<upstream>` PR descriptions and commit messages** (see
  the main Confidentiality rule above — this subsection extends it
  to cover other projects too).
- **Canned responses** and any text that ends up in a reply to the
  reporter or on a public list.

This applies **even when**:

- the same reporter discovered the same pattern in multiple ASF
  projects and said so openly on `<security-list>`;
- the cross-project correlation would be informative for our own
  triage (e.g. *"their fix used approach X, we should consider the
  same"*);
- the other project's report is already public — a published CVE
  does not re-authorise discussion of the private report that
  preceded it, nor of any other report we happen to know about
  from that project's team;
- the reporter themselves linked to the other project's advisory in
  their mail.

**Why:** every ASF project runs its own CNA process, so content about another project's vulnerability is that project's private information:
copying it into our tracker effectively re-publishes it, and learning something via a shared channel (`security@apache.org`, a cross-project Gmail thread) grants no licence to broadcast it beyond the conversation it arrived in.

**What to do instead.** Keep cross-project observations in the
channel they arrived on:

- Reporter mentioned another project on the `<security-list>` thread
  → discuss it on that same thread if it helps triage; do not copy
  into the tracker.
- Observation is load-bearing for our own fix or advisory
  (e.g. the other project's fix shape informs ours) → summarise it
  **without naming the project**. *"The reporter has filed similar
  reports with other ASF projects"* is allowed and sometimes
  useful; *"the reporter has filed the same traversal pattern
  against Superset and Allura"* is not. *"A sibling ASF project
  landed a comparable fix"* is allowed; *"Tomcat landed the
  equivalent fix in 11.0.3"* is not.
- Cross-project triage belongs on `<foundation-security-list>` or in a
  direct mail to that project's security team, not in our tracker.

**Self-check before posting, committing, or drafting.** Grep the
text for the names of known ASF projects — a non-exhaustive but
high-signal list: `Superset`, `Allura`, `Tomcat`, `Kafka`, `Spark`,
`Cassandra`, `Hadoop`, `Hive`, `HTTPD`, `Struts`, `Solr`,
`Zookeeper`, `Beam`, `Flink`, `NiFi`, `Pulsar`, `CloudStack`,
`OFBiz`, `Commons`, `Lucene`, `Camel`, `Druid`, `ActiveMQ`,
`Guacamole`, `Shiro`, `CXF`, `Iceberg` — and for the generic
phrases *"also reported against"*, *"cross-project"*, *"other
Apache projects"*, *"sister project"*, *"the same finder also"*,
*"similar to CVE-<year>-<number>"* (when that CVE belongs to
another project). If a hit lands in any tracker-destined surface,
remove it or rewrite it in the de-identified form above. When in
doubt, leave it out — the cost of omitting useful context is
low, the cost of leaking another project's private information is
not.

## Privacy-LLM — what data goes through which model

The confidentiality rules above govern *human-visible* surfaces; these govern *machine-routed* ones (the LLM context the agent operates in, any LLM API call a skill makes, any delegated-summarisation hop), and both apply.
The contract is enforced via [`tools/privacy-llm/`](../../tools/privacy-llm/tool.md) and configured per adopter in `<project-config>/privacy-llm.md` (template at [`projects/_template/privacy-llm.md`](../../plugins/magpie-setup/templates/privacy-llm.md)); setup recipes for the supported variants are in [`docs/setup/privacy-llm.md`](../setup/privacy-llm.md).

Three rules every skill follows:

**Third-party PII in `<security-list>` reports gets redacted —
the reporter's own identity does not.** The reporter is operationally
known to the team (replied to, credited in the CVE, referenced across the
tracker discussion), so their name / email / phone flow through context
as-is. **What gets redacted** is PII the reporter discloses about *other
people* — collaborators, victims, named individuals in the body —
replaced with hash-prefixed identifiers (`N-a3f9d2`, `E-b8c247`, …).
**Exception:** someone already a `<tracker>` collaborator (resolved via
`gh api repos/<tracker>/collaborators`) is **not** redacted. The
identifier↔value mapping lives at
`~/.config/apache-magpie/pii-mapping.json` (per the home-dir credentials
rule in [Local setup](../../AGENTS.md#local-setup)), is never sent to any LLM, and is
revealed only at the outbound boundary. Contract:
[`tools/privacy-llm/pii.md`](../../tools/privacy-llm/pii.md).

**`<private-list>` content never reaches a non-approved LLM.**
PMC-private foundation list content (the `<private-list>` and any other
PMC-private list the team reads) is wholly private — body and PII alike.
Skills that may read it run a Step 0 pre-flight gate that **stops the
skill if any LLM in the active stack is not in the approved-model
registry**. The default-approved set is Claude Code itself, anything at
`*.apache.org`, local-only inference (Ollama / vLLM on `127.0.0.1`), and
air-gapped on-prem endpoints; everything else (AWS Bedrock, direct
Anthropic API, Vertex, OpenAI, …) is opt-in, declared explicitly in
`<project-config>/privacy-llm.md` with a data-residency contract link and
a PMC-member approval line. Contract:
[`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md).

**Adding a new LLM hop is a deliberate act, not an emergent one.** The
gate is conservative — a single unapproved entry stops the skill — so a
skill cannot silently grow a second LLM dependency without the adopter's
security team approving it in `<project-config>/privacy-llm.md`. When a
skill needs to delegate to another LLM (a summariser, classifier, or
outbound moderation step), the adopter wires the endpoint per
[`docs/setup/privacy-llm.md`](../setup/privacy-llm.md) **before** the
skill that uses it runs.

**Status — provisional pending ASF Legal.** The default-approved list above is the framework maintainer's working position, not yet ratified by ASF Legal Affairs;
until an authoritative list lands, [`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md) is the framework's source-of-truth and the rationale-of-record.

## Reporter-supplied CVSS scores are informational only — never propagate them

Reporters frequently attach a CVSS vector or numeric score to their report, either
inline in the mail thread, in a private GitHub Security Advisory draft, or in the
body of the tracking issue. **Treat every reporter-supplied CVSS score as
informational background only.** Do not:

- copy the reporter's score into the tracking-issue `Severity` field;
- copy it into the CVE tool, the generated CVE JSON, the public advisory, or any
  status update to the reporter;
- repeat it in an email reply, even to confirm it.

The adopting project's security team rates every accepted vulnerability independently, as part of the CVE-allocation step.
ASF projects do not use CVSS scores: they rate severity on the [ASF severity rating](https://security.apache.org/blog/severityrating) scale, as [`docs/security/process.md`](process.md) describes; other projects use the rubric named in `<project-config>/security-model.md`.
The independent rating is the **only** severity that ends up in the CVE record and the public advisory.

Practical consequences:

- When a sync skill or any agent reads a reporter's score from the mail thread,
  a GHSA record, or an issue body, it must surface it in the *observed state*
  only ("*reporter estimated CVSS 4.0 = 7.2*"), never as a proposed value for
  the `Severity` field.
- Proposed field updates for `Severity` must either leave the field as
  `_No response_` until the team rates it independently, or come from a
  security-team member who has already rated it in-thread or in a
  comment on the tracking issue — not from the reporter.
- Draft replies to the reporter must not echo their score. If the reporter
  asks us to confirm their score, respond that we rate every CVE
  independently during the CVE-allocation step and will share the final
  severity when the public advisory is sent.

This rule applies equally to CVSS 3.x and 4.0 vectors, to qualitative labels
(*"Low"*, *"High"*, *"Critical"*), and to any self-assigned CWE the reporter
attaches alongside.

## CVE references must never point at non-public mailing-list threads

When populating the CVE record's `references[]` (via `generate-cve-json`
or directly in the CVE-tool UI), **never tag a URL as `vendor-advisory`
if it points to a non-publicly archived list.** For ASF projects the
public-archived lists (users / dev / announce / commits on
`lists.apache.org`) are valid `vendor-advisory` targets; the private
`<security-list>` and `<private-list>` produce `lists.apache.org/thread/<id>`
URLs that look identical but 404 for everyone outside the team and must
**never** appear in the public record. See
[`<project-config>/project.md → Mailing lists`](<project-config>/project.md#mailing-lists)
for the public / private marking.

The issue template keeps the two apart: the *"Security mailing list thread"* field is the team's internal back-reference (expected to 404 externally; **do not scrub it during sync**), and the *"Public advisory URL"* field holds the public users-list archive URL that becomes the `vendor-advisory` reference once the advisory ships.
`generate-cve-json` enforces the split ([mechanics](../../tools/cve-tool-vulnogram/)); a `vendor-advisory` link that 404s is a broken CVE record.
