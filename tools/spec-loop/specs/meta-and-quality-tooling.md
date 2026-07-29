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
  tools/pilot-report-validator/, tools/vendor-neutrality-score/,
  tools/preflight-audit/, tools/spec-inventory/, and the write-skill /
  list-skills utility skills.
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
- `tools/spec-inventory/` — deterministic `uv` tool that summarizes
  specs, skills, and tools into a compact routing inventory for spec-loop
  prompts.
- `tools/pilot-report-validator/` — validates adopter pilot-report files
  against the required schema defined in `docs/pilot-report-template.md`.
  Checks required frontmatter keys (`skill`, `date`, `target_repo`,
  plus family-specific required fields), blocked-preflight list
  structure, and section presence. Pilot reports are the primary
  evidence source for advancing a skill from `experimental` to `stable`.
  Capability: `substrate:framework-dev`. Stdlib-only, offline.
- `tools/vendor-neutrality-score/` — deterministic `uv` tool that scores
  Magpie's vendor neutrality from repository metadata alone (no network,
  no model calls). For each capability contract, answers: does Magpie
  already work across more than one vendor, and is any skill locked to a
  vendor with no alternative? Reads `tools/*/README.md` and
  `skills/*/SKILL.md` locally. Capability: `substrate:framework-dev +
  substrate:analytics`.
- `tools/preflight-audit/` — dry-runs the bulk-mode pre-flight classifier
  in live mode (via `gh api graphql`) or replay mode (offline, from a
  cached snapshot) against a real tracker. Measures skip-rate before and
  after any rule change, closing the tune-then-verify loop so rule edits
  are backed by evidence. Capability: `substrate:analytics`.
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
7. `spec-inventory` emits a compact, deterministic routing map for specs,
   skills, and tools, and has its own tests.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/spec-inventory --group dev pytest tools/spec-inventory/tests
```

## Known gaps

- **Eval coverage is complete.** All 63 shipped skills have a matching
  suite in `tools/skill-evals/evals/`; the soft eval-coverage check in
  `skill-and-tool-validator` (check #8) warns when a newly added skill has
  no suite, keeping coverage complete going forward.
- **Frontmatter validation is still shallow.** Current validation covers
  required fields, but the next pass should make `mode`, `status`,
  `capability`, `organization`, and `source` combinations explicit and
  test-backed.
- **Capability taxonomy coverage is checked.**
  `validate_capability_taxonomy_coverage` runs from `run_validation()` and
  reports undocumented capability values or taxonomy rows with no
  implementation unless they are marked reserved.
- **`docs/modes.md` consistency is checked.**
  `validate_modes_doc_consistency` compares the mode tables and shipped
  counts with live skill frontmatter so they cannot silently drift.
- **Tool README prerequisite fields are enforced.** The HARD
  `tool-prerequisites-fields` check in `validate_tools` requires the runtime,
  CLI, credentials/auth, and network sub-fields (or the documented
  delegation shorthand); a separate normalization pass is no longer pending.
- **Pilot evidence shape is now defined and validated.** `docs/pilot-report-template.md`
  defines the required frontmatter schema and body sections; `tools/pilot-report-validator/`
  enforces the schema on every `.md` file with a YAML frontmatter block.
  The "no common shape" gap is closed; the remaining gap is adoption —
  no adopter pilot has yet submitted a validated report against the template.
- **Vendor-neutrality measurement is available but unscheduled.** `tools/vendor-neutrality-score/`
  ships and can be run ad hoc, but is not yet wired into CI or the
  build loop. Score drift is not automatically surfaced.
