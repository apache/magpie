<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Implementation Plan — spec-loop

Maintained by the loop's **plan** mode. It is the prioritised list of
*gaps* found by comparing [`specs/`](specs/) against the actual code
(`skills/`, `tools/`, `docs/`). The **build** mode takes the single
highest-priority work item, isolates it on its own branch, implements it,
validates it, and commits: one work item, one branch, one PR.

> Priority lives here, not in the specs. The specs describe functional
> areas (unordered); this plan orders the work.

Shipped state is not tracked here. It lives in `specs/`, the code, and git
history. Confirm whether something is already built by the artifact it would
produce, not by branch ancestry.

*Last reconciled against `main` at `ff82fd35` (#1927) on 2026-11-01. The
previous plan (July 2026) was wholly stale: every item in it has shipped
(`ai-tutors/inject-knowledge-base.py --check` reports 0 stale, the AI-tutor
links are in both education READMEs, and `docs/setup/individual-use.md`,
`per-role-mcp-access.md` and `team-adoption.md` exist), so it was replaced
rather than amended.*

## In-flight (not available to build)

Open PRs: #1931 `batch-skill-write-lock`, #1930 `batch-failure-budget-proposal`,
#1929 `spec-loop-single-flight-lock`, #1928 `eval-run-journal`, #1920, #1900,
#1899, #1749, #1741. The first four also exist as local branches of the same
slug. None of the items below overlaps them.

## Work items (planned)

Priority order. Each is one branch and one PR. Each carries a verification
line: the evidence, gathered during this plan pass, that the gap is still open.

1. **Complete the `uv python install` catalog entry and give it a hint-hook
   branch.**
   The catalog entry "`uv python install` or `uv tool install` fails inside the
   sandbox" has only Symptom / Root cause / Fix; add the **Notes** section the
   other entries carry. Add a branch to `sandbox-error-hint.sh` that recognises
   the write failure under `~/.local/share/uv/` and points at that entry, with a
   case in `test_sandbox_error_hint.py`. A doctor probe is out of scope here.
   *Verified open:* `docs/setup/sandbox-troubleshooting.md:1139-1171` has no
   `### Notes` heading before the next `##`; `sandbox-error-hint.sh` has no
   branch matching `share/uv` (its only `uv` hint, line 128, is the
   `~/.local/bin` entry).
   Validation:
   ```bash
   uv run --project tools/agent-isolation --group dev python -m pytest tools/agent-isolation/tests/test_sandbox_error_hint.py
   bash -n tools/agent-isolation/sandbox-error-hint.sh
   ```
   Spec: [`specs/sandbox-diagnostics.md`](specs/sandbox-diagnostics.md).
   Branch `uv-install-hint-and-notes`.

2. **Spec-validator: cross-spec count check and gap-predicate check.**
   Add `validate_cross_spec_counts` (HARD when two specs claim different counts
   for the same skill family) and `validate_gap_predicates` (HARD when a
   Known-gap bullet's machine-evaluable close condition is already met, SOFT on
   an unannotated bullet) to `tools/spec-validator`, with tests. Deterministic,
   no model call.
   *Verified open:* `grep -rn "validate_gap_predicates\|validate_cross_spec_counts"
   tools/spec-validator/src` returns nothing; the module defines only
   `validate_frontmatter`, `validate_body`, `validate_spdx_header`,
   `validate_validation_paths`, `validate_file` and
   `validate_spec_loop_runner_fixtures`.
   Validation:
   ```bash
   uv run --directory tools/spec-validator --group dev pytest
   ```
   Spec: [`specs/spec-gap-staleness.md`](specs/spec-gap-staleness.md).
   Branch `spec-validator-gap-checks`.

3. **Plan and update beats: require evidence before queuing from a Known gap.**
   Add the evidence rule (call site, file content, or counted value; a name
   match is not admissible) to `PROMPT_plan.md` and the matching re-verify rule
   to `PROMPT_update.md`. Independent of item 2.
   *Verified open:* `grep -in "evidence\|verification" tools/spec-loop/PROMPT_plan.md`
   returns nothing.
   Validation:
   ```bash
   grep -qi "evidence" tools/spec-loop/PROMPT_plan.md
   grep -qi "evidence" tools/spec-loop/PROMPT_update.md
   bash -n tools/spec-loop/loop.sh
   ```
   Spec: [`specs/spec-gap-staleness.md`](specs/spec-gap-staleness.md).
   Branch `plan-beat-evidence-rule`.

4. **Validate `organization.md` content, not just presence.**
   `validate_organization_structure` only requires `README.md` and
   `organization.md` to exist. Make the validator fail on an `organization.md`
   that is empty or omits the keys the template marks required, so omitted keys
   stop resolving silently to framework defaults. Derive the required-key set
   from `organizations/_template/organization.md` and confirm the three in-tree
   adapters pass before landing.
   *Verified open:* `tools/skill-and-tool-validator/src/*/__init__.py:900-932`
   checks `_ORG_REQUIRED_FILES` existence only.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev pytest
   uv run --project tools/skill-and-tool-validator skill-and-tool-validate
   ```
   Spec: [`specs/organization-adapters.md`](specs/organization-adapters.md).
   Branch `org-manifest-content-check`.

5. **Pin `skill-reconciler-diff` clause patterns to the safety-baseline
   checklist.**
   The helper's `_CLAUSE1_RE`, `_CLAUSE2_RE` and `_CLAUSE3_RE` are hard-coded,
   so they can drift from `safety-baseline-checklist.md`. Add a test that
   extracts each clause's example phrasings from the checklist and asserts the
   matching regex fires on them (or load the patterns from the checklist). Stay
   within `tools/skill-reconciler-diff`.
   *Verified open:* regexes defined at
   `tools/skill-reconciler-diff/src/skill_reconciler_diff/__init__.py:174-191`;
   confirm at build time that no existing test reads the checklist file.
   Validation:
   ```bash
   uv run --project tools/skill-reconciler-diff --group dev pytest
   ```
   Spec: [`specs/skill-reconciler.md`](specs/skill-reconciler.md).
   Branch `reconciler-clause-checklist-pin`.

6. **`/magpie-setup:setup config` writes the container-gateway sockets into
   `sandbox.network.allowUnixSockets`.**
   Today the operator adds the block by hand or takes the diff that
   `setup-isolated-setup-install` Step L proposes. Add the write to the config
   flow, additive and merge-safe, honouring the existing mtime guard.
   *Verified partly:* the only `setup` section naming `allowUnixSockets` is
   `setup_preflight/sections/step-12.md:27`, which handles the legacy-directory
   move, not a first-time write. Re-confirm at build time that no config step
   writes it before starting.
   Validation:
   ```bash
   uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
   (cd tools/container-gateway && uv run --group dev pytest)
   ```
   Plus the `setup` eval suite, per `/AGENTS.md`.
   Spec: [`specs/container-gateway.md`](specs/container-gateway.md).
   Branch `setup-config-gateway-sockets`.

## Notes & discoveries

- `git push` and `gh pr create` are intentionally not run by the loop.
- Item 2 and 3 serve the same spec but are separate branches: validator code
  and prompt text have different validation and different reviewers.
- Deferred by design, not build items: GitLab write operations (tracked in
  #305, large, needs its own design), PMC-member nomination and emeritus
  handling (human judgement until a spec turns them into a rule), and the
  low-confidence ASF-coupling advisories.
- Not planned because evidence was not gathered this pass: the "frontmatter
  combination validation" gap in `meta-and-quality-tooling.md`. Verify it
  against `validate_frontmatter` in `skill-and-tool-validator` before queuing.
- Agentic Autonomous is deliberately off and has no work items.
