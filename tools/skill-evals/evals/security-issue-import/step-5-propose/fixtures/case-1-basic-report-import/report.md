<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

### Step 3 classification

class: Report
threadId: AAMkAGQ8xZ3mPqRs
reporter: researcher@example.com

### Step 4 field extract

```json
{
  "title": "DAG-scoped API user can read XCom entries from unauthorized DAGs",
  "reporter_name": "Alex Researcher",
  "reporter_email": "researcher@example.com",
  "affected_versions": "2.9.x, 2.10.x",
  "component": "REST API / XCom endpoint",
  "summary": "GET /api/v1/dags/{dag_id}/dagRuns/{run_id}/taskInstances/{task_id}/xcomEntries returns XCom data for any DAG regardless of the caller's DAG-scoped permissions.",
  "steps_to_reproduce": "1. Create a user with DAG-scoped read access to dag_a only.\n2. Call GET /api/v1/dags/dag_b/dagRuns/.../xcomEntries.\n3. Observe XCom data from dag_b returned without error.",
  "reporter_cvss": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
  "pr_with_fix": null,
  "ghsa_id": null,
  "security_list_thread": "https://lists.apache.org/thread/AAMkAGQ8xZ3mPqRs"
}
```

### Step 2b prior-rejection signal

```json
{
  "prior_rejection_found": false,
  "recommendation": "new_ground"
}
```

### Step 2a fuzzy-duplicate matches

No STRONG or MEDIUM matches found.
