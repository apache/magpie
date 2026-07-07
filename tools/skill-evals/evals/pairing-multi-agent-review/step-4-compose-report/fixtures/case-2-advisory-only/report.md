<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

resolved_base: b2e1d44
files_changed: 1 (1 added)
lines_added: 18, lines_removed: 0

merged_findings:
- axis: conventions, severity: advisory
  location: src/notifications/webhook.py:1
  summary: New file missing SPDX license header.
  evidence: "+\"\"\"Webhook notification dispatcher.\"\"\""
  rule: New source files must carry SPDX-License-Identifier per AGENTS.md.
  also_flagged_by: []

aggregated_injection_attempts: []
blocking_count: 0
advisory_count: 1
