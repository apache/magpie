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
  (soft check: warns when a skill has no eval suite). A skill's `name:` must
  equal the directory its `SKILL.md` actually lives in — the family-plugin
  directory name, which is the alias every harness invokes it by (#1361).
  CLI: `skill-and-tool-validate`.
- `tools/skill-evals/` — harness for measuring skill behaviour. A case whose
  CLI produced no usable JSON reports ERROR unless something asserts on a
  synthetic wrap key (`raw_output` / `stderr` / `exit_code`, via
  `expected.json` or an `assertions.json` `field`) — a wrap nothing addresses
  compares nothing, and passing it turned an unauthenticated CLI into a green
  run. Every fixture read is contained to the eval tree by resolved path:
  `magpie-run-evals.sh` runs outside the sandbox, so its wrapper resolves its
  target against `tools/skill-evals/evals` and the runner resolves every path
  it reads — `report.md`, `step-config.json`'s `skill_md` — rejecting a
  symlink or a `..` walk that leads out, while symlinks that stay inside the
  tree keep working (#1315). A prose-field verdict the grader drops from a
  batched rubric is re-asked once, and only silence that survives the retry
  is reported; a verdict the grader actually gave is never re-asked, so a NO
  cannot become a YES by asking twice (#1341).
- `tools/sandbox-lint/` — lints the sandbox/permissions configuration.
- `tools/symlink-lint/` — lints the framework's self-adoption skill
  symlinks: rejects cyclic symlinks, misdirected relays (canonical/
  relay target-correctness), and incomplete self-adoption symlink sets.
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
- Skills: `write-skill` (author/update a skill; its Step 7 runs
  `optimize-skill` on every new skill before it ships, unconditionally),
  `optimize-skill` (restructure an existing skill or sweep a set: split
  oversized `SKILL.md`, lift project-specific values into placeholders,
  harden prompt-injection defences, extract embedded code, and — in a
  separate rewrite pass, `rewrite.md` — rewrite prose paragraph by
  paragraph with the maintainer writing every word), `list-skills` (live,
  generated index of every skill, grouped by family).

- `tools/skill-token-count/` measures full local skill files with pinned
  `tiktoken` / `cl100k_base`, generates the mode-economics table, and checks
  drift through prek and a dedicated path-filtered CI workflow.

## Behaviour & contract

- **Generated, never cached.** `list-skills` reads live `SKILL.md`
  frontmatter on every run, so the index never goes stale.
- **Installation-aware discovery.** `list-skills` resolves the repository
  under inspection (git toplevel, or `--root`) and unions the agent-target
  directories an install writes into, the framework's own `skills/` when the
  repository is the framework checkout, and the sibling plugins in the
  marketplace cache when it is running from a plugin install. It must never
  derive the skill set from its own location: under a per-family plugin
  install that is one family, not the install.
- **Declared family, never inferred.** Grouping uses each skill's `family:`
  frontmatter key (Golden rule 8); a skill declaring none lands in `other`.
  Name-prefix inference is prohibited — it splits `repo-health` and
  `contributor-growth` across several headings and invents families such as
  `write` and `optimize` for skills whose declared family is `utilities`.
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
- **Skill size has measured budgets.** `optimize-skill` targets 5,000
  tokens for a `SKILL.md` body (pre-flight block excluded) and 200 for
  `description` plus `when_to_use`, both set at the catalogue median and
  measured with `skill-token-count` before and after every pass; the
  always-on frontmatter budget is spent on first, because it is paid in
  every session for every skill (#1331, #1332).
  Every pass other than the rewrite is behaviour-preserving: moved bytes
  are identical bytes, heading level excepted, and a heading that moves
  takes its references with it — eval `step-config.json` `step_heading`
  / `also_include` entries, anchor links, anything matching on the
  string (#1334).
  The extract-code pass moves a complete, deterministic program the model
  never needs to read out of the body — to `scripts/` beside the skill, a
  `tools/` project, or the vetted-ops catalogue when it would otherwise
  prompt on every run — byte-identical; placeholder-bearing command
  templates are instructions, not programs, and stay inline (#1335,
  #1338).
  The target's eval suite runs before the first pass and after the last;
  a case that flips on an unchanged tree is reported as such to the
  maintainer rather than read as a verdict, and a skill with no suite
  says so (#1332).
  Style rules the rewrite pass learns are proposed as a diff into a
  bullets-only region of `optimize-skill/SKILL.md` in this repository —
  never headings, which would move its `surface_hash` — and into an
  override file for adopters (#1331).
- **CI runs the prek hooks in two shapes.** On a pull request the hooks
  see only the PR's own diff (`--from-ref` / `--to-ref`); on a push to
  `main` they run `--all-files`. The lychee link check is exempt from the
  scoping and runs whole-repo on both events, because its file filter
  only decides whether it fires. A green PR check is therefore not a
  whole-repo result, which is why `prek run --all-files` before pushing
  is a required pre-flight (#1317).
- **Eval trust roles stay separate.** Mock tool output in `report.md` enters the user turn as untrusted data.
  Repository policy read from a trusted revision may enter through a case-level `trusted-context.md`, which the runner appends only to the system prompt.

- **Token measurement provenance.** Counts include UTF-8 file content with
  LF-normalized line endings. A content manifest hash identifies inputs without
  depending on Git history or commit time. A descriptive UTC date changes only
  on regeneration after drift; checks preserve it. Vocabulary preparation is
  explicit and checksum-verified; missing or corrupt caches block measurement
  before a network request. Skill edits,
  additions, removals, and renames invalidate the table. These file counts
  are distinct from estimated session costs and runtime percentiles.
- **Runtime evidence is scoped.** An opt-in replay benchmark captures actual
  CLI-reported input, cache, and output usage for synthetic full-entrypoint
  decision-to-draft/report tasks. It records prompts' source hashes, model/CLI
  versions, failures, and responses. Sample p50/p90 use documented interpolation;
  they are not population estimates for live workflows. CI never runs paid
  model benchmarks automatically. Before any paid call, case modes must match
  the selected skill frontmatter. Summaries group by both mode and skill;
  they must not pool different skills into a mode-wide percentile. Published
  metadata corrections preserve original usage, responses, and prompt hashes.
  Patch-drafting replays do not certify patch application or passing tests.

## Out of scope

- The maintainership modes themselves.
- The spec-loop tooling, which lives in `tools/spec-loop/` and is
  documented in [`../README.md`](../README.md), not here.

## Acceptance criteria

1. `skill-and-tool-validate` enforces required frontmatter + link integrity.
2. `list-skills` generates its index from live frontmatter, covering every
   install method (snapshot, framework checkout, marketplace plugin) and
   grouping by declared `family:`.
3. Each meta tool ships with its own tests.
4. Frontmatter values for `mode`, `status`, `capability`,
   `organization`, and `source` are validated against documented
   vocabularies; unknown organizations fail unless the organization
   exists under `organizations/`.
5. Capabilities declared in skill frontmatter and tool READMEs are
   present in `docs/labels-and-capabilities.md`; taxonomy entries with no
   implementation are explicitly marked reserved or future. The tool
   READMEs' `**Capability:**` lines also generate `.github/labeler.yml`
   (`tools/dev/generate-labeler-config.py`, kept in sync by a prek hook),
   which pre-applies `contract:*` / `substrate:*` labels to new PRs.
6. `docs/modes.md` skill lists and shipped counts are checked against
   live skill frontmatter.
7. `spec-inventory` emits a compact, deterministic routing map for specs,
   skills, and tools, and has its own tests.
8. `skill-evals` keeps mock tool output in the user turn and appends optional
   trusted repository context only to the system prompt.
9. `skill-evals` never reports PASS for a case in which nothing was graded:
   a CLI that emits no JSON, or exits non-zero, errors unless the suite
   explicitly asserts on the wrapped output.
10. `skill-evals` reads no fixture whose resolved path leaves
    `tools/skill-evals/evals`, and re-asks a dropped grader verdict once
    without ever re-asking a verdict the grader gave.
11. The validator fails a skill whose `name:` does not match the
    directory holding its `SKILL.md`.

## Validation

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
uv run --project tools/skill-evals --group dev pytest tools/skill-evals/tests
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
- **Capability taxonomy drift is now checked.**
  `validate_capability_taxonomy_coverage` parses the Axis 1 / Axis 2
  vocabulary tables in `docs/labels-and-capabilities.md`, surfaces
  taxonomy rows that no skill/tool implements (entries marked
  *(reserved)* / *(future)* are exempt), and cross-checks the
  `SKILL_CAPABILITIES` / `TOOL_CAPABILITIES` code constants against the
  doc — all SOFT advisories. Undocumented frontmatter capability values
  are rejected by skill validation separately.
- **`docs/modes.md` is no longer manually synced.**
  `validate_modes_doc_consistency` compares the doc's per-mode tables
  against live skill frontmatter — missing skills, mode mismatches,
  skill-count mismatches, and unlisted skills — as SOFT advisories.
- **Tool README prerequisites are normalized and enforced.** The HARD
  `tool-prerequisites-fields` check requires the bold sub-field labels
  (**Runtime:**, **CLIs:**, **Credentials / auth:**, **Network:**) or
  the pure-contract delegation shorthand in every tool README, so the
  normalize-then-tighten ordering this bullet used to track is done.
- **Pilot evidence shape is now defined and validated.** `docs/pilot-report-template.md`
  defines the required frontmatter schema and body sections; `tools/pilot-report-validator/`
  enforces the schema on every `.md` file with a YAML frontmatter block.
  The "no common shape" gap is closed; the remaining gap is adoption —
  no adopter pilot has yet submitted a validated report against the template.
- **Vendor-neutrality measurement is available but unscheduled.** `tools/vendor-neutrality-score/`
  ships and can be run ad hoc, but is not yet wired into CI or the
  build loop. Score drift is not automatically surfaced.
