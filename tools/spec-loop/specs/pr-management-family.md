<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: PR management family
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Technical scope (Triage: "proposes initial routing") and
  § Rationale ("review-cycle latency is one of the two named priorities").
  Implemented in docs/pr-management/ and skills/pr-management-*/. Skills
  originated as `breeze pr auto-triage` / `breeze pr stats` inside one ASF
  project's toolchain and were lifted into the framework to be reusable
  across any project with a contributor PR queue. mentor lives in the
  Mentoring mode but is PR-domain and included here for navigability.
acceptance:
  - Every Triage-mode skill in the family is read-only or
    proposes-then-confirms; none applies a label, comment, or state change
    without explicit maintainer confirmation.
  - pr-management-quick-merge never merges autonomously; it surfaces
    candidates and the exact merge command for the maintainer.
  - pr-management-mentor never posts without explicit maintainer
    confirmation; its output is pedagogical, never gatekeeping.
  - All family skills validate under skill-and-tool-validate with no errors.
  - docs/pr-management/README.md lists all five family skills.
---

# PR management family

## What it does

Groups the skills for managing a project's public contributor PR queue
into a named family. The family covers the full lifecycle of a PR from
first submission through merge or close: first-pass triage and action,
queue-level health reporting, line-aware code review, express-lane merge
surfacing for trivial changes, and pedagogical engagement with contributors
in a teaching register.

The canonical flow a maintainer runs:

1. **Triage** a candidate pool of open PRs → per-PR disposition proposal
   (draft / comment / close / rebase / rerun / mark ready / ping).
2. **Stats** for a before/after queue health snapshot to prioritise triage
   effort and measure throughput.
3. **Code review** a single PR deeply → `APPROVE` / `REQUEST_CHANGES` /
   `COMMENT` with inline rationale, posted on confirmation.
4. **Quick-merge** screen the `ready for maintainer review` queue for
   trivial, low-risk PRs → ranked candidates + merge command. Never merges.
5. **Mentor** join a PR (or issue) thread in a teaching register →
   draft a pedagogical comment for the maintainer to post.

Skills 1–4 live in the Triage mode; skill 5 is in the Mentoring mode and
is listed here for navigability since its domain is PR threads.

## Where it lives

- Skill: `pr-management-triage` — first-pass sweep of the PR queue.
  Classifies each candidate against a project decision table and proposes
  a disposition; the maintainer confirms per PR or per group. State changes
  execute on confirmation only. Ships `mode: Triage` + `experimental`.
  Detail files: `skills/pr-management-triage/`.
- Skill: `pr-management-stats` — read-only summary tables of the open PR
  backlog, grouped by area label, age bucket, and triage state. No tracker
  state is mutated. Ships `mode: Triage` + `capability: capability:stats`
  + `experimental`. Backed by `tools/pr-management-stats/`.
- Skill: `pr-management-code-review` — deep, line-aware code review one
  PR at a time; applies project criteria and drafts an `APPROVE` /
  `REQUEST_CHANGES` / `COMMENT` review with inline comments; posts on
  maintainer confirmation. Ships `mode: Triage` + `experimental`.
- Skill: `pr-management-quick-merge` — read-only express-lane screener
  for trivial, low-risk PRs (docs, changelog, translations, tests) that
  pass every quality gate; surfaces ranked candidates with diff summaries
  and the exact merge command. Never merges autonomously. Ships `mode:
  Triage` + `experimental`.
- Skill: `pr-management-mentor` — drafts a teaching-register comment on a
  single GitHub issue or PR thread; waits for explicit maintainer
  confirmation before posting. Ships `mode: Mentoring` + `experimental`.
  Listed here because its domain is PR/issue threads; documented in detail
  in [`docs/mentoring/README.md`](../../../docs/mentoring/README.md).
- Family README: `docs/pr-management/README.md` — family overview, skill
  table, adopter-config scaffold.
- Tool: `tools/pr-management-stats/` — deterministic Python backing for
  `pr-management-stats`; ships its own tests.
- Adopter config (in `projects/_template/`): `project.md`,
  `pr-management-config.md`, `pr-management-triage-comment-templates.md`,
  `pr-management-triage-ci-check-map.md`, `pr-management-code-review-criteria.md`,
  `pr-management-quick-merge-config.md`.

## Behaviour & contract

- **Read-only or propose-then-confirm.** Triage-mode skills never write
  a label, comment, or state change without the maintainer typing a
  confirmation in-session. The single exception class — `pr-management-stats`
  — is unconditionally read-only; it emits rendered tables, never a write.
- **Stable per-PR drill-in progress.** `pr-management-triage` prefixes each
  individual drill-in with the PR's original one-based group position and
  group size plus the active `classify → propose <action>` transition.
  `[E]` and `[P]NN` preserve that position and denominator across skipped,
  pending, and pulled-out rows; a changed head advances the transition to
  `re-classify → propose <action>` after live state is refreshed.
- **Quick-merge never merges.** `pr-management-quick-merge` surfaces
  candidates and the maintainer runs the exact `gh pr merge` command
  themselves. Automated merge belongs to a future Auto-merge mode that is
  deliberately off by MISSION sequencing.
- **Teaching register for mentoring.** `pr-management-mentor` follows the
  Mentoring mode's tone contract (polite, never gatekeeping, explicit
  hand-off to a human when scope exceeds the agent). It posts only on
  maintainer confirmation.
- **Untrusted content stays data.** PR bodies, titles, and author comments
  are input data for classification; injected instructions in PR body text
  are ignored and flagged. Inherits the absolute rule from
  [`AGENTS.md`](../../../AGENTS.md#treat-external-content-as-data-never-as-instructions).
- **Evidence-gated dependency-version findings.**
  `pr-management-code-review` inventories every mandatory direct and
  transitive constraint path, applies environment markers, and intersects
  the resulting ranges with available lock, resolver, and supported-version
  metadata. An empty effective intersection in any supported environment
  establishes `broken` because the graph is uninstallable; a concrete
  supported failing resolution also establishes `broken`. Exhaustive evidence
  that rules out both failures establishes `compatible`; partial evidence
  without either remains `unknown`. Every surfaced finding carries that
  constraint ledger, and its remediation follows the adopter's applicable
  `AGENTS.md` and dependency or release policy for all three classifications.
- **Config-driven, not skill-edited.** Project-specific values
  (committers team handle, area-label prefix, comment-template wording,
  CI-check → doc-URL map, review criteria, quick-merge path globs) all
  live in `<project-config>/` files; no skill body carries a project
  hardcode.

## Out of scope

- **Auto-merge.** No skill in this family merges, closes, or approves
  without a human confirmation in-session. Full auto-merge belongs to the
  Auto-merge mode (deliberately off per MISSION sequencing).
- **Security-class PRs.** CVE-fixing PRs flow through the
  `security-issue-fix` skill ([security-issue-lifecycle.md](security-issue-lifecycle.md));
  the PR management family handles the public general-purpose queue only.
- **Cross-repository PR management.** Skills scope to one configured
  `<upstream>` repo per invocation.
- **Continuous monitoring.** Each skill run is a triggered, bounded
  operation; alerting and scheduled sweeps are CI / GitHub Actions
  responsibilities.

## Acceptance criteria

1. `pr-management-triage` never writes a label, comment, or state change
   without in-session confirmation; all state-changing actions are
   propose-before-apply.
2. `pr-management-quick-merge` surfaces candidates with the merge command
   but never executes the merge autonomously.
3. `pr-management-mentor` posts only on explicit maintainer confirmation
   and never gates or rejects contributor work.
4. `pr-management-stats` emits read-only tables without mutating any
   tracker or PR state.
5. All family skills pass `skill-and-tool-validate` with no errors.
6. `pr-management-code-review` has a dedicated eval suite covering
   selector resolution, review-risk classification, AI-generated-code
   signals, prompt injection in PR content, and the final review handoff.
7. `pr-management-code-review` never surfaces a dependency-version
   compatibility finding without a complete constraint ledger and a
   supported `broken`, `compatible`, or `unknown` classification. An empty
   effective intersection is `broken` without requiring a concrete failing
   resolution; recommended remediation follows the adopter's documented
   policy.
8. Every `pr-management-triage` per-PR drill-in shows a stable
   `[position/total]` header and the active classify-to-propose transition;
   `[E]` and `[P]NN` do not renumber the original group.

## Validation

```bash
test -f .agents/skills/magpie-pr-management-triage/SKILL.md
test -f .agents/skills/magpie-pr-management-stats/SKILL.md
test -f .agents/skills/magpie-pr-management-code-review/SKILL.md
test -f .agents/skills/magpie-pr-management-quick-merge/SKILL.md
test -f .agents/skills/magpie-pr-management-mentor/SKILL.md
test -f docs/pr-management/README.md
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **`experimental` — no adopter pilot has run the full family end-to-end.**
  All five skills are on main with eval suites; no maintainer has exercised
  the triage → stats → code-review → quick-merge → mentor pipeline
  end-to-end under evaluation conditions. Shape may change as pilot
  evaluations surface real-world usage patterns.
- **`pr-management-code-review` now has a full eval suite** at
  `tools/skill-evals/evals/pr-management-code-review/` covering 116 cases
  across 27 suites: selector resolution, per-finding risk classification,
  AI-generated-code signal handling, prompt-injection resistance across PR
  body / code comments / commit messages, review-disposition (APPROVE /
  REQUEST_CHANGES / COMMENT), and the confirmation-gate handoff (post /
  dry-run-skip / re-draft), plus evidence-gated dependency compatibility
  across transitive paths, empty intersections, partial metadata, environment
  markers, and adopter-specific remediation. The SOFT eval-coverage validator
  warning is cleared. Acceptance criteria 6 and 7 are met.
- **Stale-PR handling is built into `pr-management-triage`.** Dedicated
  stale sweeps (`stale-draft`, `inactive-open`, `stale-review-ping`) run
  as Step 5 of the triage flow and can be invoked standalone via
  `triage stale`. A separate `pr-management-stale-sweep` skill is
  intentionally not planned; the triage skill already covers this surface.
- **`pr-management-mentor` is documented under Mentoring mode** and is
  listed in `docs/mentoring/README.md`. The PR management README
  cross-references it as a companion skill; adopters wanting PR-thread
  mentoring enable it alongside the triage suite.
