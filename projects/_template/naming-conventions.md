<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — naming and editorial conventions](#todo-project-name--naming-and-editorial-conventions)
  - [Terminology](#terminology)
  - [Contributor-count phrasing](#contributor-count-phrasing)
  - [Acronyms](#acronyms)
  - [Mentioning project maintainers and security-team members](#mentioning-project-maintainers-and-security-team-members)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — naming and editorial conventions

This file holds the **project-specific** editorial rules the skills
and canned responses follow. Project-agnostic editorial rules (tone,
brevity, threading, confidentiality, placeholder convention) live in
the repo-level [`../../AGENTS.md`](../../AGENTS.md) and apply to
every project — do not duplicate them here.

Keep this file terse. Add a rule only when the project diverges from
a generic convention. Delete sections you do not need.

## Terminology

TODO: project-specific capitalisation / spelling rules. Examples:

- TODO: `Foo` (not `FOO`) when referring to the project in prose.
- TODO: how to refer to specific concepts / roles in the product.

## Contributor-count phrasing

TODO: if the project often gets asked about contributor counts in
reporter conversations, lock in the phrasing (e.g. *"thousands of
contributors"* rather than a concrete number that dates quickly).
Otherwise delete this section.

## Acronyms

TODO: project-specific canonical capitalisations for acronyms that
appear often in canned responses.

## Mentioning project maintainers and security-team members

The generic rule (*"use `@handle`, not plain name, in GitHub
surfaces"*) lives in [`../../AGENTS.md`](../../AGENTS.md) and
applies to every project. What is project-specific is **which
people the rule applies to** and **which GitHub handles are the
right ones to `@`-mention**:

- TODO: the authoritative source of the PMC + committer roster (for
  ASF projects: `https://projects.apache.org/committee.html?<PROJECT>`).
- TODO: whether the security team uses release-manager rotations
  whose members should be `@`-mentioned on status updates, and if
  so, where to find the current rotation (typically
  [`release-trains.md`](release-trains.md)).
- TODO: public-surface caveats — e.g. for `<upstream>` public PRs,
  an `@`-mention must stand on its own without any of the forbidden
  terms that reveal the private nature of the coordination.

Concrete roster handles should live in
[`release-trains.md`](release-trains.md), not here — that file is
the fast-moving source of truth.
