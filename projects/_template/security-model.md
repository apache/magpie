<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — Security Model reference](#todo-project-name--security-model-reference)
  - [Authoritative URL](#authoritative-url)
  - [Known-useful anchors](#known-useful-anchors)
  - [Drafting rule](#drafting-rule)
  - [Public security policy](#public-security-policy)
  - [Severity-rating reference](#severity-rating-reference)
  - [Model preparation, verification, and update](#model-preparation-verification-and-update)
    - [Repositories in scope](#repositories-in-scope)
    - [Model revision date](#model-revision-date)
    - [Rubric](#rubric)
    - [Where substantive conversation goes](#where-substantive-conversation-goes)
    - [PR conventions](#pr-conventions)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — Security Model reference

This file is the project-specific reference to the project's
**Security Model**, which the canned responses and validity
assessments cite as the authoritative answer to *"is this a
vulnerability in `<Project>`?"*.

Project-agnostic drafting rules (tone, brevity, threading) live in
the repo-level [`../../AGENTS.md`](../../AGENTS.md). The *content*
the responses link to is what lives here.

## Authoritative URL

TODO: the URL to the project's public Security Model. Canned
responses must link directly to the relevant chapter instead of
paraphrasing it; paraphrases drift over time and create a second
source of truth that has to be maintained.

Example shape:

> The [`<Project>` Security Model](TODO: URL) is the authoritative
> source for what is and is not considered a security vulnerability
> in `<Project>`.

## Known-useful anchors

TODO: list anchor fragments that canned responses commonly link to.
One anchor per bullet, slug-form.

Example shape:

- `#capabilities-of-X`
- `#Y-executing-arbitrary-code`

## Drafting rule

When adding a new canned response, identify the matching chapter in
the Security Model first. If no chapter covers the case, that is a
signal the Security Model should be updated **upstream** (in the
project's source repository) rather than duplicated in
[`canned-responses.md`](canned-responses.md).

## Public security policy

TODO: the project's public-facing `SECURITY.md` or equivalent URL
(what reporters are expected to follow).

## Severity-rating reference

TODO: for ASF projects, the
[ASF Severity Rating blog post](https://security.apache.org/blog/severityrating)
is the rubric. For other projects, point at whatever rubric the
team uses when scoring severity. Reporter-supplied CVSS scores are
informational only — the ASF-level rule that governs this is in
the repo-level
[`../../AGENTS.md`](../../AGENTS.md#reporter-supplied-cvss-scores-are-informational-only--never-propagate-them)
(it is not project-specific).

## Model preparation, verification, and update

Read by the three `security-model-*` skills — see
[`docs/security/security-model-preparation.md`](../../docs/security/security-model-preparation.md)
for what each field is used for. Leave a row `TODO` until the project
actually has that piece; a skill that needs a missing value asks rather
than guessing.

### Repositories in scope

TODO: every repository whose security posture this model covers, with
its shape. `in-repo` means the model file lives in that repository;
`pointer` means the repository wires its discoverability chain to an
umbrella model held elsewhere (the normal shape for build tooling,
language ports, and other satellites).

| Repository | Shape | Model location | Note for `AGENTS.md` |
|---|---|---|---|
| TODO: `<owner>/<name>` | `in-repo` | `THREAT_MODEL.md` | |
| TODO: `<owner>/<name>-tools` | `pointer` | TODO: umbrella model URL | TODO: e.g. "Build-time tooling for `<PROJECT>`." |

Each repository is verified independently — an `AGENTS.md` in one says
nothing about a sibling.

### Model revision date

TODO: the date the model was last revised (`YYYY-MM`). The update skill
defaults its window to everything closed since this date.

### Rubric

The section numbers the skills cite (§1.15 known non-findings, §1.17
dispositions) are coordinates into the Alpha-Omega threat-model
specification: <https://github.com/alpha-omega-security/threat-model>.
Magpie references it and keeps no local copy. Override this only if the
project measures its model against a different published rubric.

### Where substantive conversation goes

TODO: the private list that model gaps, missing sections, and broken
links are raised on — normally the project's private governance list.
Substantive findings never go to a public issue tracker; the reasoning
is in the deep doc.

### PR conventions

Used by the `model_pr.py` helper when it opens a discoverability or
model PR.

| Setting | Value |
|---|---|
| Branch prefix | TODO: default `security-model` |
| Base branch | TODO: default is the repository's default branch |
| License header for created files | TODO: `spdx` (default), `apache-full` (needed where the licence checker matches only the canonical boilerplate), or `none` |
| Reporting address for a created `SECURITY.md` | TODO: normally `<security-list>` |
