<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Implementation Plan — spec-loop

Maintained by the loop's **plan** mode. It is the prioritised list of
*gaps* found by comparing [`specs/`](specs/) against the actual code
(`.claude/skills/`, `tools/`, `docs/`). The **build** mode takes the
single highest-priority work item, isolates it on its own branch,
implements it, validates it, and commits — **one work item, one branch,
one PR** (the branch-per-feature constraint).

> Priority lives here, not in the specs. The specs describe functional
> areas (unordered); this plan orders the work.

---

## What's been built

- **Spec set** — [`specs/`](specs/): an `overview` plus a functional
  spec per area (the four live modes, the security lifecycle, the
  release-management lifecycle (proposed), the privacy-LLM gate, the
  sandbox, CVE tooling, adoption/setup, adapters, project-agnosticism,
  and meta/quality tooling).
- **Loop scaffolding** — `loop.sh` (plan / build / consolidate; a branch
  per work item; never pushes), `PROMPT_plan.md`, `PROMPT_build.md`,
  `PROMPT_consolidate.md`, `AGENTS.md` (loop-scoped operational context),
  and this plan. Branch-collision guard is inline in `loop.sh`.
- **Agentic Pairing — both skills shipped** — `pairing-self-review` and
  `pairing-multi-agent-review` (three independent axis passes; eval
  suites present); `docs/modes.md` Agentic Pairing row reflects 2 skills /
  `experimental`. Spec: [`specs/pairing-mode.md`](specs/pairing-mode.md).
- **Agentic Mentoring — four skills shipped** — `pr-management-mentor`,
  `good-first-issue-author`, `mentoring-welcome`, and
  `contributor-to-committer` (eval suites present); `docs/modes.md`
  Agentic Mentoring row reflects 4 skills / `experimental`.
  Spec: [`specs/mentoring-mode.md`](specs/mentoring-mode.md).
- **Contributor skills** — `contributor-nomination`,
  `contributor-activity-sweep`, and `committer-onboarding` shipped with
  eval suites. Formerly tracked under draft PRs #227–#229.
- **Agentic Drafting — issue-fix-workflow and audit-finding-fix skills** —
  both shipped with eval suites (covers generic drafting from triaged
  issues and audit findings, formerly tracked as `generic-drafting` /
  #296). Spec: [`specs/drafting-mode.md`](specs/drafting-mode.md).
- **Docs — mode economics page** — `docs/mode-economics.md` exists
  (per-mode token-cost shape, vendor-neutral).
- **Meta — spec-status index** — `tools/spec-status-index/` exists as a
  `uv` tool that prints specs grouped by status.
  Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
- **Meta — spec validator** — `tools/spec-validator/` exists as a `uv`
  project with `pyproject.toml` and `tests/`, validating spec frontmatter
  and body sections. Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
- **Agent isolation — Python packaging + tests** — `tools/agent-isolation/`
  has `pyproject.toml`, `src/`, and a `tests/` directory with pytest
  coverage for the sandbox profiles and clean-env wrapper.
  Spec: [`specs/agent-isolation-sandbox.md`](specs/agent-isolation-sandbox.md).
- **Eval coverage — complete** — every current `skills/*/SKILL.md` has a
  matching eval suite in `tools/skill-evals/evals/`; the eval catalogue also
  includes non-skill smoke suites such as `non-asf-profile-smoke`. Coverage
  includes the full setup-family (setup, setup-isolated-setup-doctor,
  setup-isolated-setup-install, setup-isolated-setup-update,
  setup-isolated-setup-verify, setup-override-upstream,
  setup-shared-config-sync).
- **Release-management family complete** — all ten `release-*` skills landed
  with eval suites; no release-management skill remains proposed. See
  [`specs/release-management-lifecycle.md`](specs/release-management-lifecycle.md).
- **Agentic Triage — general-issue family filled out** — `issue-stale-sweep`,
  `issue-deduplicate`, and `issue-backlog-stats` shipped with eval suites
  (formerly planned general-issue triage work plus its deferred siblings).
  Spec: [`specs/triage-mode.md`](specs/triage-mode.md).
- **Contributor-to-committer readiness shipped** — the mentoring-family
  `contributor-to-committer` readiness tracker landed with an eval suite and
  is documented in the contributor-growth and mentoring family docs.
  Spec: [`specs/contributor-growth.md`](specs/contributor-growth.md).
- **Project-agnosticism — ASF-coupling advisory lint shipped** — the SOFT
  ASF-coupling category landed in `tools/skill-and-tool-validator`
  (formerly planned work item 5), and `drafting-mode.md` Known Gaps is
  synced to the shipped drafting skills (formerly planned work item 6).
- **Project-agnosticism — capability-flag vocabulary and wiring advanced** — the
  contributor/committer-intake (ICLA vs DCO), security-intake, and
  CVE-allocation option sets and defaults are enumerated as
  `projects/_template/committer-onboarding-config.md`,
  `security-intake-config.md`, and `cve-allocation-config.md`, following
  the backend-flag precedent in `release-management-lifecycle.md`.
  `security-issue-import`, `security-issue-sync`, and `committer-onboarding`
  have begun reading those flags; remaining adopter-pilot feedback is tracked
  in the specs, not as an immediate build item here.
  Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
- **Repo-health family complete** — `ci-runner-audit`,
  `workflow-security-audit`, `dependency-audit`, `license-compliance-audit`,
  and `flaky-test-triage` landed (read-only, `experimental`).
  Spec: [`specs/repo-health-family.md`](specs/repo-health-family.md).
- **Reviewer routing shipped** — `reviewer-routing` landed with an eval suite,
  filling the first reviewer-routing spec build item. Remaining work is spec /
  docs cleanup for the shipped state and later adopter-pilot feedback.
  Spec: [`specs/reviewer-routing.md`](specs/reviewer-routing.md).
- **Skill reconciler shipped** — `skill-reconciler` landed with an eval suite,
  implementing the cross-project comparison workflow. Follow-on gaps are the
  optional deterministic structural-diff helper and source-tag auto-pairing,
  both deferred. Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
- **Project-agnosticism cleanup shipped** — high-confidence ASF-coupling
  advisories, criteria-source advisories, and action-inventory advisories were
  cleared from the relevant skills; organization metadata, governance
  vocabulary, disclosure-governance flags, and source-control abstraction work
  also landed. Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
- **Good-first-issue sweep implemented off main** — `origin/good-first-issue-sweep`
  carries the `good-first-issue-sweep` skill and eval suite. It is tracked as
  in-flight below until that PR lands on `main`.

---

## In-flight (local branches and open PRs — not available to build)

The following items are already built on local branches or open as PRs.
Do not duplicate them.

| Branch slug | PR | Description |
|---|---|---|
| `good-first-issue-sweep` | open | `good-first-issue-sweep` skill + eval suite; keep out of the build queue until the PR lands or is explicitly abandoned. |

The previous in-flight batch (non-ASF adopter profile fixture,
reviewer-routing, skill-reconciler, release-management completion,
repo-health completion, high-confidence ASF-coupling cleanup, criteria-source /
action-inventory advisory cleanup, organization metadata, governance vocabulary,
and adapter-discovery docs) has merged to `main` and is reflected in
**What's been built** above.

---

## Work items (planned)

Priority order. Each maps to one branch and one PR. Branch names are
slugs, not numbers (numbering implies an order the specs don't carry).

1. **Sync shipped-state specs after the recent merge train.**
   Several specs still carry pre-merge language even though the code has
   shipped. Update `specs/reviewer-routing.md` and
   `specs/skill-reconciler.md` so their **Where it lives** and **Known gaps**
   sections describe the shipped skills instead of saying "proposed, not
   implemented"; update `specs/overview.md` so reviewer routing and the
   reconciler are listed as `experimental`; refresh
   `specs/meta-and-quality-tooling.md`'s shipped-skill/eval count; and verify
   `specs/project-agnosticism.md` / `specs/issue-management-family.md` no longer
   advertise already-cleared gaps (high-confidence ASF-coupling backlog,
   unwired governance-member terminology, missing issue-management rows in
   `docs/modes.md`).
   Validation:
   ```bash
   uv run --project tools/spec-status-index spec-status --ready
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   ```
   Branch `spec-shipped-state-sync`.

2. **Post-merge sync for good-first-issue-sweep.**
   Once the `good-first-issue-sweep` PR lands on `main`, remove it from the
   in-flight table and sync every shipped-state surface: flip
   `specs/good-first-issue-sweep.md` from `proposed` to `experimental`,
   update `specs/overview.md`, add the skill to `docs/modes.md` and the
   mentoring / contributor-growth family docs, and update the eval-coverage
   counts if they are still numeric. This item is intentionally blocked until
   the PR lands; do not duplicate the branch implementation.
   Validation:
   ```bash
   test -f skills/good-first-issue-sweep/SKILL.md
   test -d tools/skill-evals/evals/good-first-issue-sweep
   uv run --project tools/spec-status-index spec-status --ready
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   ```
   Spec: [`specs/good-first-issue-sweep.md`](specs/good-first-issue-sweep.md).
   Branch `good-first-issue-sweep-post-merge-sync`.

3. **Clear the mechanical SOFT validator warnings.**
   Handle the current non-judgement soft warnings that have obvious local
   remedies: add the missing Privacy-LLM gate preflight to
   `reviewer-routing`, add an explicit bounded `--limit` to the
   `security-issue-import` `gh issue list` call, and replace the
   `release-prepare` inline `--body "..."` usage with a `--body-file` flow.
   Leave ASF-coupling warnings out of this item; those require human
   judgement and are tracked separately below.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/reviewer-routing/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/security-issue-import/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-prepare/
   ```
   Branch `mechanical-soft-warning-cleanup`.

4. **Low-confidence ASF-coupling judgement pass.**
   The high-confidence coupling backlog is clear, but the validator still
   reports low-confidence `asf-coupling` warnings such as bare governance
   terms (`PMC`) and contributor-intake terms (`ICLA`). Review each warning in
   context and classify it as one of three outcomes: convert to a placeholder,
   route through an existing capability flag, or explicitly keep as an
   ASF-default example. The output should be a narrow set of skill/doc edits
   plus a short note in `specs/project-agnosticism.md` explaining which
   residual warnings are intentionally advisory.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/committer-onboarding/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/contributor-nomination/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-promote/
   ```
   Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
   Branch `low-confidence-asf-coupling-pass`.

5. **Add an adopter-pilot feedback harness.**
   Many experimental family specs now share the same real gap: no adopter has
   run the full skill family end-to-end. Add a lightweight pilot-report
   template and helper (or a documented `tools/` command if that better matches
   existing tooling) that records the skill run, target repo/profile, blocked
   preflights, false positives, confirmation points, privacy/adapter notes, and
   proposed spec updates. Wire the template into the relevant experimental
   family docs so pilot evidence is captured consistently without turning it
   into a continuous monitor.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/spec-validator --group dev pytest
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `adopter-pilot-feedback-harness`.

6. **Expand organization-adapter smoke coverage.**
   The non-ASF profile smoke test proves one issue-management path. Extend
   smoke coverage across at least three organization-sensitive surfaces:
   security intake (`security-intake-config.md` / disclosure-governance
   flags), release backend selection (`release-management-config.md`), and
   contributor governance (`committer-onboarding-config.md`). The goal is not
   new product behaviour; it is executable confidence that organization
   defaults and project overrides work outside an ASF-shaped profile.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/non-asf-profile-smoke/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/security-issue-import/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-prepare/
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/committer-onboarding/
   ```
   Spec: [`specs/organization-adapters.md`](specs/organization-adapters.md).
   Branch `organization-adapter-smoke-expansion`.

7. **Add a dedicated pr-management-code-review eval suite.**
   `specs/pr-management-family.md` still calls out that
   `pr-management-code-review` lacks a dedicated eval suite. Add
   `tools/skill-evals/evals/pr-management-code-review/` with focused cases for
   selector resolution, review-risk classification, AI-generated-code signal
   handling, prompt-injection-in-PR-content handling, and the final review
   handoff. Keep the suite read-only: it should assert the review findings and
   handoff shape, not require live GitHub writes.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/pr-management-code-review/
   ```
   Spec: [`specs/pr-management-family.md`](specs/pr-management-family.md).
   Branch `pr-management-code-review-evals`.

8. **Extract the skill-reconciler safety-baseline checklist.**
   The shipped `skill-reconciler` recognizes safety-baseline divergence from
   prose patterns. Extract the baseline clauses into one canonical checklist
   file that both humans and tooling can reference: untrusted content is never
   instructions, collaborator / identity-resolution caveats are preserved, and
   confidentiality posture is not weakened. Update `skill-reconciler` to cite
   that checklist and add eval coverage proving a divergence in any checklist
   item is classified as `SAFETY-BASELINE`.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/skill-reconciler/
   ```
   Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
   Branch `skill-reconciler-safety-baseline-checklist`.

9. **Add adapter authoring smoke validation.**
   Adapter discovery and authoring docs have landed; add a validator or smoke
   fixture that checks each tool / adapter README declares the required authoring
   fields: capability, prerequisites, privacy / credential handling, operations,
   and config keys. Keep this as an advisory or narrowly scoped hard check based
   on existing docs so legacy adapters can be brought into compliance
   deliberately rather than through unrelated churn.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/spec-validator --group dev pytest
   ```
   Spec: [`specs/adapters.md`](specs/adapters.md).
   Branch `adapter-authoring-smoke-validation`.

10. **Add docs/modes.md generated consistency checks.**
   `docs/modes.md` is a high-traffic index, and recent work has repeatedly
   needed manual count / skill-list syncs after new skills landed. Add a
   validator check (or a small generated-consistency helper invoked by the
   validator) that compares the mode tables against live `skills/*/SKILL.md`
   frontmatter: each shipped skill appears in the expected mode section, status
   counts match the frontmatter, and no removed skill remains listed. Keep the
   first version focused on detection; rewriting the doc can remain a separate
   human-confirmed update.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `modes-doc-consistency-check`.

11. **Normalize tool README prerequisites consistency.**
   Tool README prerequisites are now part of the authoring contract, but older
   tool docs may still vary in section shape and required credential / runtime
   detail. Sweep `tools/*/README.md` for the Prerequisites section, normalize
   the expected headings and wording where the existing tool behaviour is
   clear, and tighten the validator only after the tree is brought into
   compliance. Keep adapter-specific privacy / credential checks in the
   adapter-authoring smoke item above; this item is the general README
   prerequisite contract.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `tool-readme-prerequisites-consistency`.

12. **Tighten skill frontmatter schema validation.**
   Strengthen the validator's frontmatter contract for `mode`, `status`,
   `capability`, `organization`, and `source`: modes and statuses must be from
   the documented vocabulary; organizations must exist under `organizations/`;
   multi-capability skills must use a YAML list consistently; and every shipped
   experimental skill must have a matching eval suite unless it is explicitly
   exempted with a documented reason. Keep the first pass focused on fields the
   current tree can satisfy after local cleanup.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `skill-frontmatter-schema-tightening`.

13. **Add project-template drift checks.**
   Add a validator or smoke tool that compares `projects/_template/` with
   `projects/non-asf-example/` for structural drift: required config files are
   present, documented keys exist in both profiles when applicable, template-only
   keys are either copied or intentionally explained, and organization-inherited
   defaults do not hide missing adopter-required values. The check should catch
   stale template docs without forcing the example to mirror ASF-specific values.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/non-asf-profile-smoke/
   ```
   Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
   Branch `project-template-drift-check`.

14. **Add override-file contract tests.**
   Document and test the `.apache-magpie-overrides/<skill>.md` contract: override
   files are additive project guidance, agent-readable Markdown, and never a
   replacement for the framework safety / confidentiality baseline. Add a
   validator or smoke fixture that flags override text attempting to weaken the
   baseline and confirms a clean override can be discovered and surfaced to a
   skill without editing the upstream skill body.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md).
   Branch `override-file-contract-tests`.

15. **Add capability taxonomy coverage checks.**
   Validate that every `capability` declared in skill frontmatter and tool
   READMEs is documented in `docs/labels-and-capabilities.md`, and that every
   capability in the taxonomy maps to at least one skill/tool or is explicitly
   marked reserved / future. The check should catch misspellings and stale
   taxonomy rows without requiring every capability to have both a skill and a
   tool implementation.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `capability-taxonomy-coverage-check`.

16. **Define the release audit report schema.**
   `release-audit-report` exists, but downstream review would benefit from a
   structured audit-record schema. Add a template/schema for the required audit
   fields (release version, RC artefacts, vote thread, tally outcome, promotion
   revision, announcement URL, archive state, and any follow-up notes), update
   the skill to reference it, and add eval fixtures that reject incomplete audit
   records while preserving the human-reviewed nature of the report.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-audit-report/
   ```
   Spec: [`specs/release-management-lifecycle.md`](specs/release-management-lifecycle.md).
   Branch `release-audit-report-schema`.

17. **Add mail-adapter privacy-boundary tests.**
   Add smoke tests or validator fixtures for Gmail, PonyMail, `mail-archive`,
   and any `mail-source` adapter path proving private mail content is redacted,
   summarized, or routed through the Privacy-LLM gate before it enters
   model-facing skill context. The test should treat fetched mail as external
   data and include at least one prompt-injection-in-email fixture to preserve
   the repository's data-not-instructions rule.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/spec-validator --group dev pytest
   ```
   Spec: [`specs/adapters.md`](specs/adapters.md).
   Branch `mail-adapter-privacy-boundary-tests`.

18. **Add branch-name confidentiality validation.**
   Add a validator check or deterministic helper that scans generated branch
   name examples in skills/docs and rejects embargo-breaking terms: CVE IDs,
   `security`, `vulnerability`, `advisory`, and tracker-private title fragments.
   Align the check with the existing security-fix workflow guidance so public
   branch names stay neutral before disclosure.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-and-tool-validator --group dev pytest
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/security-issue-fix/
   ```
   Spec: [`specs/privacy-llm-gate.md`](specs/privacy-llm-gate.md).
   Branch `branch-name-confidentiality-validation`.

19. **Add the deterministic structural-diff helper for skill-reconciler.**
   The shipped `skill-reconciler` reasons over a prose comparison report.
   Add the optional `tools/` helper sketched in
   `specs/skill-reconciler.md`: parse two skill trees into a normalized
   structural diff (frontmatter, section headings, step inventory,
   placeholder inventory, and linked support files) so the skill can ground
   `ALLOWED` / `DRIFT` / `SAFETY-BASELINE` decisions in a deterministic
   object. Keep the reconciler read-only; the helper emits data only.
   Include unit tests for frontmatter-only, section-order, placeholder, and
   support-file divergences, plus one safety-baseline fixture that proves the
   helper preserves the clauses the skill must classify.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/skill-reconciler/
   uv run --project tools/skill-reconciler-diff --group dev pytest
   ```
   Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
   Branch `skill-reconciler-structural-diff`.

20. **Add source-tag auto-pairing to skill-reconciler.**
   The first implementation takes two explicit paths. Extend the skill so
   a maintainer can ask it to discover near-duplicate skills by `source`
   tag / capability metadata and present a bounded candidate pair list
   before running the comparison. Preserve explicit-path mode as the
   default and require confirmation before comparing any discovered pair,
   so the skill remains read-only and predictable.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/skill-reconciler/
   ```
   Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
   Branch `skill-reconciler-source-pairing`.

21. **Bring legacy adapter READMEs into adapter-authoring compliance.**
   The adapter-authoring smoke check (work item 9, shipped on
   `adapter-authoring-smoke-validation`) now flags 10 SOFT advisories across 9
   `contract:*` adapter READMEs that are missing a required authoring field.
   Bring each into compliance by adding the missing section/reference (or
   documenting why the field legitimately does not apply, once an opt-out
   convention exists). Missing **config-keys** (a `## Configuration` section,
   a `project-config` / `*-config.md` reference, or an inline
   `tools.<adapter>.<key>` knob): `apache-projects`, `cve-org`, `github`,
   `github-body-field`, `github-rollup`, `ponymail`, `vcs`, and
   `cve-tool-vulnogram`. Missing **operations** (an `## Operations` /
   `## Interface` / `## Invocation` / `## How to use` section or a `tool.md`
   reference): `cve-tool-vulnogram` and `mail-source`. Several are thin
   backend adapters whose real docs live in their contract README, so prefer a
   one-line pointer to the contract over duplicating prose. The two former
   false positives (`cve-tool` credential delegation, `gmail` inline config
   key) are already resolved by broadening the validator matchers and are not
   part of this item.
   Validation:
   ```bash
   uv run --directory tools/skill-and-tool-validator skill-and-tool-validate
   uv run --directory tools/skill-and-tool-validator --group dev pytest
   ```
   Spec: [`specs/adapters.md`](specs/adapters.md).
   Branch `adapter-readme-authoring-compliance`.

22. **Reconcile docs/modes.md with the modes-doc detection.**
   The `modes-doc-consistency-check` item added detection only; running the
   validator now surfaces two real gaps it was meant to catch. `reviewer-routing`
   carries `mode: Triage` in frontmatter but has no row in the `## Triage`
   table, and `good-first-issue-sweep` carries `mode: Mentoring` but has no row
   in the `## Mentoring` section. Add the missing `reviewer-routing` Triage row
   (with its current status), then re-run the validator to confirm the doc is
   clean. The `good-first-issue-sweep` row is already owned by the post-merge
   sync item above and stays blocked until that PR lands, so do not add it here
   unless that PR has merged; just confirm the only remaining `modes-doc`
   warning is the blocked one. Detection-only stays as the validator's job;
   this item is the human-confirmed doc update it was designed to trigger.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   ```
   Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `modes-doc-reviewer-routing-row`.

---

## Notes & discoveries

- The general Ralph-loop technique pushes after every iteration. That
  step is intentionally **removed** here: `git push` and `gh pr create`
  are in the repo's `ask` permission list and are the human's step.
- Validation per work item lives in the relevant spec's **Validation**
  section; the build prompt runs it as backpressure before committing.
- Agentic Autonomous is deliberately off and has no work items — building toward
  it would skip the proof MISSION requires.
- When a build iteration creates a new skill, its eval suite is part of
  that same work item — not a separate one.
- **Release-management family:** all ten skills have shipped and are recorded
  in **What's been built**. Further release-management work should come from
  adopter-pilot evidence or newly accepted specs, not from the old "remaining
  six skills" queue.
- **Agentic Triage contributor-growth gaps** (PMC-member nomination,
  emeritus-committer handling, contributor offboarding) noted in
  `triage-mode.md` Known Gaps are intentionally deferred: they are
  vague enough that a spec-RFC conversation is more appropriate than
  a direct build item.
- **Project-agnosticism:** the ASF-coupling advisory lint, the non-ASF adopter
  profile fixture, the capability-flag vocabulary, and the high-confidence
  coupling cleanup have shipped. Remaining low-confidence advisories (for
  example bare governance terms that may be legitimate ASF defaults) stay
  human-judgement items unless a future spec turns them into a hard rule.
- **General-issue dedupe and backlog dashboard** (`triage-mode.md` Known
  Gaps) have shipped (`issue-deduplicate`, `issue-backlog-stats`) alongside
  `issue-stale-sweep`; see **What's been built**. No longer planned items.
- **Repo-health family** has shipped all five designed members under
  [`specs/repo-health-family.md`](specs/repo-health-family.md). No additional
  repo-health skill is planned until adopter-pilot runs produce a concrete gap.
