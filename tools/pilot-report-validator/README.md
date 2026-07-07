<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [pilot-report-validator](#pilot-report-validator)
  - [Prerequisites](#prerequisites)
  - [What it checks](#what-it-checks)
  - [Usage](#usage)
  - [Writing a pilot report](#writing-a-pilot-report)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# pilot-report-validator

**Capability:** substrate:framework-dev

**Harness:** agnostic

Validates adopter pilot-report files against the required schema defined
in [`docs/pilot-report-template.md`](../../docs/pilot-report-template.md).
Pilot reports are the feedback artefact that documents an adopter's
end-to-end run of an experimental skill family, and are the primary
evidence source for advancing a skill from `experimental` to `stable`.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies). The `dev` group pulls `pytest`, `ruff`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline against local report files.

## What it checks

For every `.md` file that carries a YAML frontmatter block:

1. **Required frontmatter keys** — `skill`, `date`, `target_repo`,
   `profile`.
2. **Valid `profile` value** — `asf` | `non-asf` | `custom`.
3. **No unfilled placeholders** — frontmatter values must not contain
   un-substituted `<...>` tokens, and `date` must be a real ISO 8601
   date (`YYYY-MM-DD`).
4. **Required body sections** — `## Skill or family`,
   `## Target repo and profile`, `## Blocked preflights`,
   `## False positives`, `## Confirmation points`,
   `## Privacy and adapter notes`, `## Proposed spec changes`.

The frontmatter block must be at the very top of the file — YAML
frontmatter placed lower in the document is not detected. Files without
a top-of-file frontmatter block (e.g. README files) are silently
skipped. `docs/pilot-report-template.md` ships with placeholder
frontmatter values, so running the validator on the unedited template
reports those placeholders until you fill them in.

## Usage

```bash
# Validate a single filled-in report
uv run --project tools/pilot-report-validator \
    pilot-report-validate path/to/my-pilot-report.md

# Validate every report in a directory
uv run --project tools/pilot-report-validator \
    pilot-report-validate path/to/reports/

# Run the test suite (use --directory, not --project, to avoid the
# duplicate-`tests`-package collision when run from the repo root)
uv run --directory tools/pilot-report-validator --group dev pytest
```

## Writing a pilot report

Copy `docs/pilot-report-template.md`, fill in the frontmatter and each
section, then validate with this tool before sharing.  See the template
for detailed per-section instructions.
