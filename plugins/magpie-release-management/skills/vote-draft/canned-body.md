<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# A project `[VOTE]` template (`canned_body`)

When `<project-config>/canned-responses.md` has a `[VOTE]` template block, save it to a file and pass it as `--canned-body`.
The render substitutes the metadata placeholders (`<vote_list>`, `<Product Name>`, `<version>`, `<version>-rcN`, `<staging_url>`, `<svn_revision>`, `<tag_url>`, `<changelog_url>`, `<keys_url>`, `<vote_window_hours>`, `<swhid>`, `<atr_candidate_url>`, `<planning_issue>`, `<RM name>`)
and appends the `[EXPEDITED]` / `[SKIP-VERIFY]` notices when those overrides are in force.

The *How to verify* section is part of every `[VOTE]`, whichever backend sends it and whether the body came from the default template or from `canned_body`:
a PMC member reading the thread on their phone must find the agentic one-liner, the human-readable page, and the reproducibility record without opening the tracker.
When `canned_body` lacks the section, append it and tell the RM the project's canned block should gain it.
The *Agentic path* paragraph is fixed text describing what `verify-rc` does.
Keep it verbatim, including the SWHID and convenience-artefact clauses, even when the planning issue recorded no SWHID or the project declares no convenience artefacts;
only the *Reproducibility record* lines and the *Convenience artefacts* block vary with what the report provides.

The render does the appending: `verify_section_appended: true` and a `warnings` entry mean it added the section; pass the warning on to the RM.

When `canned_body` already has the section, the render keeps the project's text and adds nothing, so that section must itself carry the mandatory items.
It always warns that the generated section was not added, and lists in `canned_verify_missing` (one `warnings` entry each) every mandatory item it does not find:
this RC's SWHID (via `<swhid>`; a SWHID line when the planning issue recorded none), the ATR candidate page under `vote_backend = atr` (via `<atr_candidate_url>`),
and the `--trusted-hardware` reminder under `signing_mode = ci-automated`.
Pass each warning on to the RM; the project's canned block should gain what is missing.
