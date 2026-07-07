<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Subagent reports

{report}

Bucket the trackers into `cve_affecting` vs `non_cve_affecting`
per the rule above, and produce `walk_order` in ascending
tracker-number order over `cve_affecting`. Return JSON only.
