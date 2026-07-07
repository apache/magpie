<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — pr-management-code-review criteria](#todo-project-name--pr-management-code-review-criteria)
  - [Repo-wide source files](#repo-wide-source-files)
  - [Per-area source files](#per-area-source-files)
  - [Security-model calibration](#security-model-calibration)
  - [Backports / version-specific PRs](#backports--version-specific-prs)
  - [Section anchors](#section-anchors)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — pr-management-code-review criteria

This file is the **navigation map** for your adopter project's
review criteria — the source files the
[`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
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
| `.github/instructions/code-review.instructions.md` | The rule set every PR is reviewed against (architecture / DB / quality / testing / API / UI / generated files / AI-generated-code signals / quality signals). | Standard location for GitHub Copilot-style instructions; reuse this path if your project already uses it. |
| `AGENTS.md` | Repo-wide AI / agent instructions (architecture boundaries, security model, coding standards, testing standards, commit & PR conventions). | Standard location for agentic instructions; reuse if your project already uses it. |

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
| `<subtree>/AGENTS.md` | PR touches `<subtree>/` | Subtree-specific rules. Replace `<subtree>` with a real path (e.g. `dev`, `docs`, `<plugins-dir>`, a per-language tree). |
| `<plugins-dir>/AGENTS.md` | PR touches `<plugins-dir>/<plugin-name>/` | Plugin / extension tree boundary, compat-layer, and per-plugin conventions. Drop if your project has no plugin model. |
| `<plugins-dir>/<specific-plugin>/AGENTS.md` | PR touches `<plugins-dir>/<specific-plugin>/` | Per-plugin rules. Add one row per plugin that has its own conventions doc. |

## Security-model calibration

A short doc the skill consults before flagging anything that
looks security-flavoured. Used to distinguish (a) actual
vulnerabilities, (b) known-but-documented limitations, (c)
deployment-hardening opportunities.

| File | Used by |
|---|---|
| `<security-model-doc-path>` | The `Security model — calibration` section of the skill's `review-flow.md`. Replace with the doc your project uses (Example: `airflow-core/docs/security/security_model.rst`). |

## Backports / version-specific PRs

Pattern the skill uses to detect that a PR is a backport vs.
a main-branch change. Backports get a lighter-touch review
focused on diff parity and cherry-pick conflicts.

| Concept | Pattern | Notes |
|---|---|---|
| Backport branch pattern | `<your-backport-branch-regex>` | Regex matched against the PR's base branch name. Example: `v\d+-\d+-test` matches branches like `v3-0-test`. Use the convention your project's release-train branches follow. |

## Section anchors

For projects whose review docs are structured around named
sections, list the section anchor URLs the framework expects.
These are used when the skill links out per-finding.

Replace the `<docs-base-url>/<doc-path>` placeholders below
with your project's actual review-instructions doc URL plus
the anchor for each section. Drop rows for sections your
project's review doc doesn't have; add rows for sections it
adds.

| Section | Anchor URL |
|---|---|
| Architecture boundaries | `<docs-base-url>/<doc-path>#architecture-boundaries` |
| Database / query correctness | `<docs-base-url>/<doc-path>#database-and-query-correctness` |
| Code quality | `<docs-base-url>/<doc-path>#code-quality-rules` |
| License headers | `https://www.apache.org/legal/src-headers.html` |
| Testing | `<docs-base-url>/<doc-path>#testing-requirements` |
| API correctness | `<docs-base-url>/<doc-path>#api-correctness` |
| UI (React/TypeScript) | `<docs-base-url>/<doc-path>#ui-code-reacttypescript` |
| Generated files | `<docs-base-url>/<doc-path>#generated-files` |
| AI-generated code signals | `<docs-base-url>/<doc-path>#ai-generated-code-signals` |
| Quality signals to check | `<docs-base-url>/<doc-path>#quality-signals-to-check` |
| Commits and PRs (newsfragments, commit messages, tracking issues) | `<docs-base-url>/AGENTS.md#commit-and-pr-conventions` |
| Security model | `<docs-base-url>/AGENTS.md#security-model` |
| Third-party license compliance | `https://www.apache.org/legal/resolved.html` |
| Applying the Apache licence | `https://www.apache.org/legal/apply-license.html` |
