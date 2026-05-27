<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Meta & quality tooling
status: stable
kind: feature
mode: infra
source: >
  README.md § Skill families (utilities) and AGENTS.md § Reusable skills.
  Implemented by tools/skill-validator/, tools/skill-evals/,
  tools/sandbox-lint/, tools/dashboard-generator/, tools/probe-templates/,
  and the write-skill / list-steward-skills utility skills.
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

- `tools/skill-validator/` — validates `SKILL.md` frontmatter (required
  `name`, `description`, `license`), internal link integrity, and
  placeholder conventions. CLI: `skill-validate`.
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
  presence); the spec-side counterpart to `skill-validator`.
- Skills: `write-skill` (author/update a skill), `list-steward-skills`
  (live, generated index of every skill, grouped by family).

## Behaviour & contract

- **Generated, never cached.** `list-steward-skills` reads the live
  `.claude/skills/*/SKILL.md` frontmatter on every run, so the index never
  goes stale.
- **Deterministic checks.** `skill-validator` and `sandbox-lint` are
  heuristic/text tools with no model calls — reproducible in CI.
- **Hard vs soft rules.** The validator fails on missing frontmatter or
  broken links; advisories are warnings unless `--strict`.

## Out of scope

- The maintainership modes themselves.
- The spec-loop tooling, which lives in `tools/spec-loop/` and is
  documented in [`../README.md`](../README.md), not here.

## Acceptance criteria

1. `skill-validate` enforces required frontmatter + link integrity.
2. `list-steward-skills` generates its index from live frontmatter.
3. Each meta tool ships with its own tests.

## Validation

```bash
uv run --project tools/skill-validator --group dev pytest
uv run --project tools/skill-validator --group dev skill-validate
```

## Known gaps

- **Eval coverage is incomplete** — the harness has ~15 suites but the
  repo has more skills than that; skills added before the per-skill-eval
  convention have no suite. Back-filling one suite per uncovered skill is
  a tracked work item.
- Other gaps appear as new quality checks worth adding (e.g. a spec
  validator analogous to the skill validator) — recorded by the plan pass.
