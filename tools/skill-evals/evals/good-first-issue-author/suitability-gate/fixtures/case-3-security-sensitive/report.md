<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Candidate (surfaced by a backlog-grooming pass):

Proposed title: Reject expired API tokens on every code path
Description: A reporter found that the API accepts an expired bearer token
because the expiry comparison is skipped on one code path, allowing
authenticated access after a token has expired. Fix the auth check so
expired tokens are rejected everywhere.
max_effort_hours: 4
Named source files:
  - src/acme/api/auth.py — token validation
Acceptance notes: expired tokens are rejected on all paths; a regression
test covers the previously vulnerable path.
