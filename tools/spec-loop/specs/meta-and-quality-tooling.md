<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Meta & quality tooling
status: stable
kind: feature
mode: infra
source: >
  README.md § Skill families (utilities) and AGENTS.md § Reusable skills.
  Implemented by tools/skill-and-tool-validator/, tools/skill-evals/,
  tools/sandbox-lint/, tools/dashboard-generator/, tools/probe-templates/,
  and the write-skill / list-skills utility skills.
acceptance:
  - Skill definitions are validated (frontmatter keys name/description/
    license, internal link integrity, placeholder conventions).
  - There is a live, generated index of available skills (no cached copy).
  - Skill behaviour can be measured by an eval harness.
  - Every skill ships a behavioural eval suite under
    tools/skill-evals/evals/<skill-name>/ (per /AGENTS.md § Reusable
    skills).
---

# Meta & quality tooling

## What it does

The framework's tooling for authoring, validating, indexing, and
evaluating its own skills — the quality gate that keeps the catalogue
trustworthy as it grows.

## Where it lives

- `tools/skill-and-tool-validator/` — validates `SKILL.md` frontmatter (required
  `name`, `description`, `license`) and tool definitions, internal link integrity,
  placeholder conventions, license headers on tool Python files, and eval-coverage
  (soft check: warns when a skill has no eval suite). CLI: `skill-and-tool-validate`.
- `tools/skill-evals/` — harness for measuring skill behaviour.
- `tools/sandbox-lint/` — lints the sandbox/permissions configuration.
- `tools/symlink-lint/` — lints the framework's self-adoption skill
  symlinks: rejects cyclic symlinks and misdirected relays (canonical/
  relay target-correctness).
- `tools/dashboard-generator/` — read-only HTML dashboards over campaign
  artefacts.
- `tools/probe-templates/` — reusable probes.
- `tools/spec-status-index/` — deterministic `uv` tool that reads
  `tools/spec-loop/specs/` and prints specs grouped by status; used by
  build iterations to mechanically select the next work item.
- `tools/spec-validator/` — validates spec-loop spec frontmatter
  (required keys, valid `status`/`kind`/`mode` values, body-section
  presence, `Known gaps` section required in functional specs,
  SPDX-License-Identifier header, Validation code block present,
  filesystem paths in Validation blocks must exist under repo root);
  the spec-side counterpart to `skill-and-tool-validator`.
- Skills: `write-skill` (author/update a skill), `optimize-skill`
  (restructure an existing skill or sweep a set: split oversized
  `SKILL.md`, lift project-specific values into placeholders, harden
  prompt-injection defences), `list-skills` (live, generated index of
  every skill, grouped by family).

## Behaviour & contract

- **Generated, never cached.** `list-skills` reads the live
  `.claude/skills/*/SKILL.md` frontmatter on every run, so the index never
  goes stale.
- **Deterministic checks.** `skill-and-tool-validator`, `sandbox-lint`, and
  `symlink-lint` are heuristic/text tools with no model calls — reproducible in CI.
- **Hard vs soft rules.** The validator fails on missing frontmatter or
  broken links; advisories are warnings unless `--strict`.
- **Schema-backed metadata.** Skill frontmatter, tool README capability
  declarations, and family/index docs are treated as machine-checkable
  contracts. New checks should prefer clear enum/list validation over
  prose inference when the repository already declares the vocabulary.
- **Generated-index consistency.** Human-facing catalogue pages such as
  `docs/modes.md` may stay hand-written, but validator checks should
  compare their skill lists and counts against live `skills/*/SKILL.md`
  frontmatter so documentation drift is visible before review.
- **Pilot evidence is structured.** Experimental-family pilot reports
  should capture the same minimal fields every time: skill/family,
  target repo/profile, blocked preflights, false positives, confirmation
  points, privacy/adapter notes, and proposed spec changes.

## Out of scope

- The maintainership modes themselves.
- The spec-loop tooling, which lives in `tools/spec-loop/` and is
  documented in [`../README.md`](../README.md), not here.

## Acceptance criteria

1. `skill-and-tool-validate` enforces required frontmatter + link integrity.
2. `list-skills` generates its index from live frontmatter.
3. Each meta tool ships with its own tests.
4. Frontmatter values for `mode`, `status`, `capability`,
   `organization`, and `source` are validated against documented
   vocabularies; unknown organizations fail unless the organization
   exists under `organizations/`.
5. Capabilities declared in skill frontmatter and tool READMEs are
   present in `docs/labels-and-capabilities.md`; taxonomy entries with no
   implementation are explicitly marked reserved or future.
6. `docs/modes.md` skill lists and shipped counts are checked against
   live skill frontmatter.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **Eval coverage is complete.** Every shipped skill has a matching suite
  in `tools/skill-evals/evals/`; the soft eval-coverage check in
  `skill-and-tool-validator` warns when a newly added skill has no suite,
  keeping coverage complete going forward.
- **Frontmatter validation is still shallow.** Current validation covers
  required fields, but the next pass should make `mode`, `status`,
  `capability`, `organization`, and `source` combinations explicit and
  test-backed.
- **Capability taxonomy drift is not yet checked.** The validator should
  catch misspelled or undocumented capability values, and should surface
  taxonomy rows that no skill/tool implements unless they are marked
  reserved.
- **`docs/modes.md` is manually synced.** The plan tracks a generated
  consistency check so mode tables and shipped counts cannot silently
  drift from skill frontmatter.
- **Tool README prerequisites vary.** A prerequisites consistency pass
  should normalize older tool READMEs before tightening the validator.
- **Pilot evidence has no common shape.** Experimental-family specs all
  need adopter evidence, but there is no standard pilot-report template
  or helper yet.
