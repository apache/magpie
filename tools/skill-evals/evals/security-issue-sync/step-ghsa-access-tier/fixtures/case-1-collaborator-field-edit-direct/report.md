<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #412 (`<tracker>`), GHSA-sourced: body names GHSA-7xq2-m4pv-9r3c on `<upstream>`.
Tracker state: `cve allocated`; CVE field = CVE-2026-31877; Severity = Medium; CWE = CWE-79.

Access-tier probe this run:
- `gh api "/repos/<upstream>/security-advisories?per_page=100"` → 200, list includes GHSA-7xq2-m4pv-9r3c.
- No `PATCH` has been attempted yet. Operator is not in the repo's security-manager team.

Advisory GHSA-7xq2-m4pv-9r3c as returned by the list call:
- state: triage, published_at: null
- cve_id: null
- severity: high (set by the reporter when filing)
- cwe_ids: ["CWE-79"]
- collaborating_users: every security-team roster member already present

Pending change: cve_id drift and severity drift.
Link `cve_id=CVE-2026-31877` onto the advisory and mirror the tracker's Medium severity onto it.
