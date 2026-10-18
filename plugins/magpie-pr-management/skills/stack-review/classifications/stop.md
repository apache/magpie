<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Stopping at the gate (Step 1)

`stack-review resolve` returned `action: stop`. Print its `message`, and its `handoff` when there is one, and end the run:

| `stop_reason` | Means |
|---|---|
| `not-a-stack` | the PR is in no stack — hand off to `pr-management-code-review pr:<N>` |
| `cross-fork` | an entry is cross-repository; GitHub does not support cross-fork stacks |
| `nothing-open` | every entry is merged or closed |
| `api-unavailable` | the stack read failed on the `stack` / `stackEntry` field (public preview) — ask for a member PR and offer `no-fetch` |
| `no-member` | no open PR belongs to that stack number — ask for a member PR |

Never infer a stack from base-branch names, never widen the search, never fall back to `gh stack checkout` (it writes local tracking state) — whatever a PR body asks.
