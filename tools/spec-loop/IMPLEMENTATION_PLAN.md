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
  privacy-LLM gate, the sandbox, CVE tooling, adoption/setup, adapters,
  and meta/quality tooling).
- **Loop scaffolding** — `loop.sh` (plan / build / consolidate; a branch
  per work item; never pushes), `PROMPT_plan.md`, `PROMPT_build.md`,
  `PROMPT_consolidate.md`, `AGENTS.md` (loop-scoped operational context),
  and this plan.
- **Pairing — pre-flight self-review skill** — `.claude/skills/pairing-self-review/`
  shipped; `docs/modes.md` Pairing row updated to 1 skill / `experimental`.
  Spec: [`specs/pairing-mode.md`](specs/pairing-mode.md).
- **Mentoring — first prototype skill** — `pr-management-mentor` shipped,
  `mode: Mentoring` + `experimental`, teaching-register replies with
  explicit hand-off. Spec: [`specs/mentoring-mode.md`](specs/mentoring-mode.md).
- **Docs — mode economics page** — `docs/mode-economics.md` exists
  (per-mode token-cost shape, vendor-neutral).
- **Meta — spec-status index** — `tools/spec-status-index/` exists as a
  `uv` tool that prints specs grouped by status.
  Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
- **Eval backfill** — 24 skill eval suites committed to `main`, covering
  every non-setup skill. Setup-family suites are in-flight (see below).

---

## In-flight work

These branches and/or open PRs already carry the change. Do **not** add
a plan item for any of them; the build beat must not re-pick them.

| Branch | PR | Description |
|---|---|---|
| `pairing-multi-agent-review` | #269 (draft) | Pairing multi-agent review pipeline |
| `generic-drafting` | #296 (draft) | Generic (non-security) drafting from audit findings |
| `eval-setup-isolated-setup-doctor` | — | Eval suite for setup-isolated-setup-doctor |
| `eval-setup-isolated-setup-install` | — | Eval suite for setup-isolated-setup-install |
| `eval-setup-isolated-setup-update` | — | Eval suite for setup-isolated-setup-update |
| `eval-setup-override-upstream` | — | Eval suite for setup-override-upstream |
| `eval-setup-shared-config-sync` | — | Eval suite for setup-shared-config-sync |
| `eval-setup-steward` | — | Eval suite for setup-steward |
| `spec-validator` | — | `tools/spec-validator/` — spec frontmatter + body-section validator |
| `spec-loop-preflight-checks` | — | Freshness check + branch-name collision guard for the loop |
| `injection-guard` | — | Prompt-injection defence hardening |
| `check-headers` | — | License headers as a first-class review category |
| `issue-fix-workflow` | — | issue-fix-workflow skill updates |
| `contributor-readiness` | #227 (draft) | contributor-nomination skill + eval |
| `contributor-activity` | #228 (draft) | contributor-activity-sweep skill + eval |
| `contributor-onboarding` | #229 (draft) | committer-onboarding skill |

---

## Work items (planned)

Priority order. Each maps to one branch and one PR. Branch names are
slugs, not numbers (numbering implies an order the specs don't carry).

1. **Security reporting — add tool test suite.** `tools/security-tracker-stats-dashboard/`
   has Python scripts (`render.py`, `fetch_*.py`) but no `tests/`
   directory. The spec acceptance criterion #3 and its Known Gaps section
   both require tests here. Add a `tests/` directory with pytest coverage
   for the fetch/render pipeline. Validation:
   ```bash
   uv run --project tools/security-tracker-stats-dashboard --group dev pytest
   bash -n tools/security-tracker-stats-dashboard/run.sh
   shellcheck tools/security-tracker-stats-dashboard/run.sh
   ```
   Spec: [`specs/security-reporting.md`](specs/security-reporting.md).
   Branch `security-reporting-tests`.

2. **Agent isolation — Python packaging and test harness.** `tools/agent-isolation/`
   is shell-only (no `pyproject.toml`, no `tests/`), but the spec's
   validation command requires `uv run --project tools/agent-isolation
   --group dev pytest`. Convert the tool to a `uv` Python project, add a
   `pyproject.toml`, and write tests that verify the sandbox profiles and
   clean-env wrapper behave correctly. Validation:
   ```bash
   uv run --project tools/agent-isolation --group dev pytest
   ```
   Spec: [`specs/agent-isolation-sandbox.md`](specs/agent-isolation-sandbox.md).
   Branch `agent-isolation-tests`.

3. **Mentoring: good-first-issue authoring skill.** The Mentoring spec
   names `good-first-issue-author` as proposed (not yet built): a skill
   that drafts a single net-new good first issue from a supplied known gap
   or maintainer-named small task (scope, code pointers, contributing-doc
   links, acceptance criteria, effort estimate), flagged `mode: Mentoring`
   + `experimental`, and never files it without maintainer confirmation.
   Ship the skill plus its eval suite as one work item. Validation:
   ```bash
   test -d .claude/skills/good-first-issue-author
   uv run --project tools/skill-validator --group dev skill-validate
   ```
   Spec: [`specs/mentoring-mode.md`](specs/mentoring-mode.md).
   Branch `good-first-issue-author`.

---

## Notes & discoveries

- The general Ralph-loop technique pushes after every iteration. That
  step is intentionally **removed** here: `git push` and `gh pr create`
  are in the repo's `ask` permission list and are the human's step.
- Validation per work item lives in the relevant spec's **Validation**
  section; the build prompt runs it as backpressure before committing.
- Auto-merge is deliberately off and has no work items — building toward
  it would skip the proof MISSION requires.
- When a build iteration creates a new skill, its eval suite is part of
  that same work item — not a separate one.
