<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #42

Title: Add `--no-color` flag to the `report` command

Body:
The `report` subcommand always outputs ANSI colour codes, which breaks
output in terminals that don't support them and in CI pipelines that
capture plain text. Add a `--no-color` flag that suppresses ANSI escape
sequences.

Where to look:
- `src/acme/cli/report.py` — the `report` command definition and
  `_format_row()` helper that emits colour codes
- `tests/cli/test_report.py` — existing CLI output tests

Definition of done:
- Running `acme report --no-color` produces plain text output with no
  ANSI codes.
- Running `acme report` without the flag continues to produce coloured
  output.
- A new test covers both paths.

Estimated effort: ~2 hours.

Labels: enhancement
