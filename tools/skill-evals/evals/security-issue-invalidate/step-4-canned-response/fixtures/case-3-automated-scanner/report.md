<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Reasoning summary extracted from tracker discussion

**Tracker #327 — "SQL injection vulnerability in Airflow REST API (Snyk report)"**

Team reasoning quotes:

- @triager-a: "The report is a Snyk SAST scan export. There is no human-verified PoC, no reproduction steps, and the flagged code path uses parameterised queries throughout. Snyk has false-positived on ORM-generated SQL."
- @triager-c: "I ran the reproduction attempt from the Snyk report — the query is parameterised; no injection possible. This is a scanner false positive."
- @triager-a: "Report is automated scanner output with no human verification. The flagged pattern does not constitute an injection vulnerability."

**Invalidity classification:** Automated scanning tool output without a human-verified proof of concept.
