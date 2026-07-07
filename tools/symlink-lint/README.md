<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`symlink-lint`](#symlink-lint)
  - [Rules](#rules)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [Wiring](#wiring)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `symlink-lint`

**Capability:** substrate:framework-dev

**Harness:** agnostic

Lints the framework's **self-adoption skill symlinks** — the canonical
`.agents/skills/` links and their relays — against two invariants. This is
the single place the rationale lives; the module, the prek hook, and the
error output all point back here.

The framework's wiring is **one-directional** (see
[`skills/setup/agents.md`](../../skills/setup/agents.md)): the canonical
link lives under `.agents/skills/` and points *into* the source tree, and
every other agent dir (`.claude/`, `.github/`, `.windsurf/`, `.goose/`,
`.kiro/`, …) carries a thin relay that points at the canonical entry.

## Rules

1. **No cycles.** A symlink must not resolve to its own directory or an
   ancestor of it. Such a link makes a recursive `**/SKILL.md` scanner that
   follows symlinks (opencode's skill loader does) re-enter the directory
   until an internal depth cap, yielding looped paths like
   `skills/x/x/x/.../SKILL.md`. This rule is convention-agnostic — it names
   no agent dir, so a new one needs no change here.
2. **Relay correctness.** For a `magpie-<skill>` link under an
   `<agent>/skills/` directory: the canonical entry under `.agents/skills/`
   must point at `../../skills/<skill>`, and every other agent dir's relay
   must point at `../../.agents/skills/magpie-<skill>` (through the
   canonical, not straight at source). Catches relays that bypass
   `.agents/` — acyclic, so rule 1 alone would miss them.

**Dangling / unresolvable links are skipped**, never flagged: an adopter's
canonical links legitimately dangle until the gitignored `.apache-magpie/`
snapshot is installed. Broken-target detection is `setup verify`'s job.

## Prerequisites

- **Runtime:** Python 3.11+ (stdlib only) — no third-party dependencies; run it directly with `python3`, or as the console script `symlink-lint`.
- **CLIs:** `git` (optional) — locates the repo root via `git rev-parse --show-toplevel`; falls back to the current working directory.
- **Credentials / auth:** None.
- **Network:** None.

## How to use

```bash
python3 tools/symlink-lint/src/symlink_lint/__init__.py
# or, once the workspace is synced:
uv run --project tools/symlink-lint symlink-lint
```

Exit `0` if clean; `1` otherwise, with each offender printed to stderr.

## Wiring

Runs as the `symlink-lint` [prek](https://github.com/j178/prek) hook
(`.pre-commit-config.yaml`), fired on any staged symlink and always on
`prek run --all-files` (CI). Behaviour is locked by the pytest suite under
[`tests/`](tests/), run by the workspace `pytest` hook + CI matrix.

## Tests

```bash
uv run --project tools/symlink-lint pytest
```
