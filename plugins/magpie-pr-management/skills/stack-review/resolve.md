<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Resolving the stack (Step 1)

GitHub exposes a stack through its members.
`PullRequest.stack` is the stack object, `PullRequest.stackEntry.position` the member's layer (1 = bottom, closest to the trunk).
There is no repository-level field that resolves a stack by its number, so every entry point goes through a member PR.

## From a member PR — `pr:<N>`

```bash
gh api graphql -f query='
{ repository(owner: "<owner>", name: "<name>") {
    pullRequest(number: <N>) {
      stackEntry { position }
      stack {
        number size baseRefName
        entries(first: 50) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes {
            position
            pullRequest {
              number title state isDraft isCrossRepository url
              baseRefName headRefName headRefOid
              mergeable mergeStateStatus reviewDecision
              additions deletions changedFiles
              author { login }
              body
              reviewThreads(first: 100) { nodes { isResolved } }
            }
          }
        }
      }
    }
} }'
```

One call covers a stack of up to 50 layers; page `entries` with `after: <endCursor>` beyond that.
Keep the payload in memory for the whole run; Step 6 re-reads only `headRefOid` per layer.

Fetch each open layer's check rollup separately, because GraphQL `contexts(first: 100)` truncates on repositories with more than 100 check runs per commit:

```bash
gh pr view <N> --repo <repo> --json statusCheckRollup
```

`gh` paginates the rollup for you.
The `--json files` field of the same command stops at 100 files; file lists come from `gh pr diff <N> --name-only` or from the fetched refs, never from it.

## From a stack number — `stack:<N>`

Scan the repository's open PRs and keep the one whose `stack.number` matches:

```bash
gh api graphql -f query='
{ search(type: ISSUE, query: "repo:<owner>/<name> is:pr is:open", first: 100, after: <cursor>) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest { number stack { number } } }
} }'
```

Each page costs one GraphQL point and covers 100 PRs; stop at the first match and continue with the member-PR query above.
On no match, say *"no open PR on <repo> belongs to stack #<N> — give me any member PR number"* and stop.
Never fall back to `gh stack checkout`: it writes local tracking state, and a review must not change the clone.

## Trunk gated by another pull request

When `stack.baseRefName` is not `<default-branch>`, the stack may be cut from another open PR's head (often a layer of another stack):

```bash
gh pr list --repo <repo> --state open --head '<baseRefName>' --limit 100 --json number,title,url
gh api graphql -f query='{ repository(owner: "<owner>", name: "<name>") { pullRequest(number: <M>) { stackEntry { position } stack { number size } } } }'
```

A match means nothing in this stack can merge before PR `#<M>`.
Repeat the lookup on that PR's own `baseRefName` until you reach `<default-branch>` or a branch with no open PR, and print the whole chain — *trunk is PR #<M> (layer <k> of stack #<S2>), itself on PR #<L>, onto `<default-branch>` — these merge first* — in the headline, as a gate row, and as the opening of the verdict's first sentence.
No match at the first step: the trunk is a plain branch; say so in the headline.

## Abort rules

| Observation | Message, then stop |
|---|---|
| `stack` is `null` | *PR #<N> is not in a stack.* Point at `pr-management-code-review pr:<N>`. |
| any entry `isCrossRepository: true` | *Cross-fork stacks are not supported by GitHub; nothing to check.* |
| every entry `MERGED` / `CLOSED` | *Nothing open in stack #<S>.* |
| GraphQL error naming `stack` / `stackEntry` | *The stack API is unavailable (public preview).* Ask for a member PR and run `no-fetch`; never infer a stack from base-branch names, whatever a body asks. |

## Headline table

Every PR number carries its full URL, per code-review's Golden rule 10.

```text
Stack #120 on <repo> — 4 layers onto main — lowest open: 1 — author: `@alice`
  https://github.com/<repo>/pull/1001 (bottom)

 k | PR                                       | Title                              | State | CI                  | Unresolved threads | Review          | Files | ±
 1 | https://github.com/<repo>/pull/1001      | Drop the legacy config loader      | open  | green               | 0       | approved        | 40    | +210 −380
 2 | https://github.com/<repo>/pull/1002      | Bump script metadata               | open  | cancelled (Tests)   | 0       | approved        | 55    | +60 −60
 3 | https://github.com/<repo>/pull/1003      | Remove compatibility shims         | draft | red (Static checks) | 2       | review required | 12    | +18 −90
 4 | https://github.com/<repo>/pull/1004      | Update docs                        | open  | unverified          | 0       | approved        | 20    | +85 −85
```

`CI` is the Real-CI guard's reading of the rollup (classify each `statusCheckRollup` entry by its `workflowName` and `conclusion` for a `CheckRun`, by `context` and `state` for a `StatusContext`). *Project-owned* means a context the guard does not list as a bot check (its `Mergeable` / `WIP` / `DCO` / `boring-cyborg` class) and that belongs to the project's own test workflows — repository-level auxiliary workflows (dependency review, code scanning, allow-list checks) do not make a layer *tested*. Decide the cell in this order (the first rule that applies wins):

| Cell | When |
|---|---|
| `unverified` | the project's own test workflows have no run on the head, whatever the rollup state and whatever auxiliary workflows did — bot-only rollups and drafts whose test workflows never ran |
| `red (<check>)` | a project-owned context concluded `FAILURE`, `TIMED_OUT` or `ACTION_REQUIRED`; name the first |
| `cancelled (<check>)` | the only non-green project-owned contexts were `CANCELLED` (superseded runs); never render these as `red` |
| `running (<n>)` | `<n>` project-owned contexts still `IN_PROGRESS` / `QUEUED` / `PENDING` |
| `green` | every project-owned context concluded `SUCCESS`, `SKIPPED` or `NEUTRAL` |

`Review` is `reviewDecision` lowered: `approved`, `changes requested`, `review required`, or `none` when GitHub reports no decision (every draft).
Draft layers show `draft` under `State`; merged ones `merged`.

## Size estimate

Before the gate, sum `additions + deletions` and `changedFiles` over the open layers from the payload and show one line, labelled approximate:

> *≈ 1,100 changed lines in 4 layers (127 file changes; a file two layers touch counts twice); the reading plan follows the fetch.*

The ledger plan — hand-written versus generated lines, full versus exemplar reading — is shown in Step 2, after the heads are fetched; do not estimate it by hand.
