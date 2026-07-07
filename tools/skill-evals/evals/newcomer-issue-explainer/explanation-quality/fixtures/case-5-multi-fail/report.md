<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #412 asks you to add a `--output-format` flag to the `report`
command so CI pipelines can receive JSON output.

**Background context.** The `report` command currently writes a
plain-text summary to stdout. Adding a JSON mode lets downstream CI
tools parse the output without screen-scraping.

**Where to start.** Find the report command in the source tree and
update its argument parser to support the new flag.

**What "done" looks like.** Running `acme report --output-format json`
prints a JSON object. Running `acme report` still prints plain text.
A test covers both modes.

---
*This explanation was drafted by an AI assistant and reviewed by a
maintainer before posting. Please ask if anything is unclear.*
