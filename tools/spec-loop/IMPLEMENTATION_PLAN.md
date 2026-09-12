<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Implementation Plan — spec-loop

Maintained by the loop's **plan** mode. It is the prioritised list of
*gaps* found by comparing [`specs/`](specs/) against the actual code
(`.claude/skills/`, `tools/`, `docs/`). The **build** mode takes the
single highest-priority work item, isolates it on its own branch,
implements it, validates it, and commits: one work item, one branch,
one PR (the branch-per-feature constraint).

> Priority lives here, not in the specs. The specs describe functional
> areas (unordered); this plan orders the work.

---

Shipped state is not tracked here. It lives in `specs/`, the code
(`skills/`, `tools/`, `docs/`), and git history. This plan lists only the
open gaps. Confirm whether something is already built by the artifact it
would produce, not by branch ancestry (squash-merged branches still read as
ahead of `main`).

*Last reconciled against `main` on 2026-07-12 (`main` at #829). Each
In-flight entry below was re-verified by checking its artifact against
`main`, not by branch ancestry.*

## In-flight (implemented on a branch, not yet merged — not available to build)

Each item below is already built and lives on a local work-item branch; its
artifact is verified **absent from `main`** (or present but not yet carrying
the branch's change), so it is not shippable but must **not** be re-picked for
build. The loop's dedup consults open PRs and *local* work-item branches
(`refs/heads/`), so an item that was pushed to `origin` and then had its local
branch deleted is invisible to that check and will be rebuilt. This list is the
backstop. Drop each item once its branch merges to `main`.

- **`message-localization`** (`b890c38e9`, local branch only). New
  `message-localization` skill that translates contributor-facing agent prose
  with human sign-off, plus a two-step eval suite (detect-language, translate)
  and `supported-languages.md`. Skill, wiring in `docs/modes.md` and
  `docs/labels-and-capabilities.md`, and evals are all absent from `main`.
  Spec: [`specs/mentoring-mode.md`](specs/mentoring-mode.md).
- **`pattern-catalogue-eval-layout-fix`** (`7c8801577`, local). Rewrites Pattern 8
  in `docs/education/pattern-catalogue.md` to the real `fixtures/` +
  `step-config.json` + `case-*/` layout. `pattern-catalogue.md` is on `main`;
  this correction is not.
  Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
- **`your-first-skill-step-renumber`** (`bfc3e1a63`, local). Adds the step-6
  Debugging-a-skill and step-7 Portable-skills entries to the "Where to go next"
  list in `docs/education/your-first-skill.md` and renumbers the tail so the
  progression reads 5 → 6 → 7 → 8. Both target pages are on `main`; these links
  are not.
  Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
- **`local-smoke-candidate-sweep`** (`b656f4615`, local). Tags 64 small-model-
  friendly `case-meta.json` cases across 20 skills with `local-smoke`. None of
  the tag additions are on `main`.
  Spec: [`specs/meta-and-quality-tooling.md`](specs/meta-and-quality-tooling.md).
- **`sandbox-lint-any-harness`** (`4306e0f97`, local). Adds a `--any-harness`
  posture check to `sandbox-lint` and declares the tool harness-agnostic, moving
  it into the harness-neutral bucket in `docs/vendor-neutrality.md`, plus posture
  tests. `main` still lists `sandbox-lint` as `✅ portable` (Claude Code / Kiro /
  OpenCode), so this slice is unmerged.
  Spec: [`specs/agent-isolation-sandbox.md`](specs/agent-isolation-sandbox.md).
- **`permission-audit-any-harness`** (`4de6e5772`, local). Same harness-neutral
  posture move for `permission-audit`: `--any` CLI mode, `docs/vendor-neutrality.md`
  reclassification, and tests. `main` still lists `permission-audit` as
  `✅ portable`, so this slice is unmerged. With `agent-isolation` (agnostic) and
  `agent-guard` (exec-mode) already on `main`, these last two substrate tools are
  the remainder of the harness-portability push.
  Spec: [`specs/agent-isolation-sandbox.md`](specs/agent-isolation-sandbox.md).
- **`education-training-lesson-lab`** (`eee643377`, local). Remaining slice of the
  Apache Training epic: adds `docs/education/training/lesson-lab-tutorials.md` and
  wires it into `docs/education/training/README.md`. Lessons 01–11, the instructor
  guide, and the README index are already on `main`; this hands-on lab page is not.
  Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
- **`education-training-upstream-contribution`** (`d746e3197`, local). Other
  remaining Apache Training slice: adds
  `docs/education/training/upstream-contribution.md`. Absent from `main`.
  Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
- **`skill-reconciler-diff-step1`** (`8c59883e6`, local). Wires the
  `skill-reconciler-diff` helper into `skill-reconciler` as an optional Step 1
  enhancement and adds the `step-1-diff-tool` eval. The `skill-reconciler-diff`
  tool, the `skill-reconciler` skill, and its `step-0` eval are on `main`; this
  step-1 wiring and eval are not.
  Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
- **`verify-rc-version-consistency-eval-step8`** (`715b23c2b`, local). Repoints the
  release-verify-rc version-consistency eval at a renumbered Step 8 and adds its
  `step-8` fixtures. `main` has release-verify-rc eval steps 0/2/3/5/6/7 only.
  Spec: [`specs/release-management-lifecycle.md`](specs/release-management-lifecycle.md).
- **`org-non-asf-smoke-coverage`** (`f0f741f1f`, local). Adds a non-ASF
  organization-profile smoke case to the `skill-and-tool-validator` test suite.
  Not on `main`.
  Spec: [`specs/organization-adapters.md`](specs/organization-adapters.md).
- **`org-template-reflow`** (`94c3f6b85`, local). Drops org-inherited values from
  `projects/_template/project.md` and the `projects/non-asf-example/project.md`
  fixture so the template carries only project-level config. Both files exist on
  `main`; the reflow is not applied there.
  Spec: [`specs/organization-adapters.md`](specs/organization-adapters.md).

---

## Work items (planned)

Priority order. Each maps to one branch and one PR. Branch names are
slugs, not numbers (numbering implies an order the specs don't carry).

1. **Regenerate the AI tutor prompts.**
   The `ai-tutors/lesson-*.md` prompts embed the source text of their matching
   `docs/education/training/` lessons. Five are now stale after the training
   lessons landed and were revised: `lesson-07-writing-portable-skills`,
   `lesson-08-eval-driven-development`, `lesson-09-agentic-and-autonomous-work`,
   `lesson-10-english-as-a-programming-language`, and `lesson-11-how-to-contribute`.
   Run the injector to refresh the generated `## KNOWLEDGE BASE` sections
   (hand-written answer keys and summaries are preserved), then commit the
   regenerated prompts.
   Validation:
   ```bash
   python3 ai-tutors/inject-knowledge-base.py
   python3 ai-tutors/inject-knowledge-base.py --check   # must report 0 stale
   ```
   Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
   Branch `ai-tutors-regenerate`.

2. **Make the AI tutors discoverable from the education docs.**
   The tutors exist under `ai-tutors/` but the learner-facing docs barely point
   to them, so a reader following the `docs/education/` progression never learns
   they can be taught interactively. Add a short "Learn with an AI tutor" section
   to `docs/education/README.md` and `docs/education/training/README.md` that says
   what the tutors are, that each maps to one lesson, and how to load one (paste
   everything below the `---` as the system prompt), linking to
   [`ai-tutors/README.md`](../../ai-tutors/README.md) for the per-tool detail.
   Confirm `ai-tutors/README.md`'s Files table lists all eleven lessons. Keep it
   one cohesive doc change (one PR); no tutor content is regenerated here.
   Validation:
   ```bash
   grep -qi "ai-tutor" docs/education/README.md
   grep -qi "ai-tutor" docs/education/training/README.md
   ```
   Spec: [`specs/maintainer-education.md`](specs/maintainer-education.md).
   Branch `ai-tutors-doc-discoverability`.

3. **Add the `.apache-magpie-local/` personal override surface.**
   Foundational for the hybrid-setup work below. Implement acceptance 5 of
   [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md): a gitignored,
   per-person override directory read at runtime as a sibling to the committed
   `.apache-magpie-overrides/`, with precedence personal-local -> committed ->
   organization -> framework default (first hit wins) and the same additive-only
   guardrail (it cannot weaken the safety / confidentiality / privacy baseline).
   Teach the override-reading path and `setup-status` about it, and have adoption
   add the `.gitignore` entry. Document the `docs/setup/` agentic-overrides
   contract to cover the new surface.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   grep -qi "apache-magpie-local" docs/setup/*.md
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md).
   Branch `magpie-local-convention`.

4. **Add a one-shot "use framework defaults this run" switch.**
   Implement acceptance 6 of `specs/adoption-and-setup.md`: a per-invocation
   switch that runs a skill against framework defaults for that session only,
   ignoring both `.apache-magpie-local/` and `.apache-magpie-overrides/` without
   editing or deleting either, with the safety baseline still applied. Smaller
   than item 3 and independent of it in principle, but the override-reading path
   it toggles is the same one item 3 extends, so land item 3 first.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md).
   Branch `override-bypass-one-shot`.

5. **How-to: use Magpie on a repo that has not adopted it.** (blocked on item 3)
   A `docs/setup/` recipe for the "I am not on Project X, it has not adopted
   Magpie, but I want to use Magpie for a fix" case: whole-user install, drop a
   `.apache-magpie-local/`, add the one `.gitignore` line, run against the target
   repo. Behaviour is already largely supported once item 3 lands; the gap is the
   documented path.
   Validation:
   ```bash
   test -f docs/setup/individual-use.md
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md).
   Branch `howto-personal-use-unadopted-repo`.

6. **How-to: per-role MCP access (e.g. release manager enables a Policy MCP).**
   (blocked on item 3) A `docs/setup/` recipe showing a member enabling a
   capability or MCP server in their own `.apache-magpie-local/` while other
   members leave it off, without changing shared project config.
   Validation:
   ```bash
   test -f docs/setup/per-role-mcp-access.md
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md),
   [`specs/organization-adapters.md`](specs/organization-adapters.md).
   Branch `howto-per-role-mcp`.

7. **How-to: mixed-adoption teams (some use Magpie, some do not).** (blocked on
   item 3) A `docs/setup/` recipe for one person running Magpie on a shared repo
   via whole-user install plus `.apache-magpie-local/` without requiring teammates
   to opt in. Fold in a small probe: confirm shared skills do not assume every
   teammate has Magpie; if any skill hard-fails in that situation, file it as its
   own gap rather than papering over it in the doc.
   Validation:
   ```bash
   test -f docs/setup/team-adoption.md
   ```
   Spec: [`specs/adoption-and-setup.md`](specs/adoption-and-setup.md).
   Branch `howto-mixed-adoption-teams`.

Items 5–7 are blocked on item 3 (they document the surface it introduces).
Beyond the items above, every other gap from the previous plan has either shipped
to `main` or sits in the In-flight list above awaiting review and merge. Once the
In-flight items merge, run a fresh plan pass against `specs/` to surface the next
round of gaps.

Shipped to `main` since the last plan and no longer tracked here (a partial,
plan-relevant list; git history is authoritative):

- **Maintainer-education progression** restructured into the ordered path and the
  new conceptual stages landed (`what-agents-are`, `working-with-agents`,
  `choosing-models`, `agentic-work`, `english-as-code`, `contributing`, with
  `pattern-catalogue` and `eval-driven-development` as references and
  `workshops.md` renamed to `tutorials.md`). The `debugging-skills` (step 6) and
  `portable-skills` (step 7) pages and `writing-safe-skills` (step 5) also landed.
- **Apache Training epic** largely shipped: `docs/education/training/` lessons
  01–11, the README index, and the instructor guide (#805–#811 and neighbours).
  Only the lesson-lab and upstream-contribution pages remain In-flight.
- **Harness-portability substrate**: `agent-isolation` is now `✅ agnostic`
  (`agent-iso` entry point) and `agent-guard` gained harness-neutral exec-mode.
  `sandbox-lint` and `permission-audit` are the two remaining substrate slices
  (In-flight above).
- **`no-telemetry-import`** SOFT validator check plus the PRINCIPLE 10 guarantee
  note on `egress-gateway`.
- **`skill-reconciler`** skill and the `skill-reconciler-diff` tool with a
  `step-0` eval; **`skill-md-line-limit-check`** SOFT advisory; the
  `dependency-license-audit` skill (#814).
- Broad release, bitbucket, security-issue-sync, and setup/adoption work through
  #829 (clean source-only RC tarball, read-only bitbucket PR fetches, frontmatter
  family/mode/when_to_use requirement, Meta mode, and more).

---

## Notes & discoveries

- `git push` and `gh pr create` are intentionally **not** run by the loop.
  They are in the repo's `ask` permission list and are the human's step.
- Because the loop never pushes, its "already built" dedup checks open PRs and
  *local* work-item branches only. An item that a human has pushed to `origin`
  (and whose local branch was then deleted) is invisible to that check and will
  be rebuilt unless it is listed in **In-flight** above. Keep that list current.
- Stale plan-mode branches exist locally (`plan-0705`, `plan-0706`, `plan-0712`).
  They are prior snapshots of this file, not build items; `plan-0712` is identical
  to `main`. The canonical plan is this file on `main`.
- Validation per work item lives in the relevant spec's **Validation** section;
  the build prompt runs it as backpressure before committing. When a build
  creates a new skill, its eval suite is part of that same work item.
- Agentic Autonomous is deliberately off and has no work items. Building toward
  it would skip the proof MISSION requires.
- Deferred by design (not build items): Agentic Triage contributor-growth gaps
  (PMC-member nomination, emeritus handling, offboarding) and the remaining
  low-confidence ASF-coupling advisories. Both stay human-judgement until a
  spec turns them into a rule.
