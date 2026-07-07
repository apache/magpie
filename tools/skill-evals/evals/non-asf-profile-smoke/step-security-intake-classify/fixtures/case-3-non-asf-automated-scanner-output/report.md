<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Project config: Velox Stream (non-ASF community project)
  security_inbox.kind: ghsa-inbox
  forwarders.enabled: []
  cve_authority.tool: mitre-form
  governance.cve_allocation_gate: security-team-member

Automated scanner output forwarded to the project security inbox
(no ASF-specific label names; uses project-local scanner tooling):

From: scanner-noreply@ci.velox-stream.example.io
To: security@velox-stream.example.io
Subject: [velox-stream-scanner] Dependency scan report 2026-06-28

velox-stream automated dependency scanner — weekly report

Scan completed: 2026-06-28T03:15:00Z
Repository: velox-community/velox-stream
Scanner: Grype 0.78.0

=== HIGH severity findings ===

FINDING: CVE-2025-12345 in cryptography==41.0.0
  Severity: HIGH (CVSS 8.1)
  Fixed in: cryptography==42.0.0
  Status: already tracked in GHSA-abc1-def2-3456

FINDING: GHSA-xxxx-yyyy-zzzz in requests==2.28.2
  Severity: HIGH (CVSS 7.5)
  Fixed in: requests==2.31.0
  Status: not yet tracked

=== MEDIUM severity findings (3 items) ===
  [omitted for brevity]

Total: 5 findings (2 HIGH, 3 MEDIUM)
