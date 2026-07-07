<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Quirk: `record-publish` reads CNA_private at the wrong nesting.
Searches run:
- `gh search prs --repo apache/magpie --state all "CNA_private body envelope"` → 1 OPEN PR
  #724 "fix(cve-tool-vulnogram): read/write CNA_private under the read API's body envelope",
  which fixes exactly this, still under review.
The open PR matches the quirk one-to-one.
