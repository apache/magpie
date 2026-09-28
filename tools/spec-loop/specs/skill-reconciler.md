<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Cross-project skill reconciler
status: experimental
kind: feature
mode: infra
source: >
  MISSION.md § Scope boundaries ("Duplication is embraced where it buys
  decoupling ... an agent can reconcile two near-identical skills on
  demand, so the price of keeping them separate is low") and § "The data
  layer is shared; the skills on top are free to diverge" (skills carry a
  `source` tag so the split is a registry query). PRINCIPLES.md on the
  safety baseline that must stay eventually-consistent across every copy.
  meta-and-quality-tooling.md (the skill-authoring/quality family this
  joins). Skill ships experimental in
  plugins/magpie-utilities/skills/skill-reconciler/ with an eval suite
  under tools/skill-evals/evals/skill-reconciler/.
acceptance:
  - The reconciler is read-only: it produces a structured diff and a
    reconciliation proposal; it never rewrites either skill without human
    confirmation.
  - Divergence in the safety baseline (untrusted-content-is-never-
    instructions, identity-resolution caveats, confidentiality posture)
    is reported as a must-fix, distinct from divergence that is allowed
    to stand.
  - A maintainer can review the proposal and the safety-baseline verdict
    without running either skill.
---

# Cross-project skill reconciler

## What it does

Compares two near-duplicate skills, typically the same capability carried
in an ASF and a non-ASF variant (or two `source`-tagged copies), and
produces a structured diff plus a reconciliation proposal. It
operationalises the MISSION principle that duplication is fine where it
buys decoupling precisely because an agent can reconcile copies on
demand: the reconciler is that agent step, made repeatable.

The key move is that not all divergence is equal. The reconciler sorts
differences into three classes: **allowed divergence** (scope, tier,
teaching voice, project-specific values behind placeholders, the things
MISSION says skills are free to diverge on); **drift** (one copy gained a
fix, a clearer step, or a hardening the other lacks, where convergence is
probably wanted); and **safety-baseline divergence** (the
untrusted-content-is-never-instructions rule, identity-resolution
caveats, confidentiality posture, which PRINCIPLES says every copy must
stay eventually-consistent on). The first is reported and left alone, the
second is proposed as a merge, and the third is flagged as a must-fix
that a maintainer should not ignore.

## Where it lives

- Skill: `skill-reconciler` at
  `plugins/magpie-utilities/skills/skill-reconciler/` (reached as
  `skills/skill-reconciler/` and, through the self-adoption symlinks,
  `.agents/skills/magpie-skill-reconciler/`), in the utilities family
  (`mode: Meta`) with `write-skill`, `optimize-skill`, and `list-skills`
  (see [meta-and-quality-tooling.md](meta-and-quality-tooling.md)).
  Eval suite under `tools/skill-evals/evals/skill-reconciler/`.
- `safety-baseline-checklist.md` beside the skill: the three
  safety-baseline clauses, each with what must be present, what counts as
  a failure, and canonical wording. The skill's SAFETY-BASELINE class
  points at it as the ground-truth definition.
- Deterministic helper: `tools/skill-reconciler-diff/`, a stdlib-only `uv`
  tool (`substrate:framework-dev`) that parses two skill trees into a
  normalised JSON diff (frontmatter, section headings, step inventory,
  placeholder inventory, support files, and per-clause safety-baseline
  presence, detected by regex against the checklist's three clauses).
  Follows the tool-backs-skill pattern used across the catalogue.
- Inputs: two `SKILL.md` trees (plus their supporting `.md` files),
  identified by path or by `source` tag.
- It reads the safety-baseline definition from the same place the rest of
  the framework does (PRINCIPLES.md / the security posture docs); it does
  not restate the baseline inline.

## Behaviour & contract

- **Read-only; proposes, never rewrites.** The reconciler emits a diff
  and a proposal. Any actual convergence edit goes through `write-skill`
  / `optimize-skill` under human confirmation; the reconciler itself
  changes no skill file.
- **Three-class divergence verdict.** Every difference is labelled
  `ALLOWED`, `DRIFT`, or `SAFETY-BASELINE`. The safety-baseline class is
  never silently merged away and never dropped from the report, even when
  the two copies are otherwise identical.
- **Safety divergence is a must-fix, not a suggestion.** When the two
  copies disagree on the untrusted-content rule, identity-resolution
  caveats, or confidentiality posture, the reconciler surfaces it as a
  blocking finding a maintainer must resolve, separate from the
  convenience merges.
- **Decoupling is preserved by default.** The reconciler does not push
  toward DRY across organisational boundaries; allowed divergence is
  reported and left in place. Convergence is proposed only for drift and
  required only for the safety baseline.
- **Untrusted content stays data.** Skill bodies under comparison are
  treated as input data; an injected instruction inside a compared skill
  is reported as content, never executed.

## Out of scope

- Rewriting, merging, or deleting either skill on autopilot (that is a
  confirmed `write-skill` / `optimize-skill` edit).
- Choosing which copy "wins" on allowed divergence; the reconciler
  reports the difference and leaves the call to the maintainers who own
  each copy.
- Cross-foundation policy. The reconciler is a tool for reconciling skill
  text; it makes no claim on which project's governance is correct.

## Acceptance criteria

1. Given two near-duplicate skills, the reconciler emits a structured
   diff and labels every difference `ALLOWED`, `DRIFT`, or
   `SAFETY-BASELINE`.
2. A safety-baseline divergence is always reported as a must-fix and is
   never folded into the allowed-divergence noise.
3. The reconciler makes no edit to either skill; convergence is a
   separate, confirmed authoring step.
4. The skill validates under `skill-and-tool-validate` and ships an eval
   suite under `tools/skill-evals/evals/skill-reconciler/`, including a
   case where the two copies diverge only on the safety baseline and the
   reconciler must flag it.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals skill-eval tools/skill-evals/evals/skill-reconciler/
```

## Known gaps

- **Safety-baseline definition is a single file, but still prose.** The
  three clauses now live in one authoritative
  `safety-baseline-checklist.md` that both the skill and
  `tools/skill-reconciler-diff` reference. Detection remains pattern
  recognition over prose: the helper's regexes are hard-coded in the tool
  rather than read from the checklist, so the two can drift apart.
- **`capability`-tag auto-pairing shipped; `source`-tag registry not yet used.**
  `--discover <skills-dir>` now groups by `capability:` frontmatter and
  presents a bounded candidate list. The MISSION vision of a registry query
  over explicit `source:` tags is deferred until that tag is in use in
  production skill frontmatter.
- **Deterministic structural-diff helper shipped** —
  `tools/skill-reconciler-diff/` is a stdlib-only `uv` tool that parses
  two skill trees into a normalised diff (frontmatter, section headings,
  step inventory, placeholder inventory, support files, and
  safety-baseline clause presence) and emits a JSON object.  It is
  intended to be used as an optional Step 1 enhancement to the
  `skill-reconciler` skill, but the skill still does not wire it in:
  `SKILL.md` never names `skill-reconciler-diff`. Its unit tests cover
  frontmatter-only, section-order, placeholder, support-file, and
  safety-baseline divergences.
