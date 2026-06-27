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
- **Deterministic checks.** `skill-and-tool-validator` and `sandbox-lint` are
  heuristic/text tools with no model calls — reproducible in CI.
- **Hard vs soft rules.** The validator fails on missing frontmatter or
  broken links; advisories are warnings unless `--strict`.

## Out of scope

- The maintainership modes themselves.
- The spec-loop tooling, which lives in `tools/spec-loop/` and is
  documented in [`../README.md`](../README.md), not here.

## Acceptance criteria

1. `skill-and-tool-validate` enforces required frontmatter + link integrity.
2. `list-skills` generates its index from live frontmatter.
3. Each meta tool ships with its own tests.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

## Known gaps

- **Eval coverage is complete.** All 44 shipped skills have a matching
  suite in `tools/skill-evals/evals/`; the soft eval-coverage check in
  `skill-and-tool-validator` (check #8) warns when a newly added skill
  has no suite, keeping coverage complete going forward.
- Other gaps appear as new quality checks worth adding — recorded by the
  plan pass. The spec validator (analogous to the skill validator) and
  the ASF-coupling advisory lint are two recent additions to this surface.
