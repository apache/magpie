<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Four subagent reports came back from a `sync all open` selector. Two trackers carry body-field updates (CWE, summary); two are pure label flips.

---

**Tracker airflow-s/airflow-s#410**

```yaml
issue: 410
title: HITL Detail visibility on shared DAG
scope_label: airflow
current_labels: [airflow, cve allocated, pr merged, security issue, rc voting]
current_milestone: 3.2.2
current_assignees: [potiuk]
fix_pr:
  url: https://github.com/apache/airflow/pull/67800
  state: merged
  merged_at: 2026-05-15T09:00:00Z
  milestone: 3.2.2
release_shipped: true
cve_id: CVE-2026-50010
process_step: 12
proposed_label_add: [fix released]
proposed_label_remove: [pr merged, rc voting]
proposed_milestone: null
proposed_assignees_add: [vatsrahul1001]
proposed_body_field_updates: []
proposed_status_comment: "Step 12 — fix released; RM hand-off to @vatsrahul1001"
proposed_reporter_email: "Release shipped notification"
blockers: []
notes: ""
```

---

**Tracker airflow-s/airflow-s#411**

```yaml
issue: 411
title: Path traversal in custom operator deserialization
scope_label: airflow
current_labels: [airflow, cve allocated, pr merged, security issue]
current_milestone: 3.2.2
current_assignees: [bob]
fix_pr:
  url: https://github.com/apache/airflow/pull/67801
  state: merged
  merged_at: 2026-05-16T09:00:00Z
  milestone: 3.2.2
release_shipped: true
cve_id: CVE-2026-50011
process_step: 12
proposed_label_add: [fix released]
proposed_label_remove: [pr merged]
proposed_milestone: null
proposed_assignees_add: [vatsrahul1001]
proposed_body_field_updates:
  - "Short public summary for publish — add upgrade target (3.2.2 or later) + WHO/WHEN/ACTION trigger conditions"
  - "CWE — rewrite bare `CWE-22` to long form `CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')`"
proposed_status_comment: "Step 12 — fix released; body cleanup for gates #1, #2, #5"
proposed_reporter_email: "Release shipped notification"
blockers: []
notes: ""
```

---

**Tracker airflow-s/airflow-s#412**

```yaml
issue: 412
title: Bulk task instance API authorization bypass
scope_label: airflow
current_labels: [airflow, cve allocated, pr merged, security issue]
current_milestone: 3.2.2
current_assignees: [carol]
fix_pr:
  url: https://github.com/apache/airflow/pull/67802
  state: merged
  merged_at: 2026-05-17T09:00:00Z
  milestone: 3.2.2
release_shipped: true
cve_id: CVE-2026-50012
process_step: 12
proposed_label_add: [fix released]
proposed_label_remove: [pr merged]
proposed_milestone: null
proposed_assignees_add: [vatsrahul1001]
proposed_body_field_updates:
  - "Reporter credited as — anonymise from `Jane Doe (internal scan)` to `anonymous` (private-scanner source)"
proposed_status_comment: "Step 12 — fix released; anonymise gate fired"
proposed_reporter_email: null
blockers: []
notes: ""
```

---

**Tracker airflow-s/airflow-s#413**

```yaml
issue: 413
title: Stale connection cache after rotation
scope_label: airflow
current_labels: [airflow, cve allocated, pr merged, security issue]
current_milestone: 3.2.2
current_assignees: [dave]
fix_pr:
  url: https://github.com/apache/airflow/pull/67803
  state: merged
  merged_at: 2026-05-18T09:00:00Z
  milestone: 3.2.2
release_shipped: true
cve_id: CVE-2026-50013
process_step: 12
proposed_label_add: [fix released]
proposed_label_remove: [pr merged]
proposed_milestone: null
proposed_assignees_add: [vatsrahul1001]
proposed_body_field_updates: []
proposed_status_comment: "Step 12 — fix released"
proposed_reporter_email: "Release shipped notification"
blockers: []
notes: ""
```
