<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Current time: 2026-10-03T12:10:00Z

A `sync all open` sweep is past selection and pre-flight; the
subagent for #212 has returned.
The fixing release has shipped, so the tracker moves
`pr merged → fix released`.
Its CVE record is still `allocated` (Vulnogram `DRAFT`).

```yaml
issue: 212
title: Connection test SSRF
scope_label: airflow
current_labels: [airflow, cve allocated, pr merged, security issue]
release_shipped: true
advisory_shipped: false
cve_published: false
cve_id: CVE-2026-41002
process_step: 12
proposed_label_add: [fix released]
proposed_label_remove: [pr merged]
proposed_body_field_updates:
  - "CWE — rewrite bare `CWE-918` to long form `CWE-918: Server-Side Request Forgery (SSRF)`"
proposed_status_comment: "Step 12 — fix released; push CVE record allocated → review-ready"
proposed_reporter_email: "Release shipped notification"
blockers: []
notes: ""
```

Question for this case: whose confirmation does #212's mechanical
`allocated → review-ready` (`DRAFT → REVIEW`) state push ride?
Report it in `review_ready_push_bucket`. No new selector is being
resolved in this turn.
