<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Budget discipline

Per session: one paginated sweep of open PRs (`gql-cr-open`) and the
once-per-session reads `queue` asks for (the ownership file, team rosters,
the viewer's recent commits). Per reviewed PR: the full read (`gql-cr-pr`),
the diff, 0–3 path-history reads for reviewer suggestions, the liveness read
before posting, and one post — `session record --calls` tallies them and
flags a session past ~100 calls. That is mis-batching (most likely a
re-fetch per finding): stop and fix the call pattern; never sleep and retry.
