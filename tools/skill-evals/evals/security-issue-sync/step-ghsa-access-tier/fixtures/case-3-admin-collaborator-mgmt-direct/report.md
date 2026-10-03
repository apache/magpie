<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker #421 (`<tracker>`), GHSA-sourced: body names GHSA-f3rt-8n2v-k7wq on `<upstream>`.
Tracker state: `cve allocated`; CVE field = CVE-2026-32250.

Access-tier probe this run:
- `gh api "/repos/<upstream>/security-advisories?per_page=100"` → 200, list includes GHSA-f3rt-8n2v-k7wq.
- The operator is a member of the repository's security-manager team, so their tier is admin / security-manager.
- No `PATCH` has returned `403` this run.

Advisory GHSA-f3rt-8n2v-k7wq: cve_id already CVE-2026-32250; severity and CWE match the tracker.

Access drift: security-team roster member @dnguyen is missing from the advisory's `collaborating_users`.

Pending change: add @dnguyen to `collaborating_users`.
