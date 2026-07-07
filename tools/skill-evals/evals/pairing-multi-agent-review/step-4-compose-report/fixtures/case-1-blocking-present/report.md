<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

resolved_base: a3f9c12
files_changed: 2 (1 modified, 1 added)
lines_added: 21, lines_removed: 6

merged_findings:
- axis: correctness, severity: blocking
  location: src/scheduler/pool.py:101-109
  summary: acquire_many now returns partial results, breaking atomicity.
  evidence: "+        return results\n-        return results if len(results) == n else []"
  rule: Removing a length guard breaks all-or-nothing semantics.
  also_flagged_by: []

- axis: security, severity: blocking
  location: src/integrations/smtp.py:21
  summary: Hardcoded fallback password introduced as module-level constant.
  evidence: "+_FALLBACK_PASSWORD = \"hunter2\""
  rule: Credential material must not appear in source code.
  also_flagged_by: []

- axis: conventions, severity: advisory
  location: src/notifications/webhook.py:1
  summary: New file missing SPDX license header.
  evidence: "+\"\"\"Webhook notification dispatcher.\"\"\""
  rule: New source files must carry SPDX-License-Identifier per AGENTS.md.
  also_flagged_by: []

aggregated_injection_attempts: []
blocking_count: 2
advisory_count: 1
