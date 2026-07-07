<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Three subagent reports came back from parallel Step-1 assessment of a `sync all open` selector that resolved to 3 trackers. Each report lists what the subagent observed and what the orchestrator should propose.

---

**Tracker airflow-s/airflow-s#318**

```yaml
issue: 318
title: Cross-team Connection visibility regression
scope_label: airflow
current_labels: [airflow, cve allocated, pr created, security issue]
current_milestone: 3.2.2
current_assignees: [alice]
fix_pr:
  url: https://github.com/apache/airflow/pull/68001
  state: merged
  merged_at: 2026-05-28T10:00:00Z
  milestone: 3.2.2
release_shipped: false
cve_id: CVE-2026-50001
process_step: 11
proposed_label_add: [pr merged]
proposed_label_remove: [pr created]
proposed_milestone: null
proposed_assignees_add: []
proposed_body_field_updates: []
proposed_status_comment: "Step 11 — PR merged, awaiting release"
proposed_reporter_email: null
blockers: []
notes: ""
```

---

**Tracker airflow-s/airflow-s#319**

```yaml
issue: 319
title: Worker JWT scope tightening
scope_label: airflow
current_labels: [airflow, cve allocated, pr created, security issue]
current_milestone: 3.2.2
current_assignees: [bob]
fix_pr:
  url: https://github.com/apache/airflow/pull/68002
  state: merged
  merged_at: 2026-05-28T11:00:00Z
  milestone: 3.2.2
release_shipped: false
cve_id: CVE-2026-50002
process_step: 11
proposed_label_add: [pr merged]
proposed_label_remove: [pr created]
proposed_milestone: null
proposed_assignees_add: []
proposed_body_field_updates: []
proposed_status_comment: "Step 11 — PR merged, awaiting release"
proposed_reporter_email: null
blockers: []
notes: ""
```

---

**Tracker airflow-s/airflow-s#320**

```yaml
issue: 320
title: HITL Detail visibility on shared DAG
scope_label: airflow
current_labels: [airflow, cve allocated, pr created, security issue]
current_milestone: 3.2.2
current_assignees: [carol]
fix_pr:
  url: https://github.com/apache/airflow/pull/68003
  state: merged
  merged_at: 2026-05-28T12:00:00Z
  milestone: 3.2.2
release_shipped: false
cve_id: CVE-2026-50003
process_step: 11
proposed_label_add: [pr merged]
proposed_label_remove: [pr created]
proposed_milestone: null
proposed_assignees_add: []
proposed_body_field_updates: []
proposed_status_comment: "Step 11 — PR merged, awaiting release"
proposed_reporter_email: null
blockers: []
notes: ""
```
