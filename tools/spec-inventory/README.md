<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [spec-inventory](#spec-inventory)
  - [`spec-inventory`](#spec-inventory-1)
  - [`spec-scope`](#spec-scope)
  - [Prerequisites](#prerequisites)
  - [Usage](#usage)
  - [Run tests](#run-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# spec-inventory

**Capability:** substrate:framework-dev + substrate:analytics

**Harness:** agnostic

Two deterministic `uv` tools that help the spec-loop navigate the
repository without scanning it from scratch each iteration.

## `spec-inventory`

Emits a compact routing inventory for the spec-loop prompts. It
summarizes spec frontmatter, where-it-lives hints, validation commands,
known gaps, skill frontmatter, and tool/test presence so agents can
choose what to read next without first scanning the whole repository.

The output is a routing aid, not proof. Prompts still require direct file
reads or code search before declaring behaviour present or absent.

## `spec-scope`

Maps a list of changed file paths to the spec files most likely relevant
to those changes. Used by the spec-loop `update` beat to focus the agent
on the specs whose subjects appear in the diff, rather than requiring
the agent to derive the mapping itself.

Path patterns are extracted from each spec's `## Where it lives` section:
backtick-quoted path tokens (containing `/`) are treated as prefix
patterns, and `Skill: \`<name>\`` bullets produce a `skills/<name>`
pattern. `.claude/skills/magpie-<name>` symlink entries are expanded to
`skills/<name>` aliases so that skill-name patterns resolve correctly.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`, `ruff`, and `mypy`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline; reads local specs, skills, and tool
  metadata from the repository checkout.

## Usage

```bash
# Routing inventory
uv run --project tools/spec-inventory spec-inventory
uv run --project tools/spec-inventory spec-inventory --brief --max-where 1 --max-validation 1 --max-gaps 1
uv run --project tools/spec-inventory spec-inventory --json

# Scope mapper — pipe changed paths from git diff, get relevant specs back
git diff --name-only HEAD~1..HEAD -- .claude/skills tools docs/modes.md | \
    uv run --project tools/spec-inventory spec-scope

# Or pass paths as positional arguments
uv run --project tools/spec-inventory spec-scope tools/gmail/tool.md .claude/skills/magpie-pr-management-triage
```

## Run tests

```bash
uv run --project tools/spec-inventory --group dev pytest tools/spec-inventory/tests
```
