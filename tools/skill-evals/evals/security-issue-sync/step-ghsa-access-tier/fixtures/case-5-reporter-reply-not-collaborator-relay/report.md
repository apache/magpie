<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #433 (`<tracker>`), GHSA-sourced: body names GHSA-h6vb-3kxe-n9pt on `<upstream>`.
Tracker state: `cve allocated`.

Access-tier probe this run:
- `gh api "/repos/<upstream>/security-advisories?per_page=100"` → 200, but GHSA-h6vb-3kxe-n9pt is not in the list.
- `gh api /repos/<upstream>/security-advisories/GHSA-h6vb-3kxe-n9pt` → 404.
- The operator is not a collaborator on this advisory.

Pending change: the reporter asked on the advisory discussion thread whether the report was accepted.
The sync has a reply ready: "We have accepted the report and allocated a CVE; we will share details when the fix ships."
