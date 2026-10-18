<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Upstreaming a body-field parser

`setup config` can generate a project's own body-field parser for a local-files tracker whose reports are not `###` field sections
([setup → custom parser](../../setup/local-files/custom-parser.md)).
It lives at `.apache-magpie-overrides/tools/local-tracker/parsers/<name>.py`, with its fixtures beside it as `<name>.cases.jsonl`.
Another project that keeps its reports in the same layout gets it for free once it is in Magpie.

When the override picked in Step 1 is such a parser, the walk-through changes as follows:

- **Step 2 — Read.** Read the parser and its fixtures, and show the layout it implements (its `FORMAT` and `DESCRIPTION`) and its boundary rule.
  There is no framework skill to read; the framework counterpart is [`tools/body-field-contract/formats/`](../../../../../tools/body-field-contract/formats/README.md).
- **Step 3 — Decide.** A layout another project could use is upstreamable.
  One that only this project's reports have (a project name in the boundary rule, say) stays local.
  The fixtures and `SAMPLE_BODY` must hold synthetic values only: check every value against the reports' structure, and stop if one looks copied from a report — the reports are embargoed.
- **Step 4 — Design.** The shape is always *add an adapter*: `tools/body-field-contract/formats/<layout>.py` plus `<layout>.cases.jsonl`, named after the layout, not the project.
- **Step 5 — Implement.** Copy both files, run the conformance suite on the framework clone
  (`uv run --directory tools/github-body-field --project . python -m pytest tests/test_conformance.py -k format`, which covers every adapter in `formats/`),
  and list the adapter in [`formats/README.md`](../../../../../tools/body-field-contract/formats/README.md).
- **Step 7 — Cleanup.** Once the adapter ships, the project may keep its copy (the descriptor names it by path and hash)
  or replace it with the upstream file and re-run `setup config`, which shows the new hash and re-confirms it.
