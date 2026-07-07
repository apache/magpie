<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for airflow-s/airflow-s#254 (ReDoS in DAG name validation):

Labels: airflow, cve allocated
CVE: CVE-2025-38912
Milestone: 3.0.4

Discussion thread summary:
  jsmith: "Option A: replace the regex with a manual loop that short-circuits
  after the first invalid character. Fast and simple."

  mwilson: "I prefer Option B: switch to `re2` which has guaranteed linear
  time. The regex is used in four other places and fixing them all at once is
  cleaner."

  agarcia: "Option C — just add a length cap before the regex. No dependency
  change needed."

  jsmith: "Option B requires adding a new dependency to the core, which needs
  PMC sign-off. Option C doesn't address the underlying exponential
  backtracking, just limits blast radius."

  mwilson: "Still think Option B is correct long-term. Not ready to go with
  Option A just yet."

Fix PR: none yet
Security classification: valid
Open questions: dependency decision pending PMC input
