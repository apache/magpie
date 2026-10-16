<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Plan: security tracker backends](#plan-security-tracker-backends)
  - [Tasks](#tasks)
  - [Verification](#verification)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Plan: security tracker backends

Implementation plan for [Security tracker backends](2026-10-15-security-tracker-backends.md).
Per the [designs convention](README.md), this plan is folded into the design and deleted once the work has landed and been piloted.

## Tasks

| # | Task | Files | Status |
|---|---|---|---|
| 1 | Contract: operations, outputs, exit codes, confidentiality guard, publishing | `tools/security-tracker/README.md`, `contract.md` | Done |
| 2 | Local backend: metadata (front matter, bold fields), sections, comments, rollup | `tools/local-tracker/src/magpie_local_tracker/{metadata,sections}.py` | Done |
| 3 | Local backend: descriptor and detection of an existing format | `descriptor.py`, `detect.py` | Done |
| 4 | Local backend: store operations, access guard, folder-per-state moves | `store.py` | Done |
| 5 | Local backend: Git and SVN `pending` / `publish` scoped to the tracker root | `vcs.py` | Done |
| 6 | Local backend: CLI, README, tests (incl. real Git and SVN publish) | `cli.py`, `README.md`, `tests/` | Done |
| 7 | Jira backend: REST client, wiki-markup fields, rollup comment, security-level guard, tests | `tools/jira/` | Done |
| 8 | Skill wiring: shared `tracker-backend` block in the 12 tracker-touching security skills | `tools/dev/blocks/tracker-backend.md`, `plugins/magpie-security/skills/*/SKILL.md` | Done |
| 9 | Config: `tracker.platform`, `tracker.local.*`, `tracker.jira.*`; framework baseline `platform: github` | `plugins/magpie-setup/templates/project.md`, `organizations/independent/organization.md` | Done |
| 10 | Setup: Step 3a — choose backend, detect format, confirm access, write descriptor | `plugins/magpie-setup/skills/setup/config.md` | Done |
| 11 | Taxonomy: `contract:security-tracker` in the validator, capability docs, labeler | `tools/skill-and-tool-validator`, `docs/labels-and-capabilities.md`, `.github/labeler.yml` | Done |
| 12 | Token restamp for the edited skills; `prek run --all-files` | `measured_tokens:` frontmatter | Done |
| 12a | vetted-ops: `[tracker]` policy, translation of every tracker operation, six new operations, refusal of the rest, tests incl. an end-to-end run against the local tracker | `tools/vetted-ops/` | Done |
| 12b | Contract: skill-command → vetted-operation → backend table; shared block points skills at vetted operations | `tools/security-tracker/contract.md`, `tools/dev/blocks/tracker-backend.md` | Done |
| 13 | Security-skill eval suites (self-eval) — 308/313; the 5 failures come from prompt files this change does not touch | `tools/skill-evals/evals/security-*` | Done (cross-model pass to do) |
| 14 | Create the `contract:security-tracker` label on `apache/magpie` | GitHub labels | To do (maintainer) |
| 15 | Pilot: one SVN-files project, one Jira project | adopter repos | To do |
| 16 | Spec: record the contract and backends in `tools/spec-loop/specs/adapters.md` | specs | Done |

## Verification

- `uv run --project tools/local-tracker --group dev pytest tools/local-tracker/tests`
- `uv run --project tools/jira --group dev pytest tools/jira/tests`
- `uv run --project tools/vetted-ops --group dev pytest tools/vetted-ops/tests`
- `python3 tools/dev/check-shared-blocks.py`
- `prek run --all-files`
