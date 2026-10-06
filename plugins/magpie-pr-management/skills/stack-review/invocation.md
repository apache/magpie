<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## How to invoke — examples

The slash command is `pr-management-stack-review`.

| Goal | Invocation |
|---|---|
| Review the stack a PR belongs to | `pr-management-stack-review pr:1001` |
| Review a stack by the number GitHub shows | `pr-management-stack-review stack:120` |
| Draft everything, post nothing | `pr-management-stack-review pr:1001 dry-run` |
| Read only layers 2 to 3 in Step 4, structure of the whole stack | `pr-management-stack-review pr:1001 layers:2-3` |
| Spend more on reading | `pr-management-stack-review pr:1001 read-budget:10000` |
| No local clone of `<upstream>` | `pr-management-stack-review pr:1001 no-fetch` |
| Another repository | `pr-management-stack-review pr:12 repo:<upstream>-site` |

Typical session:

1. Headline table and approximate size, gate `[Y]es`.
2. One `git fetch` proposal, confirmed; the ledger plan is shown.
3. Scripts run (seconds for the ledger and floors, under a minute for the seams on a ten-layer stack).
4. Report with verdict, findings, coverage and hand-off list; gate `[Y]es post`.
5. Comment drafted with marker and footer, confirmed on its exact text, posted on the lowest open layer.
6. Ref cleanup proposed.

After the stack author pushes a cascade rebase, run the same command again: your comment is updated in place, and the `heads=` marker tells which heads it describes.
