<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Issue-management family
status: experimental
kind: feature
mode: Triage
source: >
  MISSION.md § Technical scope (Triage). triage-mode.md § Known Gaps
  ("General-issue triage lacks the dedupe, stale-handling, and
  backlog-dashboard coverage the security side already has").
  docs/issue-management/README.md. Implemented by issue-triage,
  issue-reassess, issue-reassess-stats, issue-reproducer,
  issue-fix-workflow, issue-stale-sweep, issue-backlog-stats, and
  issue-deduplicate.
acceptance:
  - Every issue-management skill is read-only or proposes-then-confirms;
    none applies a label, comment, or close without explicit maintainer
    confirmation.
  - issue-fix-workflow produces a branch, commits, and test results but
    never pushes or opens a PR without the maintainer's direct action.
  - issue-backlog-stats and issue-reassess-stats are strictly read-only;
    no tracker state is mutated.
  - All family skills validate under skill-and-tool-validate with no errors.
  - docs/modes.md Agentic Triage and Agentic Drafting tables carry each shipped
    issue-management skill.
---

# Issue-management family

## What it does

Groups the skills for maintaining a project's general-issue tracker into a
named family. The family covers per-issue work, pool-level sweeps, backlog
hygiene, duplication resolution, and read-only reporting — mirroring the
depth the `security-issue-*` family already provides for the confidential
tracker.

The canonical lifecycle a maintainer walks:

1. **Agentic Triage** a candidate pool of open issues → classification + disposition.
2. **Reproduce** a code-level bug to confirm it → structured verdict.
3. **Draft a fix** for a triaged confirmed bug or feature → branch +
   commits + test results for human review and push.
4. **Reassess** a pool of resolved or EOL issues → silent-fix and
   partial-fix surfaces.
5. **Stale-sweep** the backlog → classify dormant issues; post notices on
   confirmation; close on second confirmation.
6. **Deduplicate** two open issues with the same root cause → propose merge;
   execute on confirmation.
7. **Dashboard** (backlog stats / reassess stats) → read-only aggregate view
   of tracker health.

Each skill is independent; a maintainer may use any subset depending on
the project's workflow. The skills share a common adopter-config scaffold
and a consistent propose-before-act discipline.

## Where it lives

- Skill: `issue-triage` — sweeps the configured candidate pool, classifies
  each issue against the project's disposition criteria (BUG /
  FEATURE-REQUEST / NEEDS-INFO / DUPLICATE / INVALID / ALREADY-FIXED),
  and proposes a disposition for maintainer confirmation before any write.
  Ships `mode: Triage` + `experimental`.

- Skill: `issue-reassess` — sweeps a configured pool of resolved or
  end-of-life issues and re-assesses each against the current default
  branch, surfacing silent fixes and partial fixes for re-opening or
  closing. Read-only on the tracker until confirmation.
  Ships `mode: Triage` + `experimental`.

- Skill: `issue-reassess-stats` — read-only dashboard over a directory
  of `verdict.json` artefacts produced by `issue-reassess` campaigns.
  Surfaces a health rating, classification distribution, partial-fix
  surfaces, oldest-unresolved buckets, and per-component breakdowns.
  Output is HTML by default; Markdown fallback available. No tracker
  state is mutated. Ships `experimental`, outside MISSION mode taxonomy.

- Skill: `issue-reproducer` — for a single issue identifying a code-level
  bug, extracts the reporter's example code, adapts it to run on the
  current default branch, executes via the project's configured runtime,
  and composes a structured reproduction verdict. Read-only on the tracker;
  never posts a comment. Ships `experimental`, outside MISSION mode taxonomy.

- Skill: `issue-fix-workflow` — drafts a fix for a triaged confirmed issue:
  failing regression test, smallest production change, targeted test run,
  commit message, and PR-description template. Hands back a branch and
  commit summary; does not push or open a PR without the maintainer's
  explicit direction. Ships `mode: Drafting` + `experimental`.

- Skill: `issue-stale-sweep` — sweeps open issues for inactivity past
  configurable thresholds, classifies each as `REQUEST-UPDATE` (activity
  nudge) or `CLOSE-STALE` (pre-close notice), posts one comment per issue
  on maintainer confirmation; closures require a separate explicit
  confirmation step. Ships `mode: Triage` + `capability: capability:triage`
  + `experimental`.

- Skill: `issue-backlog-stats` — read-only maintainer dashboard over the
  open issue backlog. Surfaces age distribution, triage-rate trends,
  component pressure, and stale-fraction without modifying any tracker
  state. Ships `mode: Triage` + `capability: capability:stats`
  + `experimental`.

- Skill: `issue-deduplicate` — identifies two open issues with the same root
  cause, drafts a merge rationale and cross-link comment, and proposes
  closing the duplicate after the maintainer confirms. Never closes without
  explicit confirmation. Ships `mode: Triage` + `capability: capability:resolve`
  + `experimental`.

- Family README: `docs/issue-management/README.md` — family overview,
  mode boundary with `pr-management-*` and `security-issue-*`, and the
  adopter-config scaffold.

- Adopter config (in `projects/_template/`): `project.md`,
  `issue-tracker-config.md`, `scope-labels.md`, `release-trains.md`,
  `canned-responses.md`, `runtime-invocation.md`,
  `reassess-pool-defaults.md`, `reproducer-conventions.md`,
  `stale-sweep-config.md`.

## Behaviour & contract

- **Read-only or propose-then-confirm.** Agentic Triage-mode skills never write
  a label, comment, or state change without the maintainer typing a
  confirmation. The single exception class — dashboard skills
  (`issue-backlog-stats`, `issue-reassess-stats`) — is unconditionally
  read-only; they emit a rendered report, never a tracker write.

- **Dual-confirm for closures.** `issue-stale-sweep` and
  `issue-deduplicate` require a first confirmation to post a notice or
  cross-link comment, and a second explicit confirmation before any issue
  is closed. Closing is never implied by the first confirmation.

- **Draft, never push.** `issue-fix-workflow` produces a local branch with
  commits and test results. The human maintainer reviews, then pushes and
  opens the PR via `gh pr create --web`. The skill never executes a push
  or a `gh pr create` autonomously.

- **Evidence-only for reproducer.** `issue-reproducer` extracts and runs
  code; it never posts its verdict to the tracker. The reproduction
  package (code + runtime output + verdict JSON) is written to the local
  evidence directory; the maintainer decides what to do with it.

- **Point-in-time sweeps.** Pool-sweeping skills (`issue-triage`,
  `issue-reassess`, `issue-stale-sweep`) process a bounded candidate pool
  per run. They do not persist incremental sweep state between runs; each
  run is a fresh snapshot of the configured pool.

- **Within-tracker deduplication only.** `issue-deduplicate` resolves
  duplicate pairs within the same tracker. Cross-tracker duplicates (e.g.,
  the same bug reported in both a JIRA project and GitHub Issues) are out
  of scope.

## Out of scope

- **Auto-closing or auto-labelling without confirmation.** No skill applies
  a tracker state change without an explicit maintainer confirmation step.
- **Continuous monitoring.** Each skill run is a triggered, bounded
  operation. Alerting and scheduled sweeps are CI / GitHub Actions
  responsibilities.
- **Cross-tracker deduplication.** `issue-deduplicate` operates within a
  single configured tracker. Resolving the same bug across two trackers
  (JIRA + GitHub Issues) requires a human-led merge.
- **Complex multi-file or architecture-level fixes.** `issue-fix-workflow`
  targets well-scoped, single-file bugs where a failing test + minimal
  patch is the right response. Large refactors or cross-cutting changes
  need a human-led workflow.
- **Security-class issues.** CVE-rated bugs and confidential reports flow
  through the `security-issue-*` family
  ([security-issue-lifecycle.md](security-issue-lifecycle.md)); the
  issue-management family handles the public general-issue tracker only.

## Acceptance criteria

1. Every issue-management skill is read-only or proposes-then-confirms;
   none applies a label, comment, close, or cross-link without maintainer
   confirmation.
2. `issue-stale-sweep` and `issue-deduplicate` require a second explicit
   confirmation before any issue is closed; a single confirmation posts
   the notice or cross-link only.
3. `issue-fix-workflow` hands back a branch + commit summary; the PR is
   opened by the maintainer (`gh pr create --web`), never by the skill.
4. `issue-backlog-stats` and `issue-reassess-stats` produce a rendered
   report without mutating any tracker state.
5. All family skills pass `skill-and-tool-validate` with no errors.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **No adopter pilot has run the full family.** All eight skills are
  `experimental`; no maintainer has exercised the triage → reproduce →
  fix-draft → stale-sweep → deduplicate → dashboard pipeline end-to-end.
  Shape may change as pilot evaluations surface edge cases.
- **`issue-reproducer` is Python-only.** The current skill extracts code
  and invokes the project runtime via `runtime-invocation.md`; other
  language runtimes (JVM, Node.js, Go) are supported only if the adopter's
  `reproducer-conventions.md` provides a matching invocation recipe. No
  language-detection or multi-runtime branching exists in the skill today.
- **`issue-fix-workflow` is bounded to single-file, well-scoped bugs.**
  Multi-file refactors, cross-cutting API changes, and architecture-level
  fixes exceed the skill's scope and must be handed back to a human-led
  workflow. This boundary is intentional, not a tooling gap, but adopters
  should be aware of it.
- **`docs/modes.md` Agentic Triage table may not reflect newer skills.**
  `issue-backlog-stats` and `issue-deduplicate` may not yet appear in the
  `docs/modes.md` Agentic Triage table; a docs-sync PR should verify and add them.
