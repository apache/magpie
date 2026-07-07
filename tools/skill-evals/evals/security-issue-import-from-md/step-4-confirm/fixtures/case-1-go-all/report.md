<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Proposal surfaced to user

ai-security-review-2025-05-01.md — 3 findings parsed.

| # | Severity | Category                       | Title                                                             | Possible duplicate |
|---|----------|--------------------------------|-------------------------------------------------------------------|--------------------|
| 1 | HIGH     | Insecure Deserialization / RCE | Arbitrary callable invocation via pickle deserialization in XCom  | (none)             |
| 2 | HIGH     | Broken Access Control          | RCE via template rendering — conf object exposed in Jinja2        | (none)             |
| 3 | MEDIUM   | Server-Side Request Forgery    | SSRF via worker-supplied hostname in remote logging endpoint       | airflow-s/airflow-s#287 |

Default disposition: import all 3 as `Needs triage`.
Reply with one of: `go` / `proceed` / `yes, all` — import every finding above. `skip <N>` — drop finding N. `cancel` / `none` — bail; no trackers created.

## User reply

go
