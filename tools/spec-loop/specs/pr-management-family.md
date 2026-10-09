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
  Implemented in docs/pr-management/ and plugins/magpie-pr-management/skills/
  (each linked from skills/<name>, e.g. skills/pr-management-triage ->
  plugins/magpie-pr-management/skills/pr-triage). Skills
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

Every skill ships in the `magpie-pr-management` plugin under
`plugins/magpie-pr-management/skills/<alias>/`, and the repository name
`skills/<name>` is a link to it.
Since #1390 each `SKILL.md` keeps its gates, golden-rule headlines and
step skeleton inline and moves sub-action detail into sibling files in the
same directory; the behaviour is unchanged.

- Skill: `pr-management-triage` (`pr-triage/`) — first-pass sweep of the PR
  queue.
  Classifies each candidate against a project decision table and proposes
  a disposition; the maintainer confirms per PR or per group. State changes
  execute on confirmation only. Ships `mode: Triage` + `experimental`.
  The deterministic work runs in `tools/pr-management` (`triage classify`,
  `render`, `fold`, `guard`, `session`) over reads saved with
  `vetted-op-read --save`; the agent never evaluates a rule or writes a body.
  Detail files: `prerequisites.md`, `interaction-loop.md`,
  `workflow-approval.md`, `backport-check.md`, `session-history.md`,
  `contract-binding.md`, `typed-decision-prefilter.md`, `design-notes.md`,
  one file per decision row or sweep under `classifications/`, and one per
  action under `actions/`; `triage classify` names which of them a run loads.
  It also ships agent-guard guards under `guards/` (`mark_ready.py`,
  `mention.py`) and the opt-in shadow pre-filter
  `scripts/typed_decision_prefilter.py` with its tests under `tests/`.
- Skill: `pr-management-stats` — read-only summary tables of the open PR
  backlog, grouped by area label, age bucket, and triage state. No tracker
  state is mutated. Ships `mode: Triage` + `capability: capability:stats`
  + `experimental`. Backed by `tools/pr-management-stats/`.
- Skill: `pr-management-code-review` (`code-review/`) — deep, line-aware
  code review one PR at a time; applies project criteria and drafts an
  `APPROVE` / `REQUEST_CHANGES` / `COMMENT` review with inline comments;
  posts on maintainer confirmation. Ships `mode: Triage` + `experimental`.
  Detail files include `prerequisites.md`, `selectors.md`, `review-flow.md`,
  `review-loop.md`, `criteria.md`, `slop-detection.md`, `adversarial.md`,
  and `posting.md`.
- Skill: `pr-management-stack-review` (`stack-review/`) — stack-level review
  of a GitHub stacked pull request. Resolves the stack from a member PR or
  its stack number, fetches the layer heads into `refs/magpie-stack/<S>/*`
  (proposed once, cleaned up at the end), and runs two stdlib scripts:
  `scripts/stack_ledger.py` (file-by-layer matrix, hunk-shape mechanical
  detection, outliers, duplicate release notes, regenerated generated
  files, lock-without-manifest, reading plan and coverage table) and
  `scripts/stack_chain.py` (chain currency, merge commits, trunk drift,
  removed-definition seams at the layer's own head, later heads and new
  trunk uses). Code is read by tier; the report carries the coverage
  table. Posts one rolling `COMMENT` on the lowest open layer (marker,
  updated in place) and never a review event. Ships `mode: Triage` +
  `experimental`. Detail files: `resolve.md`, `detectors.md`, `tiers.md`,
  `report.md`, `adopter-config.md`, `invocation.md`; tests under `tests/`.
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
- Companion skills in the same plugin, covered in other specs:
  `pr-stale-sweep` (`mode: Triage`, draft-or-close inactivity sweep on
  confirmation; [triage mode](triage-mode.md)),
  `reviewer-routing` (`mode: Triage`; [reviewer routing](reviewer-routing.md)),
  and `pre-first-pr-check` (`mode: Pairing`, read-only newcomer checklist on a
  local branch; [pairing mode](pairing-mode.md)).
- Family README: `docs/pr-management/README.md` — family overview, skill
  table, adopter-config scaffold.
- Tool: `tools/pr-management-stats/` — deterministic Python backing for
  `pr-management-stats`; ships its own tests.
- Adopter config (templates in `plugins/magpie-setup/templates/`, which
  `projects/_template/` links to): `project.md`,
  `pr-management-config.md`, `pr-management-triage-comment-templates.md`,
  `pr-management-triage-ci-check-map.md`, `pr-management-code-review-criteria.md`,
  `pr-management-quick-merge-config.md`, and the optional
  `adversarial-review.md` read by code review.

## Behaviour & contract

- **Read-only or propose-then-confirm.** Triage-mode skills never write
  a label, comment, or state change without the maintainer typing a
  confirmation in-session. The single exception class — `pr-management-stats`
  — is unconditionally read-only; it emits rendered tables, never a write.
- **Triage rules run as code, not as model judgement.** `pr-management triage
  classify` evaluates the pre-filters, the first-match-wins decision table,
  the stale sweeps and bot-draft promotion over the saved sweep and prints
  groups in presentation order with the documents each one needs. A decision
  that depends on data the sweep lacks (a truncated rollup page, commits
  behind, a login's permission, live mergeability) comes back under `needs`
  as a vetted read; the skill runs it and classifies again. Every mutation is
  preceded by `triage guard` on fresh reads (moved head, pending workflow
  approval, unknown or conflicting mergeability), and every contributor-facing
  body comes from `triage render`, which allows only the author's
  `@`-mention. Regression cases: `tools/pr-management/tests/`.
- **Stable per-PR drill-in progress.** `pr-management-triage` prefixes each
  individual drill-in with the PR's original one-based group position and
  group size plus the active `classify → propose <action>` transition.
  `[E]` and `[P]NN` preserve that position and denominator across skipped,
  pending, and pulled-out rows; a changed head advances the transition to
  `re-classify → propose <action>` after live state is refreshed.
- **Triage markers from any triager count.** `pr-management-triage`
  treats a PR as already triaged when a triage marker exists after the last
  commit in either channel: a comment by any `OWNER`, `MEMBER`, or
  `COLLABORATOR` carrying the `Pull Request quality criteria` link, or the
  `pr-triage-fold` block in the PR body with a matching `head`, whoever wrote
  it.
  The fold block carries an optional `by=<login>` field naming the triager,
  which the rows 3–4 reasons show; folds written before the field existed
  are read without it.
  Association alone does not start Sweep 1a's close clock: a comment-channel
  marker by anyone other than the viewer counts toward a close only after
  its author passes the live maintainer check, and a marker comment never
  double-counts as maintainer activity.
  Regression cases: `tools/pr-management/tests/test_triage_classify.py`,
  including `test_case_22_fold_by_another_triager_without_by`.
- **Backports are checked early, when the project cherry-picks.** With
  `backport_branches` set in `pr-management-config.md`,
  `pr-management-triage` runs Step 0.7 before the main flow on every open
  PR targeting one of those branches — from any author, drafts included,
  since pre-filters F1/F2 would otherwise drop bot-opened backports. It
  resolves each commit's default-branch source, compares `-U0` patch-ids
  (context lines differ between branches), ignores commits already on the
  base, and under `backport_policy: fixes-only` (the default) flags source
  changes that are not fixes — features, new checks, behaviour changes,
  deprecations, removals, refactors — for closing. It proposes
  hand-off, surface or close and never merges. With `backport_branches`
  empty the step is skipped. Regression cases:
  `tools/skill-evals/evals/pr-management-triage/backport-check/`.
- **Acted-on PRs are not re-surfaced in the same session.**
  After pagination dedup, `triage classify` silently drops
  every PR the session cache holds under a terminal `action_taken` whose
  cached `head_sha` equals the freshly fetched head SHA: it appears in no
  group, progress line, or Step 6 summary.
  A changed head SHA falls through to the existing staleness rule and is
  re-classified; the suppression dies with the session cache (#1479).
- **The mark-ready guard sees every label.** The skill-contributed
  `guards/mark_ready.py` agent-guard guard enforces Golden rule 1b — no
  `ready for maintainer review` label while the head SHA has Actions runs
  awaiting approval — and fails open when the lookup cannot be made.
  It reads every `--add-label` value of a `gh pr edit` (repeated flags,
  `=` form, and CSV lists with or without double quotes) through
  `GuardContext.opts()`, so the ready label cannot slip past bundled with
  another label (#1525).
- **Typed-decision shadow pre-filter is advisory and opt-in.** With
  `enable_typed_decision_prefilter: true` in `pr-management-config.md`
  (default `false`; threshold `typed_decision_confidence_threshold`,
  default `0.85`), Step 2 of `pr-management-triage` runs
  `scripts/typed_decision_prefilter.py` alongside the post-guard
  classification.
  It calls a third-party `typed_decision.choice()` endpoint with public PR
  metadata (title, body, and commit messages fenced as untrusted data),
  and only after a `<project-config>/privacy-llm.md` opt-in entry with a
  data-residency contract and maintainer sign-off.
  The decision table and Real-CI guard stay authoritative: the pass only
  appends `high_confidence` / `low_confidence` / `fell_through` records to
  `.apache-magpie-local/logs/pr-triage-typed-decision.jsonl`, and any
  missing credential, approval, or network error falls through without
  affecting triage (#1403).
- **The fold timestamp is untrusted input to stats.** The
  `pr-triage-fold` block lives in the PR body, which the author controls.
  `tools/pr-management-stats/reference.py` (`fold_triaged_at`) treats an
  unparsable or timezone-naive `triaged=` value as no fold event rather
  than crashing the run, and tries every marker, so a malformed one above
  the real block cannot hide it (`tests/test_fold_parsing.py`).
- **Active-maintainer cooldown spans every feedback surface.**
  `pr-management-triage` steps back from a PR whose most recent feedback —
  a general comment, a review-thread comment, or a submitted top-level review
  whose body is non-empty after stripping whitespace — came from a maintainer,
  was posted after the latest author push, and is less than 72 hours old.
  Regression cases: the F5a tests in
  `tools/pr-management/tests/test_triage_classify.py`.
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
- **A green rollup is not evidence CI ran.** `statusCheckRollup.state ==
  SUCCESS` aggregates only completed check-runs, so a PR whose real
  workflows sit in `action_required` — awaiting approval for a
  first-time contributor — reports SUCCESS while nothing was built,
  linted, or tested, and fast bot checks (Mergeable, WIP, DCO,
  boring-cyborg) that succeed unconditionally are enough to carry it
  there. Both `pr-management-triage` and `pr-management-code-review`
  therefore run a mandatory Real-CI guard before any row classifies a
  PR as passing. A PR whose real CI never ran is as ineligible for
  APPROVE as one that fails, sorts below every PR with a real run when
  a queue is ordered, and is reported as *CI unverified* rather than
  having its outcome predicted.
- **A posted review is confirmed, never retried.** `gh pr review` prints
  nothing on success, so an empty result must not be read as failure: a
  zero exit means the review posted whatever it printed. Before any
  retry the skill confirms the post-condition through the reviews API,
  because a duplicate cannot be withdrawn — GitHub deletes only pending
  reviews, and `DELETE /repos/{owner}/{repo}/pulls/{n}/reviews/{id}`
  answers `422 Can not delete a non-pending pull request review` once
  submitted, leaving the body edited down to a pointer as the only
  repair. The same rule covers `gh pr comment` and the
  `addPullRequestReview` mutation.
- **Adversarial second read in code review.** `pr-management-code-review`
  offers two paths at Step 5 of `review-flow.md`.
  The tool path — `with-reviewers:codex,copilot`, or a resolved
  `adversarial-review.md` whose `mode` is not `off` — has the agent run the
  [adversarial-review](adversarial-review.md) tool over `--target pr:<N>`
  from an empty temporary directory created once per session, because the
  skill has no checkout of the PR's head and the maintainer's own checkout
  must not be readable by other models.
  Its findings fold into the Step 4 list, attributed per reviewer, as
  untrusted data.
  The slash path — `with-reviewer:<command>` or a *Review preferences*
  entry — still proposes a command for the maintainer to type.
  `no-adversarial` turns both off for the session.
  On a private `<upstream>` the skill asks before the first tool run; exit
  code 2 skips the tool path for the rest of the session; prefetched PRs get
  Step 5 from the parent, since subagents have no shell.
  The resolution order is in `prerequisites.md` §2 and pinned by the
  `step-2-reviewer-resolution` eval suite.
- **A stack is reviewed as structure first, code by tier.**
  `pr-management-stack-review` answers chain, ordering, duplicate and
  trunk-drift questions for every file of the stack deterministically,
  and reads code only where the ledger points (overlap files, seam hits,
  outlier hunks, small semantic layers in full, one exemplar per repeated
  shape otherwise). Every report and comment carries the script-rendered
  coverage table; a sampled layer is never called reviewed. `blocking`
  requires deterministic or head-verified evidence. The skill emits no
  `APPROVE` or `REQUEST_CHANGES`; layer approval stays with
  `pr-management-code-review`, which the stack report names per layer.
  Regression cases: `tools/skill-evals/evals/pr-management-stack-review/`.
- **Config-driven, not skill-edited.** Project-specific values
  (committers team handle, area-label prefix, comment-template wording,
  CI-check → doc-URL map, review criteria, quick-merge path globs) all
  live in `<project-config>/` files; no skill body carries a project
  hardcode.
  Review footers and the triage comment templates link the contributing
  guide through `<upstream_contributing_docs_url>` from `project.md`, not a
  fixed project's docs path (#1407).

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
9. When `backport_branches` is configured, `pr-management-triage` classifies
   every open backport PR as a direct cherry-pick, an adapted backport, a
   policy violation, already landed, or unverified before the main flow,
   and never proposes handing off a change that is not a fix under
   `backport_policy: fixes-only`.
10. `pr-management-stack-review` never posts a review event, posts at most
    one comment per stack (updated in place on re-runs), and renders the
    coverage table in every report; its eval suite pins the Step 1 gate,
    the Step 3 finding table, the Step 4 tier plan and the Step 6 posting
    rules.

## Validation

```bash
test -f .agents/skills/magpie-pr-management-triage/SKILL.md
test -f .agents/skills/magpie-pr-management-stats/SKILL.md
test -f .agents/skills/magpie-pr-management-code-review/SKILL.md
test -f .agents/skills/magpie-pr-management-quick-merge/SKILL.md
test -f .agents/skills/magpie-pr-management-stack-review/SKILL.md
tools/dev/run-skill-script-tests.sh
test -f .agents/skills/magpie-pr-management-mentor/SKILL.md
test -f docs/pr-management/README.md
uv run --all-packages --group dev pytest tools/pr-management-stats/tests
uv run --all-packages --group dev pytest tools/pr-management/tests
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
- **Stale-PR handling lives in two places.** Stale sweeps
  (`stale-draft`, `inactive-open`, `stale-review-ping`) run as Step 5 of
  the triage flow and can be invoked standalone via `triage stale`.
  A standalone `pr-stale-sweep` skill has since shipped in the same plugin
  (draft-or-close proposals on confirmation), so the earlier note that no
  separate stale-sweep skill was planned is superseded; how the two divide
  the surface is not written down in one place.
- **`pr-management-mentor` is documented under Mentoring mode** and is
  listed in `docs/mentoring/README.md`. The PR management README
  cross-references it as a companion skill; adopters wanting PR-thread
  mentoring enable it alongside the triage suite.
