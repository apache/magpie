<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #430 (`<tracker>`), GHSA-sourced: body names GHSA-q8mz-5tdc-w2jh on `<upstream>`.
Tracker state: `pr merged`; the fix PR is merged, a release is scheduled.

Access-tier probe this run:
- `gh api "/repos/<upstream>/security-advisories?per_page=100"` → 200, list includes GHSA-q8mz-5tdc-w2jh.
- Operator is an advisory collaborator on GHSA-q8mz-5tdc-w2jh (field edits succeed earlier this run); not in the security-manager team.
- Advisory `html_url`: https://github.com/<upstream>/security/advisories/GHSA-q8mz-5tdc-w2jh

Pending change: the reporter asked on the advisory discussion thread when the fix ships.
The sync has a status-update reply ready for the reporter: "The fix has been merged and will be in the next release; we will update this advisory when it is out."
