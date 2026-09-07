<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/api, callers can pass a mutable buffer the library
retains beyond the call, in-process caller)`

Occurrences: 3 trackers over 8 months.

Stated reasons and outcomes:
- #212 DEFENSE-IN-DEPTH — "Not a violation of anything we claim, but we
  added a defensive copy in 4.2. No CVE."
- #248 DEFENSE-IN-DEPTH — "Same class. Hardened in 4.3."
- #305 DEFENSE-IN-DEPTH — "Hardened; no advisory."

The team proposes adding this to the known non-findings so the scanner
stops re-reporting it.
