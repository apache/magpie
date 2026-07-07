<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [skill-and-tool-validator](#skill-and-tool-validator)
  - [Prerequisites](#prerequisites)
  - [What it checks](#what-it-checks)
    - [Hard rules (failure)](#hard-rules-failure)
    - [SOFT advisories (warning, do not fail)](#soft-advisories-warning-do-not-fail)
  - [Run](#run)
  - [Design notes](#design-notes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# skill-and-tool-validator

**Capability:** substrate:framework-dev

**Harness:** agnostic

Validate framework skill definitions — YAML frontmatter, internal
link integrity, and placeholder conventions.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no third-party
  runtime dependencies). The `dev` group pulls `pytest`, `ruff`, `mypy`.
- **CLIs:** None beyond the runtime. `git` is used only for the optional
  trigger-phrase-preservation check and is silently skipped when git or
  the base ref is unavailable.
- **Credentials / auth:** None.
- **Network:** Runs fully offline against local skill files.

## What it checks

### Hard rules (failure)

1. **YAML frontmatter** — Every `SKILL.md` must have a valid
   frontmatter block with required keys (`name`, `description`,
   `license`).
2. **Internal link integrity** — Relative markdown links between
   skill files and docs must point to existing files and anchors.
3. **Placeholder convention** — Skill docs must use `<PROJECT>`,
   `<upstream>`, and `<tracker>` instead of hardcoded project names.
4. **Name convention** — Every `SKILL.md` `name:` must be
   `magpie-<directory-name>`. Framework skills install under a
   `magpie-` namespace prefix (`skills/issue-triage/` →
   `.claude/skills/magpie-issue-triage`), so the frontmatter name
   must match that installed name.

### SOFT advisories (warning, do not fail)

5. **Principle compliance** — Heuristic warnings when frontmatter
   carries content the LLM router doesn't need:
   - **Action-inventory** in `description` (≥ 5 commas in one sentence)
   - **Distinct-from-sibling-skill** clauses (`Unlike`, `Distinct from`, `Counterpart to`, `rather than`)
   - **Chain-handoff** narrative (`Hands off to`, `ready for X to take over`)
   - **Parenthetical rationale** (parens containing `typically`, `implies`, `because`, `since`, `is required first`, `needs to`, `requires`)
   - **Criteria-source path** (`process step N`, `Step Na`, ``docs/X.md``, `documented in …`)
6. **Trigger-phrase preservation** — Compares quoted phrases in
   `when_to_use` against a base ref (default `origin/main`) and
   warns when any phrase has been dropped. Silently skipped when
   git or the base ref is unavailable. Override via
   `SKILL_VALIDATOR_BASE_REF`.

SOFT advisories are surfaced as warnings on stderr without failing
the run. The reviewer has the final say on borderline cases.

## Run

From the repo root:

```bash
uv run --project tools/skill-and-tool-validator --group dev pytest
```

Or install and run as CLI:

```bash
uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate
```

CLI flags:

- `--strict` — promote SOFT categories to hard failures.
- `--skip-categories principle_compliance,trigger_preservation` —
  skip given violation categories entirely (silent).

## Design notes

- **stdlib-only** — no external dependencies. The frontmatter parser
  is a lightweight text heuristic rather than a full YAML loader,
  because the frontmatter in skills is intentionally simple.
- **Complements `check-placeholders.sh`** — both tools share the same
  forbidden-pattern and allowlist lists. `check-placeholders.sh` runs
  as a pre-commit hook; this package runs as pytest in CI.
