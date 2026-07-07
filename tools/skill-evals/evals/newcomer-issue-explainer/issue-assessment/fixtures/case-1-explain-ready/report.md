<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #412

State: open
Labels: good first issue, help wanted
Title: Add `--output-format` flag to the `report` command
Body:
The `report` subcommand currently always writes to stdout in plain text.
Users running it in CI pipelines want a JSON output option so the results
can be parsed by downstream tooling.

Add a `--output-format` flag accepting `text` (default) and `json`.
When `json` is selected the command prints a JSON object with the same
fields the plain-text report lists.

Relevant files:
- `src/acme/cli/report.py` — the report command and its argparse setup
- `tests/cli/test_report.py` — existing CLI tests; add a new test covering
  both format options

Acceptance criteria: `report --output-format json` prints valid JSON;
`report` (no flag) still works as before; a test covers both modes.
