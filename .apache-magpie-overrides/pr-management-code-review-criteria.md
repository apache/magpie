<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`Apache Magpie` — pr-management-code-review criteria](#apache-magpie--pr-management-code-review-criteria)
  - [Repo-wide source files](#repo-wide-source-files)
  - [Per-area source files](#per-area-source-files)
  - [Security-model calibration](#security-model-calibration)
  - [Backports / version-specific PRs](#backports--version-specific-prs)
  - [Section anchors](#section-anchors)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `Apache Magpie` — pr-management-code-review criteria

This file is the **navigation map** for your adopter project's
review criteria — the source files the
[`pr-management-code-review`](../skills/pr-management-code-review/SKILL.md)
skill reads when forming its findings.

Copy this file into your own
`<project-config>/pr-management-code-review-criteria.md` and
replace every `<placeholder>` with your project's value. Drop
or add rows so the per-area entries match your project's
tree structure.

The skill's review pass reads each source file at session
start (and re-reads per-area files as PRs route into
different trees) and quotes the **source rule verbatim** in
any finding it raises. If the file is missing or unreadable,
the skill warns and falls back to a smaller default rule set.

## Repo-wide source files

These apply to every PR regardless of which subtree it
touches. At least one entry is required.

| File | What it covers | Notes |
|---|---|---|
| `AGENTS.md` | Repo-wide agent instructions: external-content-as-data, placeholder convention, confidentiality, labeling taxonomy, commit & PR conventions (`Generated-by:` trailer, no `Co-Authored-By`), documentation style (SemBr), evals-in-sync rule, before-submitting checklist. | Derived: present in repo. |
| `CONTRIBUTING.md` | Contributor workflow and expectations. | Derived: present in repo. |
| `PRINCIPLES.md` | Design principles every change is measured against (e.g. §13 snapshot-plus-override, never vendored copies). | Derived: present in repo. |
| `docs/labels-and-capabilities.md` | Label / capability taxonomy a PR must carry. | Derived: referenced from AGENTS.md. |

## Per-area source files

Files that apply only when the PR touches a specific subtree.
The skill auto-discovers any `AGENTS.md` under the touched
paths via `git ls-files`, but rows listed here are **always**
loaded even if the PR doesn't directly touch the area.

The rows below are illustrative — replace with the subtrees
relevant to your project (a plugins / extensions / providers
directory, a `dev/` scripts tree, an IDE bootstrap tree,
language-specific subtrees like `<language>/AGENTS.md`,
etc.). Drop rows that don't apply; add rows for each subtree
where the project has its own conventions.

| File | When it applies | Notes |
|---|---|---|
| `tools/AGENTS.md` | PR touches `tools/` | Derived via `git ls-files`. |
| `tools/spec-loop/AGENTS.md` | PR touches `tools/spec-loop/` | Derived via `git ls-files`. |
| `docs/adapters/README.md` | PR touches `docs/adapters/` | Adapter and runtime conventions (harness adapters). |

## Security-model calibration

A short doc the skill consults before flagging anything that
looks security-flavoured. Used to distinguish (a) actual
vulnerabilities, (b) known-but-documented limitations, (c)
deployment-hardening opportunities.

| File | Used by |
|---|---|
| `docs/setup/secure-agent-internals.md` | The `Security model — calibration` section of the skill's `review-flow.md`. The framework's threat-model doc. |

## Backports / version-specific PRs

Pattern the skill uses to detect that a PR is a backport vs.
a main-branch change. Backports get a lighter-touch review
focused on diff parity and cherry-pick conflicts.

| Concept | Pattern | Notes |
|---|---|---|
| Backport branch pattern | none — Apache Magpie releases only from `main`; no backport branches | Regex matched against the PR's base branch name. |

## Section anchors

For projects whose review docs are structured around named
sections, list the section anchor URLs the framework expects.
These are used when the skill links out per-finding.

Apache Magpie has no single review-instructions doc; each section
points at the closest heading in `AGENTS.md`, `CONTRIBUTING.md`,
`PRINCIPLES.md`, or the AI contribution policy. The framework has
no database or UI code, so those sections are omitted.

| Section | Anchor URL |
|---|---|
| Architecture boundaries | `https://github.com/apache/magpie/blob/main/CONTRIBUTING.md#repository-layout` |
| Project-agnostic skills (placeholders, no hardcoded project values) | `https://github.com/apache/magpie/blob/main/AGENTS.md#placeholder-convention-used-in-skill-files` |
| Code quality | `https://github.com/apache/magpie/blob/main/CONTRIBUTING.md#code-in-this-repo` |
| Documentation style (SemBr, tone, links) | `https://github.com/apache/magpie/blob/main/AGENTS.md#writing-and-editing-documentation` |
| License headers | `https://www.apache.org/legal/src-headers.html` |
| Testing (tests, evals, token cost) | `https://github.com/apache/magpie/blob/main/AGENTS.md#keeping-evals-and-mode-economics-in-sync` |
| Tool contracts and adapters | `https://github.com/apache/magpie/blob/main/CONTRIBUTING.md#tool-families` |
| Generated files (doctoc TOCs, token stamps, generated blocks) | `https://github.com/apache/magpie/blob/main/AGENTS.md#local-setup` |
| AI-generated code signals | `https://github.com/apache/magpie/blob/main/docs/ai-contribution-policy.md#4-human-ownership-and-review` |
| Quality signals to check | `https://github.com/apache/magpie/blob/main/AGENTS.md#before-submitting` |
| Commits and PRs (newsfragments, commit messages, tracking issues) | `https://github.com/apache/magpie/blob/main/AGENTS.md#commit-and-pr-conventions` |
| Security model | `https://github.com/apache/magpie/blob/main/docs/setup/secure-agent-internals.md` |
| Design principles | `https://github.com/apache/magpie/blob/main/PRINCIPLES.md` |
| Third-party license compliance | `https://www.apache.org/legal/resolved.html` |
| Applying the Apache licence | `https://www.apache.org/legal/apply-license.html` |
