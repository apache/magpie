<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [spec-validator](#spec-validator)
  - [Prerequisites](#prerequisites)
  - [What it checks](#what-it-checks)
  - [Usage](#usage)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# spec-validator

**Capability:** substrate:framework-dev

**Harness:** agnostic

Validates spec files in `tools/spec-loop/specs/` — the counterpart to
`tools/skill-and-tool-validator/` for the spec side of the framework.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`, `ruff`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline against local spec files.

## What it checks

For every `.md` file that carries a YAML frontmatter block:

1. **Required frontmatter keys** — `title`, `status`, `kind`, `mode`,
   `source`, `acceptance`.
2. **Valid `status`** — `stable` | `experimental` | `proposed` | `off`.
3. **Valid `kind`** — `feature` | `fix` | `docs` | `chore`.
4. **Valid `mode`** — `Triage` | `Mentoring` | `Drafting` | `Pairing` | `infra`.
5. **Non-empty `acceptance` list** — at least one `- item` entry.
6. **Required body sections** — `## What it does`, `## Where it lives`,
   `## Behaviour & contract`, `## Out of scope`, `## Acceptance criteria`,
   `## Validation`.
7. **Validation section has a fenced code block** — at least one `` ```…``` ``
   block so build-loop backpressure commands are always explicit.
8. **Known-gap close conditions** — a `## Known gaps` bullet may carry
   `<!-- gap-closes-when: <predicate> -->`, where the predicate is
   `path-exists:<path>`, `symbol-called:<path>::<name>` (a call from
   non-test code, not counting recursion), `skill-count:<family>=<n>`, or
   `none (narrative)`.
   A predicate that now holds, or one that is malformed or unresolvable, is HARD;
   a bullet with no predicate is a SOFT advisory.
9. **Cross-spec family counts** — an "N-skill family" claim that disagrees
   with another spec, or with the number of `SKILL.md` files carrying that
   `family:`, is HARD.

HARD violations fail the run; SOFT advisories are printed and never do.

Files without frontmatter (e.g. `README.md`, `overview.md`) are silently
skipped — they are index/overview docs, not functional specs.

## Usage

```bash
# Run against the default spec directory
uv run --project tools/spec-validator spec-validate

# Run against a specific directory or file
uv run --project tools/spec-validator spec-validate tools/spec-loop/specs/

# Run the test suite
uv run --project tools/spec-validator --group dev pytest
```
