---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-optimize-skill
family: utilities
mode: Meta
description: |
  Optimize an existing framework skill (or sweep a set of them) by
  applying the restructuring patterns proven on the security-skill
  suite: split an oversized `SKILL.md` into linked sibling docs,
  lift concrete/project-specific values out of the body into
  `<project-config>` placeholders, replace in-agent-context body
  reads with out-of-context tool calls, batch per-item fetches into
  a single upfront pass, and add a deterministic pre-flight no-op
  classifier ahead of LLM passes. Every change is a behavior-
  preserving proposal the maintainer signs off on; the skill
  validator must stay green before and after. The refactoring
  sibling of `write-skill` (which authors net-new skills).
when_to_use: |
  Invoke when a maintainer says "optimize <skill>", "slim down
  <skill>'s SKILL.md", "this SKILL.md is too long", "split <skill>
  into subdocs", "lift the hardcoded values out of <skill>", "make
  <skill> read less into context", or "sweep the skills for P14
  violations". Also a natural follow-up to a principles/validator
  audit that flags an over-500-line SKILL.md, concrete-name
  leakage, or a heavy in-context read. Skip for net-new skills —
  that is `write-skill`. Skip when the request is a behavior
  change dressed up as an optimization; route those through normal
  skill editing + review.
capability: capability:authoring
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md
     <framework>      → `.apache-magpie/apache-magpie` in adopters; `.` in
                        the framework standalone -->

# optimize-skill

Take one existing framework skill — or a maintainer-supplied set of
them — and make it leaner without changing what it does. The skill
diagnoses a target against the optimization catalogue distilled from
the recent security-suite refactors, proposes the applicable passes,
and applies them one at a time as **behavior-preserving** edits the
maintainer confirms. The skill validator (and, for tracker-touching
skills, the placeholder linter) is the deterministic gate: it is
green before the first pass and green again after the last.

This skill operates only on **framework-internal files** — `SKILL.md`
bodies, their sibling docs, `<project-config>` manifests, tool
adapters in this repo. It reads no external or attacker-controlled
content, so the prompt-injection-defence callout does not apply.

It is the refactoring counterpart to
[`write-skill`](../write-skill/SKILL.md): `write-skill` authors a
net-new skill; `optimize-skill` restructures one that already exists.
The five passes, their smells, exemplar PRs, mechanics, and
behavior-preservation guarantees live in
[`patterns.md`](patterns.md); this body is the orchestration.

---

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-overrides/optimize-skill.md`](../../docs/setup/agentic-overrides.md)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-magpie.local.lock` (per-machine
fetch) against the committed `.apache-magpie.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`/magpie-setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now.

---

## Inputs

- **Target** — the skill to optimize, as a skill name
  (`security-issue-import`), a directory
  (`.claude/skills/security-issue-import/`), or a `SKILL.md`
  path. Required for a single-skill run.
- **Sweep selector** (optional) — `--all` to diagnose every skill
  under `.claude/skills/` and rank optimization candidates without
  applying anything, or `over:<N>` to scope the sweep to SKILL.md
  files longer than `<N>` lines (default threshold: **500**, the
  `PRINCIPLES.md` P14 cap).
- **Pass filter** (optional) — restrict to named passes from
  [`patterns.md`](patterns.md), e.g. `pass:split` or
  `pass:config-lift,out-of-context`. Default: propose every
  applicable pass.

When no target and no sweep selector are given, default to a
read-only `--all` diagnosis and let the maintainer pick a target
from the ranked list.

---

## Prerequisites

- **`uv`** — runs the skill validator
  ([`tools/skill-and-tool-validator`](../../tools/skill-and-tool-validator/README.md))
  and the placeholder linter. Without it the green-before /
  green-after gate cannot run; stop and ask the user to install
  `uv`.
- **`git`** — the behavior-preservation checks rely on
  `git diff` / `git mv`; the skill expects a clean (or
  intentionally dirty, user-acknowledged) working tree so its own
  edits are isolable.
- **`doctoc`** — regenerates a sibling/anchor TOC after a split
  changes headings. If absent, surface the manual TOC step instead
  of silently skipping it.

---

## Step 0 — Pre-flight check

1. **Target resolves** to a real skill directory containing a
   `SKILL.md`. A bad name → stop and list the available skills.
2. **Baseline is green.** Run the validator on the target (or the
   whole tree for a sweep) and record the result. If it is already
   **red**, stop: optimization is a no-behavior-change operation
   layered on a passing skill, not a way to fix a broken one. Hand
   the failures back; the maintainer fixes correctness first.
3. **Working tree is isolable.** Prefer a clean tree, or a
   dedicated branch, so the optimization diff is reviewable on its
   own. If the tree carries unrelated changes, surface them and ask
   before proceeding.
4. **Snapshot is current** (see *Snapshot drift* above) — a stale
   snapshot means the target on disk may not match the framework
   the maintainer thinks they are editing.

---

## Step 1 — Diagnose

Run every diagnostic in [`patterns.md`](patterns.md) against the
target and emit a findings table — one row per detected smell, each
naming the pass that addresses it, the evidence (`path:line`, line
count, the offending construct), and an effort/blast-radius note.
Diagnosis is **read-only**; it never edits.

The five smells, in the order the passes below apply them:

1. **Oversized body** — `SKILL.md` over the 500-line P14 cap, or a
   single section that dominates the body. → *split* pass.
2. **Concrete-name leakage** — adopter-specific values (a concrete
   `<upstream>` repo slug, real list addresses, real IDs) baked into
   the body instead of resolved from `<project-config>`. →
   *config-lift* pass.
3. **In-context bulk read** — a step that pulls a whole issue body,
   rollup comment, or large artefact into the agent context only to
   touch one field of it. → *out-of-context* pass.
4. **Per-item round-trips** — N sequential fetches the skill could
   issue as one upfront batch. → *fetch-upfront* pass.
5. **No deterministic pre-filter** — the skill spends an LLM pass on
   items a cheap deterministic classifier could skip as obvious
   no-ops. → *preflight-classifier* pass.

For a sweep, rank targets by (cap overflow × number of distinct
smells) and present the list; apply nothing until the maintainer
picks one.

---

## Step 2 — Propose

For the chosen target, propose the applicable passes **in the order
above** (lowest blast radius first: a pure file move before any
content lift before any tool rewire). For each proposed pass state:
the exact files created/moved, the slimming delta (e.g. *"SKILL.md
3425 → ~660 lines, four new siblings"*), and the
behavior-preservation guarantee from [`patterns.md`](patterns.md).

Propose; do not apply. Wait for the maintainer to pick which passes
to run, in which order.

---

## Step 3 — Apply one pass at a time

For each confirmed pass, smallest reversible step first:

- **Restructure passes (split, config-lift)** move or relocate text
  with **no wording change to the instructions themselves**. Use
  `git mv` where a whole file relocates; otherwise cut-and-paste the
  exact bytes and replace the body region with a one-line pointer to
  the new sibling. Never paraphrase a moved instruction — a
  behavior-preserving move means the moved bytes are identical.
- **Rewire passes (out-of-context, fetch-upfront,
  preflight-classifier)** change *how* a step runs, not *what
  decision it reaches*. They route through an existing deterministic
  tool (e.g. [`github-body-field`](../../tools/github-body-field/README.md),
  [`github-rollup`](../../tools/github-rollup/README.md)) or a
  pre-flight classifier; the human-visible proposals and gates the
  skill produces are unchanged. If a rewire would alter what the
  skill proposes to the user, it is a behavior change — stop and
  route it through normal review, not this skill.

After each pass: regenerate the doctoc TOC if headings moved, and
re-run the validator. One pass per commit keeps the diff reviewable
and the `git mv` rename-detection intact.

---

## Step 4 — Validate (green-after gate)

Re-run the validator (and the placeholder linter for tracker-
touching skills) on the optimized target. It **must** return the
same green it returned at Step 0. Then prove behavior preservation:

- For restructure passes, confirm the concatenation of `SKILL.md` +
  new siblings contains the same instruction bytes as the original
  (a moved-not-changed check: `git diff` should show deletions in
  `SKILL.md` matching additions in the siblings, plus the new
  pointer lines).
- For rewire passes, confirm the skill's proposal/apply surface —
  the things a human signs off on — is unchanged; only the
  in-context cost or round-trip count drops.

If the validator goes red or behavior preservation cannot be shown,
**revert the pass** and hand back; do not ship a half-applied
optimization.

---

## Step 5 — Hand back

Summarise per pass: files touched, the slimming delta, validator
result, and the behavior-preservation evidence. Do **not** open a
PR or commit unless the maintainer asks — surface the diff and let
them review. When they do commit, one pass per commit, subject in
the `refactor(<skill>): …` form the security-suite splits used
(e.g. *"extract N subdocs to slim SKILL.md A → B lines"*).

If the run was a sweep, restate the ranked remaining candidates so
the maintainer can queue the next one.

---

## Hard rules

- **Behavior never changes.** This skill restructures and rewires;
  it never alters what a skill decides, proposes, or asks a human to
  confirm. A change that alters behavior is out of scope — route it
  through normal skill editing and review.
- **Moved bytes are identical bytes.** A split or lift that
  paraphrases the moved instructions is a behavior change in
  disguise. Move verbatim; only the surrounding pointer is new.
- **Propose before applying.** Every pass is a proposal the
  maintainer confirms (framework Principle 6). Never batch-apply a
  sweep.
- **The validator is the gate.** Green before, green after, every
  pass. A pass that needs the validator relaxed is not an
  optimization.
- **The optimized SKILL.md still obeys P14** — under 500 lines, with
  every sibling linked exactly one level deep and no unreferenced
  siblings.
- **Never touch the snapshot** (`<adopter-repo>/.apache-magpie/`).
  Framework-skill optimizations land via PR to `apache/magpie`.

---

## References

- [`patterns.md`](patterns.md) — the five optimization passes:
  smell, exemplar PR, mechanics, behavior-preservation guarantee,
  validation.
- [`write-skill`](../write-skill/SKILL.md) — authoring a net-new
  skill (this skill's counterpart).
- [`tools/skill-and-tool-validator`](../../tools/skill-and-tool-validator/README.md)
  — the green-before / green-after gate.
- [`tools/github-body-field`](../../tools/github-body-field/README.md)
  and [`tools/github-rollup`](../../tools/github-rollup/README.md)
  — out-of-context read/PATCH tools the rewire passes route through.
- [`docs/labels-and-capabilities.md`](../../docs/labels-and-capabilities.md)
  — the `capability:*` taxonomy and the P14 authorship rule this
  skill enforces.
