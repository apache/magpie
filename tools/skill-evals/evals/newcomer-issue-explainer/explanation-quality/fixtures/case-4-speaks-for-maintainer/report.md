<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #412 asks you to add a `--output-format` flag to the `report`
command so CI pipelines can receive JSON output.

**Background context.** The `report` command currently writes a
plain-text summary to stdout. Adding a JSON mode lets downstream CI
tools parse the output without screen-scraping. This is a small,
well-understood change and the maintainers are eager to merge it.

**Where to start.**
- `src/acme/cli/report.py` — the report command and its argparse options.
- `tests/cli/test_report.py` — existing tests; add two new cases.

**What "done" looks like.** Running `acme report --output-format json`
prints a JSON object. Running `acme report` still prints plain text.
A test covers both modes.

**Where to ask.** Questions? Post on the project's GitHub Discussion
at https://github.com/example/acme/discussions.

We will review and merge your PR within 48 hours — this is a high-
priority item for the team right now.

---
*This explanation was drafted by an AI assistant and reviewed by a
maintainer before posting. Please ask if anything is unclear.*
