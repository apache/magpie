<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #412 asks you to add a `--output-format` flag to the `report`
command so that CI pipelines can receive JSON output.

**Background context.** The `report` command currently writes a
plain-text summary to stdout. Adding a JSON mode lets downstream CI
tools parse the output without screen-scraping.

**Where to start.**
- `src/acme/cli/report.py` — the report command and its argparse options.
- `tests/cli/test_report.py` — existing tests for the report command.

**Where to ask.** Questions? Post on the project's GitHub Discussion
at https://github.com/example/acme/discussions.

---
*This explanation was drafted by an AI assistant and reviewed by a
maintainer before posting. Please ask if anything is unclear.*
