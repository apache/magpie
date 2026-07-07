<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #412 asks you to add a `--output-format` flag to the `report`
command so that CI pipelines can get JSON output instead of plain text.

**Background context.** The `report` command (`src/acme/cli/report.py`)
currently writes a fixed plain-text summary to stdout. Several CI users
have requested a JSON mode so downstream tools can parse the results
without screen-scraping. The change is self-contained: only the output
serialisation layer needs to change.

**Where to start.**
- `src/acme/cli/report.py` — find the `run_report` function and its
  argparse options; add `--output-format` with choices `["text", "json"]`
  and default `"text"`.
- `tests/cli/test_report.py` — look at the existing tests for the
  `report` command; add two new test cases, one for each format.

**What "done" looks like.** Running `acme report --output-format json`
prints a JSON object containing the same fields the plain-text report
lists. Running `acme report` (no flag) still prints plain text. A new
test passes for both modes.

**Where to ask.** Questions? Post on the project's GitHub Discussion
at https://github.com/example/acme/discussions.

---
*This explanation was drafted by an AI assistant and reviewed by a
maintainer before posting. Please ask if anything is unclear.*
