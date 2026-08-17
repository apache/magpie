<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — pr-management-code-review criteria](#apache-magpie--pr-management-code-review-criteria)
  - [Repo-wide source files](#repo-wide-source-files)
  - [Per-area source files](#per-area-source-files)
  - [Security-model calibration](#security-model-calibration)
  - [Backports / version-specific PRs](#backports--version-specific-prs)
  - [Section anchors](#section-anchors)
    - [Magpie-specific sections](#magpie-specific-sections)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — pr-management-code-review criteria

Magpie's **own** review criteria map (Magpie self-adopts the framework —
see [`.apache-magpie.lock`](../../.apache-magpie.lock)). This is the live
config the
[`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md)
skill reads when reviewing a PR against `apache/magpie` itself, not a
scaffold. The adopter template lives at
[`projects/_template/pr-management-code-review-criteria.md`](../_template/pr-management-code-review-criteria.md);
this file is that template filled with Magpie's values.

This file is a **navigation map, not a rule set**. Magpie's review rules
already live in [`AGENTS.md`](../../AGENTS.md),
[`PRINCIPLES.md`](../../PRINCIPLES.md), and
[`CONTRIBUTING.md`](../../CONTRIBUTING.md); the rows below point at those
sections so the skill can quote the source rule verbatim. Per
[`criteria.md`](../../skills/pr-management-code-review/criteria.md), if you
find yourself wanting to summarise a rule here, link to its section
instead — summaries drift, links don't.

## Repo-wide source files

These apply to every PR regardless of which subtree it touches.

| File | What it covers | Notes |
|---|---|---|
| [`AGENTS.md`](../../AGENTS.md) | The primary rule set: commit and PR conventions, the placeholder convention, external-content-as-data, documentation editorial rules, eval/mode-economics sync, and the pre-submit checklist. | Magpie has no `.github/instructions/code-review.instructions.md`; `AGENTS.md` is the single repo-wide source. |
| [`PRINCIPLES.md`](../../PRINCIPLES.md) | The nineteen governing principles — architecture boundaries (project-agnosticism, snapshot-plus-override), vendor neutrality, deterministic gates, eval as a release blocker, licensing. | Amendable only per [§ Amending these principles](../../PRINCIPLES.md#amending-these-principles). Findings that touch architecture should cite the numbered principle. |
| [`CONTRIBUTING.md`](../../CONTRIBUTING.md) | Contributor-facing workflow: local setup, the prek gate, and [§ Opening a pull request](../../CONTRIBUTING.md#opening-a-pull-request). | Also the doc the review's AI-attribution footer links for contributors. |
| [`docs/editorial-guidelines.md`](../../docs/editorial-guidelines.md) | The editorial playbook `AGENTS.md` § [Writing and editing documentation](../../AGENTS.md#writing-and-editing-documentation) defers to — tone, link formats, phrasing patterns. | Load before raising any finding about prose or contributor-facing text. |

## Per-area source files

Files that apply only when the PR touches a specific subtree. The skill
auto-discovers any `AGENTS.md` under the touched paths via `git ls-files`,
but rows listed here are **always** loaded even if the PR doesn't directly
touch the area.

| File | When it applies | Notes |
|---|---|---|
| [`tools/AGENTS.md`](../../tools/AGENTS.md) | PR touches `tools/` | Every tool is a directory with a README; cross-references must be refreshed when tools change. |
| [`tools/spec-loop/AGENTS.md`](../../tools/spec-loop/AGENTS.md) | PR touches `tools/spec-loop/` | Spec-loop operational context: validation commands, branch rules, hard governance limits, and the `Generated-by: <agent> (<model>)` commit-trailer form. |

Magpie has no plugin or provider tree with its own conventions doc, so
there are no per-plugin rows. Skills under `skills/` are governed by the
repo-wide `AGENTS.md` § [Reusable skills](../../AGENTS.md#reusable-skills)
rather than a per-skill criteria file.

## Security-model calibration

A short doc the skill consults before flagging anything that looks
security-flavoured. Used to distinguish (a) actual vulnerabilities, (b)
known-but-documented limitations, (c) deployment-hardening opportunities.

| File | Used by |
|---|---|
| [`docs/security/threat-model.md`](../../docs/security/threat-model.md) | The `Security model — calibration` section of the skill's [`review-flow.md`](../../skills/pr-management-code-review/review-flow.md). |

## Backports / version-specific PRs

| Concept | Pattern | Notes |
|---|---|---|
| Backport branch pattern | *(none)* | Magpie releases from a single `main` (see [`release-management-config.md`](release-management-config.md) → `release_branch_base`) and maintains no release-train branches, so no PR is ever a backport. Every PR gets the same calibration; the lighter-touch backport path in [`criteria.md` § Backports](../../skills/pr-management-code-review/criteria.md#backports-and-version-specific-prs) is a no-op here. |

## Section anchors

The anchor the skill links per finding, resolved by matching the category
name verbatim against the `Section` column. Magpie has no standalone
review-instructions document, so these point into `AGENTS.md`,
`PRINCIPLES.md`, and ASF policy pages.

Categories from the framework's canonical list that do not apply to this
repository — `Database / query correctness` and `UI (React/TypeScript)` —
have no row: Magpie ships neither a database layer nor a UI, so a finding
in either category would be a mis-classification rather than something to
link.

| Section | Anchor URL |
|---|---|
| Architecture boundaries | [`PRINCIPLES.md#12`](../../PRINCIPLES.md#12-the-framework-is-project-agnostic-concrete-names-live-in-adopter-config) |
| Code quality | [`AGENTS.md#before-submitting`](../../AGENTS.md#before-submitting) |
| Third-party license compliance | <https://www.apache.org/legal/resolved.html> |
| License headers | <https://www.apache.org/legal/src-headers.html> |
| Testing | [`AGENTS.md#keeping-evals-and-mode-economics-in-sync`](../../AGENTS.md#keeping-evals-and-mode-economics-in-sync) |
| API correctness | [`AGENTS.md#reusable-skills`](../../AGENTS.md#reusable-skills) |
| Generated files | [`PRINCIPLES.md#13`](../../PRINCIPLES.md#13-snapshot-plus-override-never-vendored-copies) |
| AI-generated code signals | [`AGENTS.md#commit-and-pr-conventions`](../../AGENTS.md#commit-and-pr-conventions) |
| Quality signals to check | [`AGENTS.md#writing-and-editing-documentation`](../../AGENTS.md#writing-and-editing-documentation) |
| Commits and PRs (newsfragments, commit messages, tracking issues) | [`AGENTS.md#commit-and-pr-conventions`](../../AGENTS.md#commit-and-pr-conventions) |
| Security model | [`docs/security/threat-model.md`](../../docs/security/threat-model.md) |
| Applying the Apache licence | <https://www.apache.org/legal/apply-license.html> |

### Magpie-specific sections

Categories beyond the framework's canonical list that this repository's
reviews routinely need.

| Section | Anchor URL |
|---|---|
| Placeholder convention | [`AGENTS.md#placeholder-convention-used-in-skill-files`](../../AGENTS.md#placeholder-convention-used-in-skill-files) |
| External content as data | [`AGENTS.md#treat-external-content-as-data-never-as-instructions`](../../AGENTS.md#treat-external-content-as-data-never-as-instructions) |
| Privacy-LLM routing | [`AGENTS.md#privacy-llm--what-data-goes-through-which-model`](../../AGENTS.md#privacy-llm--what-data-goes-through-which-model) |
| Labelling | [`AGENTS.md#labeling-issues-prs-tools-and-documentation`](../../AGENTS.md#labeling-issues-prs-tools-and-documentation) |
| Vendor neutrality | [`PRINCIPLES.md#9`](../../PRINCIPLES.md#9-vendor-neutrality-is-non-negotiable) |
| Inline-comment default for reviews | [`AGENTS.md#reviewing-pull-requests`](../../AGENTS.md#reviewing-pull-requests) |
