<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Eval task

You are evaluating the **bulk-mode orchestration** step of the
`security-issue-sync` skill — specifically the bucket-and-walk
decision the orchestrator makes after parallel subagents return
their per-tracker reports.

The skill's bulk mode splits trackers into two buckets after
assessment:

- **CVE-affecting** — any tracker whose proposal includes a body-field
  update that lands in the regenerated CVE JSON
  (Title, Short public summary for publish, CWE, Severity,
  Affected versions, Reporter credited as, Remediation developer,
  PR with the fix, Public advisory URL). Each CVE-affecting tracker
  is walked **individually**: own proposal, own confirmation, own
  apply, in ascending tracker-number order.
- **Non-CVE-affecting** — only label flips, milestone touches,
  assignee swaps, project-board column moves, status-rollup
  entries, reporter Gmail drafts, RM hand-off comments. Bundled
  into one combined proposal.

Given the per-tracker subagent reports in the user turn, return
ONLY valid JSON with this shape:

```json
{
  "cve_affecting": [<issue_number>, ...],
  "non_cve_affecting": [<issue_number>, ...],
  "walk_order": [<issue_number>, ...]
}
```

Field rules:

- `cve_affecting`: every tracker whose `proposed_body_field_updates`
  list contains at least one entry that names a CVE-publication
  field (Title, Short public summary for publish, CWE, Severity,
  Affected versions, Reporter credited as, Remediation developer,
  PR with the fix, Public advisory URL). Order is not significant
  in this list.
- `non_cve_affecting`: every tracker that is NOT in `cve_affecting`.
  Order is not significant in this list.
- `walk_order`: ascending tracker-number order over `cve_affecting`.
  Empty list when `cve_affecting` is empty.

Do not include any text outside the JSON object.
