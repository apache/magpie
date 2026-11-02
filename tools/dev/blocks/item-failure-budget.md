<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Item failure budget

This applies to the read and classify phase only. One item whose state
cannot be read or classified (a missing body, an unparsable timestamp, a
404 or 410 for that item, a classifier that returns no verdict for it twice)
does not stop the sweep: record it as `failed` with a one-line reason, skip it
for the rest of the run, and carry on with the next item.
The budget is `item_failure_budget` in the config file this skill already
reads: `issue-tracker-config.md` for the issue skills,
`project.md` for the security skills, `pr-management-config.md` for the PR
skills. Its value is `<n>`, `<p>%` of the
pool, or `max(<n>, <p>%)`; unset means `max(3, 10%)`. A malformed value
stops the run before the sweep starts, with an error naming the value and no
fallback: nothing has been read, so no item is failed or unfinished; the
maintainer fixes the value and reruns the same selector.
When more items have failed than the budget allows, stop before the next item:
the pool is likely broken as a whole, not one item.

The **write phase is not budgeted**: a post, label, close or transition that
fails still stops at once, and is never retried, because a retry can duplicate
a visible action.

The recap always has three groups, failed items first in the summary line when
there are any: **completed** (with their dispositions), **failed** (each with
its reason), and **unfinished** (not reached because the budget ran out or a
write stopped the run; say which, once). End with the selector that reruns
exactly the failed and unfinished items. A sweep with no failures does not
mention the budget. Contract:
[`docs/batch-failure-budget.md`](../../../../docs/batch-failure-budget.md).
