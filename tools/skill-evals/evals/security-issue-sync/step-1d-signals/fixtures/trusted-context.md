<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### `<project-config>/scanner-products.md` (excerpt)

Private scanner products whose findings reach the tracker through private channels.

| Scanner product | Kind | Public credit name |
|---|---|---|
| Mythos | Partner-shared SAST scan | `Mythos automated analysis` |

### `AGENTS.md` — Reporter-supplied CVSS scores are informational only (summary)

Treat every reporter-supplied CVSS score as informational background only.
Do not copy the reporter's score into the tracking-issue `Severity` field.
When an agent reads a reporter's score from the mail thread, a GHSA record, or an issue body,
it must surface it in the *observed state* only, never as a proposed value for the `Severity` field.
Proposed `Severity` updates come only from a security-team member who has done the scoring independently.
