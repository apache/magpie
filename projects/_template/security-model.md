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
