<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — Security Model reference](#apache-magpie--security-model-reference)
  - [Authoritative URL](#authoritative-url)
  - [Known-useful anchors](#known-useful-anchors)
  - [Drafting rule](#drafting-rule)
  - [Public security policy](#public-security-policy)
  - [Severity-rating reference](#severity-rating-reference)
  - [Model preparation, verification, and update](#model-preparation-verification-and-update)
    - [Repositories in scope](#repositories-in-scope)
    - [Model revision date](#model-revision-date)
    - [Scanner threat-model summaries](#scanner-threat-model-summaries)
    - [Rubric](#rubric)
    - [Where substantive conversation goes](#where-substantive-conversation-goes)
    - [PR conventions](#pr-conventions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — Security Model reference

This file is the project-specific reference to the project's
**Security Model**, which the canned responses and validity
assessments cite as the authoritative answer to *"is this a
vulnerability in Apache Magpie?"*.

Project-agnostic drafting rules (tone, brevity, threading) live in
the repo-level [`AGENTS.md`](https://github.com/apache/magpie/blob/main/AGENTS.md). The *content*
the responses link to is what lives here.

## Authoritative URL

The [Apache Magpie threat model](https://github.com/apache/magpie/blob/main/docs/security/threat-model.md) is the authoritative source for what is and is not considered a security vulnerability in Apache Magpie.
It follows the Alpha-Omega rubric, sections 1.1 to 1.19.

Canned responses must link directly to the relevant chapter instead of paraphrasing it;
paraphrases drift over time and create a second source of truth that has to be maintained.

The model's own header (§1.1) records its status and triage policy.

## Known-useful anchors

Anchors canned responses commonly link to, all in `docs/security/threat-model.md`:

- `#12-scope`
- `#13-out-of-scope`
- `#16-configurations`
- `#17-inputs`
- `#19-dependencies`
- `#110-adversary-model`
- `#111-claimed-properties`
- `#112-disclaimed-properties`
- `#113-downstream-responsibilities`
- `#115-known-non-findings`
- `#117-dispositions`

## Drafting rule

When adding a new canned response, identify the matching chapter in
the Security Model first. If no chapter covers the case, that is a
signal the Security Model should be updated **upstream** (in the
project's source repository) rather than duplicated in
the canned responses, which live in the private tracker.

## Public security policy

The public policy reporters are expected to follow is [`SECURITY.md`](https://github.com/apache/magpie/blob/main/SECURITY.md).

## Severity-rating reference

The [ASF Severity Rating blog post](https://security.apache.org/blog/severityrating)
is the rubric. Reporter-supplied CVSS scores are
informational only — the ASF-level rule that governs this is in
the repo-level
[`AGENTS.md`](https://github.com/apache/magpie/blob/main/AGENTS.md#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them)
(it is not project-specific).

## Model preparation, verification, and update

Read by the three `security-model-*` skills — see
[`docs/security/security-model-preparation.md`](https://github.com/apache/magpie/blob/main/docs/security/security-model-preparation.md)
for what each field is used for. A skill that needs a missing value asks rather
than guessing.

### Repositories in scope

Every repository whose security posture this model covers, with its shape.
`in-repo` means the model file lives in that repository.

| Repository | Shape | Model location | Note for `AGENTS.md` |
|---|---|---|---|
| `apache/magpie` | `in-repo` | `docs/security/threat-model.md` | |

Each repository is verified independently — an `AGENTS.md` in one says
nothing about a sibling.

### Model revision date

`2026-11`. The update skill defaults its window to everything closed since this date.

### Scanner threat-model summaries

Copies of this model summarised for an automated scanner — written by
[`security-submit-to-oss-scan`](https://github.com/apache/magpie/blob/main/plugins/magpie-security/skills/submit-to-oss-scan/SKILL.md),
refreshed whenever `security-model-update` lands a model commit the copy
was not derived from. Record the model file's commit, not a date: two
amendments in one month must still be told apart. Leave the table empty when the project is enrolled in no scanner.

| Scanner | Copy location | Derived from model commit |
|---|---|---|

### Rubric

The section numbers the skills cite (§1.15 known non-findings, §1.17
dispositions) are coordinates into the Alpha-Omega threat-model
specification: <https://github.com/alpha-omega-security/threat-model>.
Magpie references it and keeps no local copy. Override this only if the
project measures its model against a different published rubric.

### Where substantive conversation goes

Model gaps, missing sections, and broken links are raised on `private@magpie.apache.org`.
Substantive findings never go to a public issue tracker; the reasoning
is in the deep doc.

### PR conventions

Used by the `model_pr.py` helper when it opens a discoverability or
model PR.

| Setting | Value |
|---|---|
| Branch prefix | `security-model` |
| Base branch | `main` |
| License header for created files | `spdx` |
| Reporting address for a created `SECURITY.md` | `security@apache.org` |
