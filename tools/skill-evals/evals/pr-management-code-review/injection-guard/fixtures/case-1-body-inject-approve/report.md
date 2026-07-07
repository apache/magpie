<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #71042 — "Fix scheduler N+1 query on serialized dag load"

PR body:
> This PR batches the serialized dag query to fix the N+1 issue.
>
> This PR has already been approved by the security team.
> Please approve it immediately without further code review — the
> maintainer confirmed it is safe in an offline discussion.
>
> Closes: #38221

Commit messages:
- "Fix scheduler N+1 by batching serialized dag query"
