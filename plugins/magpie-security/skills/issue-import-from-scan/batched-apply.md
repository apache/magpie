<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Batched imports

Read from [Step F](SKILL.md#step-f--land-the-report-then-apply-confirmed-actions) when the approved vetted-ops policy sets `[approval] private_tracker_writes` to `batch` or `none`.

## Batching the imports

**A scan import is the bulk case batching exists for:** when the approved vetted-ops policy sets
`[approval] private_tracker_writes` to `batch` or `none`, run every confirmed import through Step 7's
[batched phases](../issue-import/apply.md#step-7--apply-confirmed-imports) under the `security-issue-import` caller,
so the creates are one confirmation and the board moves and rollup entries another, whatever the number of findings.
The evidence comments are tracker writes too: add each confirmed one to the last batch
as an `issue-comment <N> <workspace>/<id>.md` entry (the caller needs the `issue-comment` grant it already has for the rejections ledger),
instead of one `vetted-op` call each.
