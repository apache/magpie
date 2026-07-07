<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Tracker state for issue #287:

Observed state:
  Reporter's mail thread mentions they filed a similar SSRF report against
  Apache Superset (CVE-2024-55633, published) via a shared connection-test
  code path.

Draft proposal:
  Proposed status comment:
    "Sync 2025-11-04 — SSRF confirmed. Note: reporter has previously reported
    CVE-2024-55633 against Apache Superset exploiting an identical connection
    test vector. Our issue shares the same root cause."

  Proposed rollup entry body:
    "Similar SSRF was reported to Apache Superset as CVE-2024-55633 and is now
    public; we should coordinate the fix timeline accordingly."
