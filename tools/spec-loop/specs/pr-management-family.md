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
  - pr-management-merge-candidates never merges autonomously; it surfaces
    candidates and the exact merge command for the maintainer.
  - pr-management-thread-mentor never posts without explicit maintainer
    confirmation; its output is pedagogical, never gatekeeping.
  - No pr-management body @-mentions anyone but the PR author and the
    project's merged mention_allowlist; the agent-guard mention guard
    refuses the rest on every posting surface.
  - All family skills validate under skill-and-tool-validate with no errors.
  - docs/pr-management/README.md lists the family's skills.
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
  The skill runs its bundled scripts (`pr_link.py` and the pre-filter) as
  `<skill-dir>/scripts/…`, because `<framework>` on a marketplace install
  holds no `skills/` directory (#2063).
- Skill: `pr-management-stats` — read-only dashboard of the open PR
  backlog, grouped by area label, age bucket, and triage state. No tracker
  state is mutated. Ships `mode: Triage` + `capability: capability:stats`
  + `experimental`. Backed by `tools/pr-management/` (`pr-management stats build`).
  Since #1572 the whole dashboard is built as code over reads saved with
  `vetted-op-read --save`: `stats build` emits the HTML (or the Markdown
  fallback), the health rating, the recommendations, the summary and the
  exact gist-publish command; the skill is a router plus `panels.md`, read
  only when a maintainer asks what a panel means.
  Triage markers, bot detection and maintainer detection come from the same
  modules `pr-management-triage` uses, so both agree on what "triaged" means.
- Skill: `pr-management-code-review` (`code-review/`) — deep, line-aware
  code review one PR at a time; applies project criteria and drafts an
  `APPROVE` / `REQUEST_CHANGES` / `COMMENT` review with inline comments;
  posts on maintainer confirmation. Ships `mode: Triage` + `experimental`.
  Selection, scans, the slop threshold, disposition, inline anchoring and the
  review payload run as code in `pr_management.code_review`; the agent judges
  H1/H5/S2, writes the findings and assigns severity.
  The `pr:` selector names one PR or several (#2055): `pr:N,M`, inclusive
  ranges `pr:N-M`, optional `#` prefixes and repeated `pr:` tokens, with
  duplicates dropped and at most 50 PRs; the queue keeps the order the
  maintainer named, and a named PR missing from the open-PR sweep is listed
  under `not_open`.
  The selector output keeps `pr_number` (set when exactly one PR is named)
  beside `pr_numbers`.
  `code-review session record --outcome` accepts `FIXUP` beside the three
  review events and the `skipped` / `slop-comment` / `slop-close` /
  `dry-run` outcomes, and the session summary counts it as a review (#2056).
  An inline comment carries the finding as the review body does (its
  `quoted_rule` and `suggestion`), minus the excerpt it is anchored on, and
  a folded finding falls back to its suggestion before its rule, never the
  bare rule label (#1853).
  A finding that has both keeps its explanation and its suggestion, on both
  surfaces (#1987).
  Detail files include
  `prerequisites.md`, `review-flow.md`, `review-loop.md`, `criteria.md`,
  `adversarial.md`, `posting.md`, one file per outcome under
  `classifications/` and per category under `criteria/`.
  `code_review/runs.py` reads the workflow runs held at a PR head and plans
  their release for the auto-merge path.
  Under Claude Code the plugin also ships a mod,
  `plugins/magpie-pr-management/hooks/review-findings.ts`, wired through
  `hooks/hooks.json` with its types in `hooks/types.ts` and `types.d.ts`
  (#1920, #1954, #1992).
- Skill: `pr-management-stack-review` (`stack-review/`) — stack-level review
  of a GitHub stacked pull request. Resolves the stack from a member PR or
  its stack number, fetches the layer heads into `refs/magpie-stack/<S>/*`
  (proposed once, cleaned up at the end), and runs the detectors in
  `tools/pr-management` (`pr_management.stack_review.stack_ledger`: file-by-layer
  matrix, hunk-shape mechanical detection, outliers, duplicate release notes,
  regenerated generated files, lock-without-manifest, reading plan and coverage
  table; `stack_chain`: chain currency, merge commits, trunk drift,
  removed-definition seams at the layer's own head, later heads and new trunk
  uses); resolve, findings mapping, verdict and posting are
  `pr-management stack-review` subcommands. Code is read by tier; the report carries the coverage
  table. Posts one rolling `COMMENT` on the lowest open layer (marker,
  updated in place) and never a review event. Ships `mode: Triage` +
  `experimental`. Detail files: `tiers.md`, `report.md`, `adopter-config.md`,
  `invocation.md`, and one file per finding class / verdict / step outcome
  under `classifications/`; tests under `tools/pr-management/tests/stack_review/`.
- Skill: `pr-management-merge-candidates` — read-only express-lane screener
  for trivial, low-risk PRs (docs, changelog, translations, tests) that
  pass every quality gate; surfaces ranked candidates with diff summaries
  and the exact merge command. Never merges autonomously. Ships `mode:
  Triage` + `experimental`.
  The screen runs as code (`pr-management quick-merge screen` / `approve-check`)
  over reads saved with `vetted-op-read --save`; one file per gate, bucket,
  tier and drop reason under `classifications/`, and
  `actions/{present,approve,hand-off}.md`.
- Skill: `pr-management-thread-mentor` — drafts a teaching-register comment on a
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
  `pr-management-thread-mentor`, `reviewer-routing` and `pre-first-pr-check` run their
  rules in `tools/pr-management` (`mentor assess|render|tone-check|log`,
  `reviewer-routing preflight|propose`, `pre-first-pr check|report`); their
  detail files are per-classification under `classifications/`.
- Family README: `docs/pr-management/README.md` — family overview and skill
  table; `docs/pr-management/install.md` (*Install & first runs*) — the
  `/plugin install` line, the generated *Before the first run* config table,
  *Works well with* and *Try these first*.
- Tool: `tools/pr-management/` (`pr_management.stats`) — deterministic Python backing for
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
  — never writes to a PR or the tracker; its one write is publishing the
  dashboard to a secret gist on the maintainer's own account, proposed and
  run on confirmation (skipped under `dry-run` or `markdown`). The publish
  command is assembled with `shlex.join`, and a stored gist id must be hex,
  so agent-writable session state cannot inject shell syntax (#1572).
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
  `@`-mention and the project's `mention_allowlist`.
  Regression cases: `tools/pr-management/tests/`.
- **Mentions are allowlisted, and the guard enforces it.** Every
  pr-management renderer (triage notes, stale-sweep comments, mentor comments,
  code-review bodies) keeps only the PR author's `@`-mention live and
  backtick-quotes every other handle, except handles and teams listed in
  `mention_allowlist` in `pr-management-config.md` (#1584).
  The agent-guard `mention` guard checks `gh pr|issue comment`, folded notes,
  `gh pr review --body/--body-file`, and every value a non-GET `gh api` call
  sends (each `-f` / `-F` / `--raw-field` / `--field` spelling, `@file`
  reads, `--input`); text it cannot read is refused rather than passed
  (#1579).
  The guard takes the allowlist, and the mentoring hand-off's
  `maintainer_team_handle`, only from `.apache-magpie-overrides/` as GitHub
  serves it from the target repository's default branch — never the local
  checkout — so only a reviewed, merged change widens what may be mentioned.
  The target must be explicit and unambiguous (`--repo` in any spelling,
  including attached `-R`, and/or a PR or issue URL selector, all agreeing,
  or a plain `repos/OWNER/REPO/…` endpoint); arguments are parsed by flag
  arity, an unreadable line names no target, and GraphQL writes get no
  allowlist.
  The hand-off team is allowed alone, in a body that opens with the hand-off
  template's line, and only for a team of the organisation owning the target.
  One call can add a handle with `--allow-mention <login>` paired with
  `MAGPIE_ALLOW_MENTIONS=1` on the posting command (#1584).
- **Session-local history and guarded recovery.**
  `pr-management-triage` journals intent before every operation and verifies its outcome afterwards, including compound actions, skipped PRs and actions without notes.
  A new structured `action_log` lives beside the existing `prs` cache; neither the history gist nor its pointer file is parsed as action evidence.
  `[H]istory` revisits any recorded PR in the saved session while `[B]ack to group` retains its navigation meaning.
  Reclassify bypasses only the selected PR's session suppression, never normal safety rules.
  Recovery proposes exact inverse operations newest-first on each PR, checks current state and confirmation, preserves unrelated author text and records partial progress.
  Exact comment IDs, ownership and update times are required for comment deletion; unknown outcomes, moved heads, merged PRs and conflicting edits block rather than guess.
  Already-sent notifications, workflow approvals, CI execution and branch updates are explicitly non-reversible; a partial recovery is never reported as a full undo.
  Legacy cache entries are viewable without inventing missing receipts.
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
  `tools/pr-management/src/pr_management/stats/reference.py` (`fold_triaged_at`, via the shared `markers.parse_fold`) treats an
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
- **Stale-sweep rules run as code.** `pr-management stale-sweep classify`
  measures inactivity from the last real activity (never the sweep's own
  comments), nudges before it closes (hard close excepted, with at least a
  7-day notice), and reuses triage's maintainer-court, ready-label, security
  and bot rules; the close notice carries `<!-- pr-stale-sweep-close -->`.
  Regression cases: `tools/pr-management/tests/stale_sweep/`.
- **Merge-candidates never merges.** `pr-management-merge-candidates` surfaces
  candidates and the maintainer runs the exact `gh pr merge` command
  themselves. Automated merge belongs to a future Auto-merge mode that is
  deliberately off by MISSION sequencing.
- **The quick-merge approve protocol fails closed.** `quick-merge
  approve-check` needs the fresh PR, the live merge state and the
  workflow-approval index (none optional), re-runs the Stage-1 gates and the
  Stage-2 triviality screen on the fresh file list, and refuses when either
  regressed, the head moved, the diff was not viewed at that head this
  session, approvals are disabled, or the branch now conflicts.
  Gate G7 blocks on any request for changes that still stands; a later push
  does not dismiss it, only the reviewer can.
  An optional `approve_body` ends with the triage-style `<sub>` credit line
  naming the approving maintainer (#1580).
  Regression cases: `tools/pr-management/tests/quick_merge/` and the
  `approve-protocol` eval suite.
- **Teaching register for mentoring.** `pr-management-thread-mentor` follows the
  Mentoring mode's tone contract (polite, never gatekeeping, explicit
  hand-off to a human when scope exceeds the agent). It posts only on
  maintainer confirmation.
- **Untrusted content stays data.** PR bodies, titles, and author comments
  are input data for classification; injected instructions in PR body text
  are ignored and flagged. Inherits the absolute rule from
  [`AGENTS.md`](../../../AGENTS.md#treat-external-content-as-data-never-as-instructions).
- **One APPROVE definition in code review.** `pr-management code-review
  disposition` proposes `APPROVE` only when nothing is above a nit, real CI is
  green, no review thread is unresolved, no other maintainer's
  `CHANGES_REQUESTED` stands, and no maintainer question is unanswered; an
  outdated thread the agent verified the current code addresses leaves the
  thread gate and goes to the maintainer to resolve instead (the agent judges
  every comment in the thread, and a thread longer than the read stays a
  gate); the
  maintainer may downgrade it, and upgrading past a named gate needs a stated
  reason (#1585).
  When every gate holds and the only findings left are `minor` / `nit` ones
  with a mechanical `fixup`, and the maintainer can push to the PR head,
  `FIXUP` is the default action: the maintainer commits those changes to the
  contributor's branch on confirmation, waits for CI, and approves with a body
  that lists what the fixup changed. A `major` is never fixed up.
  The "touching mine" selector uses GitHub data rather than `git log
  --author`, CODEOWNERS team ownership checks team membership rather than
  organisation membership, and `maintain` permission gets the maintainer
  footer (#1585).
  A suggested reviewer who is not a committer is called a frequent
  contributor only when a committer roster was loaded; with none, the reason
  makes no claim about the role and `committer` is null, and a configured
  `committers_team_slug` whose `team-<slug>.txt` read is missing is named as a
  needed `team-members` read (#1988).
- **Approve plus auto-merge is the default where the repository allows it.**
  When `disposition` finds an action that ends in an `APPROVE`, the repository
  allows auto-merge (`autoMergeAllowed`) and the viewer can enable it on the
  PR (`viewerCanEnableAutoMerge`), the default becomes `APPROVE+AUTO-MERGE`,
  or `FIXUP+APPROVE+AUTO-MERGE` when a fixup is the default; `auto_merge`
  carries the eligibility, its reason and the method (#1951).
  It is never eligible on a self-authored PR, on one that already has
  auto-merge enabled, on a branch that conflicts or has no computed merge
  state, or when the saved read names no viewer to check self-authorship
  against (#1960).
  Elsewhere merging stays a separate confirmed action.
  Real CI that is still running stops being a gate on this path, because
  GitHub holds the merge until the required checks pass, but only when every
  running check is a required one; a running check that is not required keeps
  the gate, since auto-merge would not wait for it.
  Its `ci_action` says to wait for those checks, or to approve their held
  runs through `pr-management-triage`, because `release-runs` needs the
  approval this gate withholds (#2029).
  With CI held this way (`ci_pending_held_by_auto_merge`) plain `APPROVE` and
  `FIXUP` are not offered, because without auto-merge they would approve on
  unfinished CI.
  Failing CI, a rollup green from bot checks only, and workflows waiting for
  approval stay gates, and `ci_action` names what to approve or re-run first.
  A rollup is used only when its commit is the PR's head commit; when the
  installed vetted-ops queries do not return that commit's oid, the rollup is
  dropped, the headline says CI cannot be verified, and `ci_action` names the
  vetted-ops upgrade. Before an approval is emitted, disposition performs secondary
  confirmation of real CI on the head commit via check-runs, failing closed if no
  real CI runs are recorded (#2034).
  The maintainer's confirmation of the disposition covers the auto-merge
  write, and the prompt names it.
  After the approval posts, the skill refreshes the liveness read, re-runs
  `guard` and stops on a head nobody reviewed.
  `code-review release-runs` then releases the runs held in `action_required`
  at the head, and only on a head the viewer has an `APPROVED` review on, or
  a single commit on top of it signed by the viewer alone; a released run
  executes that head's code in CI.
  `render --auto-merge` re-runs the disposition gates, refuses a viewer that
  disagrees with the saved read, and emits `gh pr merge --auto
  --match-head-commit <reviewed head>`, so a later push cannot ride the
  approval into a merge; the method is the repository's
  `viewerDefaultMergeMethod`, squash when unknown (#1983).
- **The findings pane is additive.** Under Claude Code, a `code-review
  disposition --findings <file>` Bash call hydrates the mod's interactive pane
  above the prompt, and the zero-token `/magpie-findings` command (`status`,
  `all`, `none`, `keep`, `drop`, `edit`) tracks per-finding actions.
  Once the maintainer curates, the mod writes the findings to
  `<file>.curated.json` (an envelope carrying the PR number and the source
  file's SHA-256) and the keep answer to `<file>.curated.keep` beside the
  findings file; the first `disposition` run writes neither, and a write
  failure, empty findings or a PR mismatch writes an invalidation marker
  instead, since the mod API cannot delete files (#2005).
  It refuses to write through a symlink or a non-regular file.
  `render` uses `<file>.curated.json` only when its PR and source hash
  match, else the original findings; a curated envelope passed directly
  must pass every check or the run stops.
  An answer typed at the picker still wins; an empty answer is passed as
  `--keep curated`, which uses `<file>.curated.keep` only when the curated
  findings were used, and `A` otherwise.
  Runtimes without mods keep the text picker alone, and Codex reads the clean
  `hooks/codex-hooks.json` instead (#1992).
- **Third-party licence scan reads only real copyright notices.**
  `scans.third_party_licences` treats an added file as third-party code when
  the first 25 lines carry a licence identifier or block and either a
  copyright line naming someone other than the ASF or an "adapted / derived /
  ported / copied / vendored from" note; it then reports Category X and B
  licences as `blocking` and a Category A licence as `major` when
  `LICENSE` / `LICENSE.txt` was not updated.
  A copyright notice has to open its line (after comment markers, optionally
  "Portions"), so the ASF header's mid-line "regarding copyright ownership"
  never marks a file carrying `SPDX-License-Identifier: Apache-2.0` and the
  full ASF header as third-party (#1777).
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
  with `--repo-dir` set to a new temporary directory holding an export of
  the PR's head, made per PR, because the maintainer's own checkout
  must not be readable by other models and with an empty directory the
  reviewers reply without findings (#1986).
  The export goes through a temporary index (`git read-tree` plus
  `git checkout-index`), not `git archive`, so paths marked `export-ignore`
  stay in it (#2030).
  It drops `.apache-magpie-overrides/tools/vetted-ops`, which the
  secure setup denies writes to, so the agent reviews a PR's policy change
  itself.
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

- **Auto-merge without a human.** No skill in this family merges, closes, or
  approves without a human confirmation in-session.
  `pr-management-code-review` enabling GitHub's auto-merge on a PR the
  maintainer just approved is that confirmed action, not an exception.
  Agent-decided merging belongs to the Agentic Autonomous mode (deliberately
  off per MISSION sequencing).
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
2. `pr-management-merge-candidates` surfaces candidates with the merge command
   but never executes the merge autonomously.
3. `pr-management-thread-mentor` posts only on explicit maintainer confirmation
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
11. No pr-management renderer emits a live `@`-mention other than the PR
    author and the target repository's merged `mention_allowlist`, and the
    agent-guard `mention` guard refuses any other mention on comments,
    folded notes, reviews and non-GET `gh api` writes, reading the allowlist
    only from the target's default branch on GitHub (#1579, #1584).
12. `pr-management-merge-candidates` submits an `APPROVE` only after
    `approve-check` passes on fresh reads, and refuses when any Stage-1 gate
    or the Stage-2 screen has regressed or a change request still stands
    (#1580).
13. `pr-management-code-review` proposes `APPROVE` only when the single
    disposition gate holds (no finding above a nit, real CI green or, on
    the auto-merge path, running with every running check required, no
    unresolved thread other than an outdated one the current code
    addresses, no standing change request, no open maintainer
    question) (#1585, #1951).
14. `pr-management-stats` writes nothing to any PR or tracker; its only
    write is the confirmed secret-gist publish on the maintainer's account
    (#1572).
15. `pr-management-code-review` enables auto-merge only on a confirmed
    disposition whose gates `render --auto-merge` re-ran, pinned to the
    reviewed head with `--match-head-commit`, and never on a self-authored
    PR (#1951, #1960).

## Validation

```bash
test -f .agents/skills/magpie-pr-management-triage/SKILL.md
test -f .agents/skills/magpie-pr-management-stats/SKILL.md
test -f .agents/skills/magpie-pr-management-code-review/SKILL.md
test -f .agents/skills/magpie-pr-management-merge-candidates/SKILL.md
test -f .agents/skills/magpie-pr-management-stack-review/SKILL.md
tools/dev/run-skill-script-tests.sh
test -f .agents/skills/magpie-pr-management-thread-mentor/SKILL.md
test -f docs/pr-management/README.md
uv run --all-packages --group dev pytest tools/pr-management/tests
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **`experimental` — no adopter pilot has run the full family end-to-end.**
  All nine skills are on main with eval suites; no maintainer has exercised
  the triage → stats → code-review → merge-candidates → thread-mentor pipeline
  end-to-end under evaluation conditions. Shape may change as pilot
  evaluations surface real-world usage patterns.
  <!-- gap-closes-when: none (narrative) -->
- **Stale-PR handling lives in two places.** Stale sweeps
  (`stale-draft`, `inactive-open`, `stale-review-ping`) run as Step 5 of
  the triage flow and can be invoked standalone via `triage stale`.
  A standalone `pr-stale-sweep` skill has since shipped in the same plugin
  (draft-or-close proposals on confirmation), so the earlier note that no
  separate stale-sweep skill was planned is superseded; how the two divide
  the surface is not written down in one place.
  <!-- gap-closes-when: none (narrative) -->
