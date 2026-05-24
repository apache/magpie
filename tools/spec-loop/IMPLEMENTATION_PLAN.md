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

---

## Work items (planned)

Priority order. Each maps to one branch and one PR. Branch names are
slugs, not numbers (numbering implies an order the specs don't carry).

1. **Pairing — pre-flight self-review skill.** Highest priority: closes
   the empty-Pairing-family gap MISSION makes a v1 goal. New
   `.claude/skills/pairing-self-review/SKILL.md` (read-only, hands a
   report back, never opens a PR); update `docs/modes.md` Pairing row
   0 → 1, `proposed` → `experimental`. Validate with `skill-validate`.
   Spec: [`specs/pairing-mode.md`](specs/pairing-mode.md). Branch
   `pairing-self-review`.

2. **Mentoring — first prototype skill.** `pr-management-mentor` (working
   name), `mode: Mentoring` + `experimental`, drafting replies in a
   teaching register with an explicit hand-off to a human. The Mentoring
   spec/tone-guide already exists under `docs/mentoring/`. Spec:
   [`specs/mentoring-mode.md`](specs/mentoring-mode.md). Branch
   `mentoring-prototype`.

3. **Docs — mode economics page.** New `docs/mode-economics.md` (per-mode
   token-cost shape, vendor-neutral, indicative-not-a-quote), linked from
   `docs/modes.md`. From MISSION § Affordability. Branch
   `mode-economics-doc`.

4. **Meta — spec-status index.** A deterministic `uv` tool (mirrors
   `list-steward-skills`) that prints specs by status and a `--ready`
   filter, so later build iterations choose the next work item
   mechanically. Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `spec-status-index`.

5. **Pairing — multi-agent review pipeline.** Fans a local diff through
   independent review passes (correctness / security / conventions) and
   merges the findings. Reuses the self-review report format, so it
   follows work item 1. Branch `pairing-multi-agent-review`.

6. **Drafting — generic (non-security) drafting.** Extend Drafting beyond
   the security + general-issue cases to lint fixes, audit-tool findings,
   and documentation holes (MISSION names these in scope). Larger; split
   into per-source work items as it is picked up. Spec:
   [`specs/drafting-mode.md`](specs/drafting-mode.md). Branch
   `generic-drafting`.

7. **Meta — back-fill missing skill eval suites.** Per `/AGENTS.md`
   § Reusable skills, every skill ships an eval suite under
   `tools/skill-evals/evals/<skill-name>/`. Several skills predate that
   convention and have none. Add one suite per uncovered skill — one
   branch per skill (or per family). Spec:
   [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
   Branch `eval-<skill-name>`.

   Also: when a build iteration creates a new skill, its eval suite is
   part of that same work item — not a separate one.

---

## Notes & discoveries

- The general Ralph-loop technique pushes after every iteration. That
  step is intentionally **removed** here: `git push` and `gh pr create`
  are in the repo's `ask` permission list and are the human's step.
- Validation per work item lives in the relevant spec's **Validation**
  section; the build prompt runs it as backpressure before committing.
- Auto-merge is deliberately off and has no work items — building toward
  it would skip the proof MISSION requires.
