<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Review criteria — pointers to source

This file is a **navigation map** for the project's review
criteria. It does not restate the rules — those live in the
source files below and are the single source of truth. The
skill's review pass reads them at session start (and re-reads
the per-area `AGENTS.md` files as PRs route into different
trees) and quotes the **source rule verbatim** in any finding
it raises.

If you find yourself wanting to "summarise the rule" in this
file or in a finding body, **stop and link to the source line
or section instead**. Summaries drift; links don't.

---

## Source files

| File | What it covers |
|---|---|
| (read from `<project-config>/pr-management-code-review-criteria.md` → `repo_wide_source_files`) | The rule set every <PROJECT> PR is reviewed against. |

The concrete list of source files is project-specific and lives in
the adopter's `<project-config>/pr-management-code-review-criteria.md`.
The table below shows the **shape** of a typical configuration;
see `projects/_template/pr-management-code-review-criteria.md` for
a concrete example.

| File | What it covers |
|---|---|
| `<repo_wide_review_criteria>` | The rule set every PR is reviewed against (typically architecture / DB / quality / testing / API / UI / generated files / AI-generated-code signals / quality signals). |
| `AGENTS.md` | Repo-wide AI/agent instructions (architecture boundaries, security model, coding standards, testing standards, commits & PR conventions). |
| `<area>/AGENTS.md` | Per-area rules (e.g. tree-specific or subsystem-specific overlays). |
| `<security-model-doc>` | The documented security model — what *is* and *isn't* a vulnerability. |

`code-review context` resolves which of these apply to a PR (`sources_to_read`), including every `AGENTS.md` between a touched file and the repository root.

---

## Categories — link out to the source section

The list below is the **abstract canonical category list** the
skill uses when grouping findings. The concrete review-doc URL
for each category lives in the adopter's
`<project-config>/pr-management-code-review-criteria.md` →
`Section anchors` table; the skill resolves a category to its
URL at finding time by matching the category name verbatim
against that table's `Section` column. If a category has no
anchor row, the skill falls back to a plain reference (no
clickable link) and surfaces the missing anchor as a one-line
warning at the top of the review.

The canonical category list — each links to its own file, which `code-review context` names in `docs` only when the PR needs it:

- [Architecture boundaries](criteria/architecture-boundaries.md)
- [Database / query correctness](criteria/database-query-correctness.md)
- [Code quality](criteria/code-quality.md)
- [Third-party license compliance](criteria/third-party-license-compliance.md)
- [License headers](criteria/license-headers.md)
- [Testing](criteria/testing.md)
- [API correctness](criteria/api-correctness.md)
- [UI (React/TypeScript)](criteria/ui.md)
- [Generated files](criteria/generated-files.md)
- [AI-generated code signals](criteria/ai-generated-code-signals.md)
- [Quality signals to check](criteria/quality-signals-to-check.md) (and [image IP](criteria/image-ip.md))
- [Commits and PRs (newsfragments, commit messages, tracking issues)](criteria/commits-and-prs.md)
- [Security model](criteria/security-model.md)

See
[`projects/_template/pr-management-code-review-criteria.md` § Section anchors](../../../magpie-setup/templates/pr-management-code-review-criteria.md#section-anchors)
for a worked example.

---

---

## Per-area / subtree-specific signals

When a PR touches a subtree the adopter listed in
`<project-config>/pr-management-code-review-criteria.md` →
`Per-area source files`, the skill reads (and quotes from) those
per-area files in addition to the repo-wide ones. `code-review context` also
discovers any `AGENTS.md` between a touched file and the root, so one not listed in the table is still loaded.

If a touched subtree has no `AGENTS.md` and no entry in the
adopter table, only the repo-wide rules apply.

---

---

## Backports and version-specific PRs

A PR whose base matches the adopter's backport pattern gets the lighter-touch calibration in [`classifications/backport.md`](classifications/backport.md); `code-review context` sets `backport` when it applies.

---

## Conflict between source rules

If the per-area `AGENTS.md` rules **conflict** with the
repo-wide ones (rare; usually a more specific override), the
more specific one wins — but the conflict is surfaced to the
maintainer for explicit acceptance during disposition pick
(see [`review-flow.md`](review-flow.md)).

---

## When in doubt — defer

If after reading the diff you're not sure whether something is
a finding or just a style preference, **do not flag it**.
Surface the uncertainty to the maintainer (one line:
*"Hmm — line N does X, which I'm not sure violates the rules;
flagging for your eye."*) and let them decide. The cost of an
over-zealous auto-finding is a contributor who feels
nitpicked; the cost of a missed nit is one round of
back-and-forth a maintainer can catch easily on their own
pass.

**Golden rule 3 — criteria are authoritative; this skill is a
checker, not a re-interpreter.** The project's review criteria
live in the source files declared in
`<project-config>/pr-management-code-review-criteria.md` (see
[`projects/_template/pr-management-code-review-criteria.md`](../../../magpie-setup/templates/pr-management-code-review-criteria.md)
for the shape) and in the project's repo-wide
[`AGENTS.md`](../../../../AGENTS.md). When you find a violation,
quote the **specific rule** from those files in the review
finding. Do not invent new rules; do not soften documented ones.
A summary checklist lives in [`criteria.md`](criteria.md) for
quick reference, but the source files are the ground truth.
