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
- **Agentic Mentoring — both skills shipped** — `pr-management-mentor` and
  `good-first-issue-author` (eval suites present); `docs/modes.md`
  Agentic Mentoring row reflects 2 skills / `experimental`.
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
- **Eval coverage — complete** — 60 skill eval suites exist in
  `tools/skill-evals/evals/`, covering all skills including the full
  setup-family (setup, setup-isolated-setup-doctor,
  setup-isolated-setup-install, setup-isolated-setup-update,
  setup-isolated-setup-verify, setup-override-upstream,
  setup-shared-config-sync).
- **Release-management — first four skills shipped** —
  `release-vote-draft`, `release-announce-draft`, `release-vote-tally`,
  and `release-verify-rc` landed with eval suites (formerly planned work
  items 1–2 plus two follow-ups). Six `release-*` skills remain; see
  [`specs/release-management-lifecycle.md`](specs/release-management-lifecycle.md).
- **Agentic Triage — general-issue family filled out** — `issue-stale-sweep`,
  `issue-deduplicate`, and `issue-backlog-stats` shipped with eval suites
  (formerly planned work item 3 plus its deferred siblings).
  Spec: [`specs/triage-mode.md`](specs/triage-mode.md).
- **Agentic Mentoring — first-contribution welcome shipped** — `mentoring-welcome`
  landed with an eval suite (formerly planned work item 4).
  Spec: [`specs/mentoring-mode.md`](specs/mentoring-mode.md).
- **Project-agnosticism — ASF-coupling advisory lint shipped** — the SOFT
  ASF-coupling category landed in `tools/skill-and-tool-validator`
  (formerly planned work item 5), and `drafting-mode.md` Known Gaps is
  synced to the shipped drafting skills (formerly planned work item 6).
- **Project-agnosticism — capability-flag vocabulary enumerated** — the
  contributor/committer-intake (ICLA vs DCO), security-intake, and
  CVE-allocation option sets and defaults are enumerated as
  `projects/_template/committer-onboarding-config.md`,
  `security-intake-config.md`, and `cve-allocation-config.md`, following
  the backend-flag precedent in `release-management-lifecycle.md`. Wiring
  the skills to read these flags is tracked as work item 3.
  Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
- **Repo-health — three-skill family shipped** — `ci-runner-audit`,
  `workflow-security-audit`, and `dependency-audit` landed (read-only,
  `experimental`). Spec: [`specs/repo-health-family.md`](specs/repo-health-family.md).
- **New proposed specs awaiting their first build item** —
  [`specs/reviewer-routing.md`](specs/reviewer-routing.md) (Agentic Triage) and
  [`specs/skill-reconciler.md`](specs/skill-reconciler.md) (infra) are
  documented spec-first; their build items are below.

---

## In-flight (local branches and open PRs — not available to build)

The following items are already built on local branches or open as PRs.
Do not duplicate them.

| Branch slug | PR | Description |
|---|---|---|
| `non-asf-profile-fixture` | open | Non-ASF adopter profile under `projects/_template/` + `non-asf-profile-smoke` eval (former work item 3) |

The previous in-flight batch (spec-validator SPDX / path-existence /
Known-gaps checks, the `spec-validate` pre-commit hook, the SOFT
eval-coverage check, `pr-management-quick-merge`, the security-tracker
dashboard pytest suite, the loop incremental-sync and CLI-UX changes, the
markdownlint Node bump, the AGENTS.md slim, and the modes / mentoring /
setup-status doc syncs) has all merged and is reflected in the code and
in **What's been built** above.

---

## Work items (planned)

Priority order. Each maps to one branch and one PR. Branch names are
slugs, not numbers (numbering implies an order the specs don't carry).

1. **First reviewer-routing skill: reviewer-routing.**
   `specs/reviewer-routing.md` is `proposed` with zero implemented
   skills, and review-cycle latency is one of the two priorities MISSION
   names. Add an Agentic Triage-family skill `reviewer-routing` that takes an open
   issue or PR and proposes a primary reviewer (and optional backup) from
   the project's configured roster, scored on roster eligibility for the
   touched area, git-history familiarity with the changed paths, and the
   reviewer's current open-review load. Read-only / propose-then-confirm:
   it never assigns or requests review. An unresolved roster yields an
   explicit `NO ELIGIBLE REVIEWER` signal, never a fabricated handle.
   Include an eval suite with an adversarial case asserting an injected
   "assign to X" line in a PR body is ignored.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/reviewer-routing/
   ```
   Spec: [`specs/reviewer-routing.md`](specs/reviewer-routing.md).
   Branch `reviewer-routing`.

2. **Cross-project skill reconciler: skill-reconciler.**
   `specs/skill-reconciler.md` is `proposed` with no implementation. Add
   a meta/infra-family skill `skill-reconciler` that compares two
   near-duplicate skills (two `source`-tagged copies, e.g. an ASF and a
   non-ASF variant) and emits a structured diff plus a reconciliation
   proposal, labelling every difference `ALLOWED`, `DRIFT`, or
   `SAFETY-BASELINE`. Read-only: it proposes, it never rewrites either
   skill (convergence is a separate confirmed `write-skill` /
   `optimize-skill` edit). A safety-baseline divergence is always a
   must-fix and never folded into allowed-divergence noise. First cut may
   take two explicit paths rather than auto-pairing by `source` tag.
   Include an eval suite with a case where the two copies diverge only on
   the safety baseline and the reconciler must flag it.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/skill-reconciler/
   ```
   Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
   Branch `skill-reconciler`.

3. **Clear the high-confidence ASF-coupling advisory backlog.**
   The SOFT ASF-coupling lint (shipped, see **What's been built**) still
   flags ~62 high-confidence couplings, almost all in the
   release-management skills: hardcoded ASF dist-tree paths (`dist/dev/`,
   `dist/release/`), `svn mv` / `svn commit` / `svn checkout`
   distribution commands, and the literal `announce@apache.org` list. The
   capability-flag vocabulary and `release-management-config.md`'s backend
   flags (`release-dist-backend`, `release-announce-backend`) already
   exist; this item wires the release skills (`release-rc-cut`,
   `release-promote`, `release-archive-sweep`, `release-keys-sync`,
   `release-prepare`, `release-verify-rc`, `release-vote-draft`,
   `release-vote-tally`, `release-announce-draft`) plus
   `security-issue-sync` to read those flags / use the `<announce-list>`
   placeholder instead of hardcoding ASF specifics, regressing no
   behaviour for the ASF default profile. Low-confidence advisories (bare
   `PMC`, `ICLA`, `incubator`) are out of scope: the SOFT lint leaves
   those to contributor self-judgement. Done when the validator reports
   zero high-confidence asf-coupling warnings.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/release-promote/
   ```
   Spec: [`specs/project-agnosticism.md`](specs/project-agnosticism.md).
   Branch `asf-coupling-cleanup`.

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
- **Release-management family:** the first four skills (`release-vote-draft`,
  `release-announce-draft`, `release-vote-tally`, `release-verify-rc`)
  have shipped and are recorded in **What's been built**. The remaining
  six (`release-prepare`, `release-keys-sync`, `release-rc-cut`,
  `release-promote`, `release-archive-sweep`, `release-audit-report`)
  should be planned in subsequent passes now that the first four have
  established the skill-authoring patterns for this family.
- **Agentic Triage contributor-growth gaps** (PMC-member nomination,
  emeritus-committer handling, contributor offboarding) noted in
  `triage-mode.md` Known Gaps are intentionally deferred: they are
  vague enough that a spec-RFC conversation is more appropriate than
  a direct build item.
- **Project-agnosticism:** the ASF-coupling advisory lint has shipped
  (recorded in **What's been built**); the non-ASF adopter profile
  fixture is in flight (PR open, see **In-flight**). The capability-flag
  vocabulary for contributor/committer intake (ICLA vs DCO), security
  intake, and CVE allocation has been enumerated and shipped to main
  (recorded in **What's been built**), following the backend-flag
  precedent set by `release-management-lifecycle.md` (distribution /
  approval / announcement backends). The remaining follow-on is wiring
  the skills to read those flags (work item 3) — an engineering task, not
  a spec-authoring one. The SOFT ASF-coupling lint still reports ~62
  high-confidence couplings (hardcoded `dist/` paths, `svn` commands,
  `announce@apache.org`), almost all in the release-management skills,
  which is the measurable backlog work item 3 clears.
- **General-issue dedupe and backlog dashboard** (`triage-mode.md` Known
  Gaps) have shipped (`issue-deduplicate`, `issue-backlog-stats`) alongside
  `issue-stale-sweep`; see **What's been built**. No longer planned items.
- **Repo-health family** has shipped its first three members
  (`ci-runner-audit`, `workflow-security-audit`, `dependency-audit`) under
  its own [`specs/repo-health-family.md`](specs/repo-health-family.md);
  remaining candidates (license / NOTICE compliance, flaky-test detection)
  are deferred to a subsequent pass.
