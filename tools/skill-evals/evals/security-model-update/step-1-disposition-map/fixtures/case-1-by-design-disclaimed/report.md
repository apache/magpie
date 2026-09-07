<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/decoder, integer overflow on the length field,
attacker controls the archive)`

Occurrences: 4 trackers over 14 months, all closed INVALID.

Stated reasons, in the team's own words:
- #211 "We don't claim memory-safety on inputs above the documented
  4 GiB limit. §1.12-D2 disclaims it explicitly."
- #240 "Same as #211 — over the documented size cap. §1.12-D2."
- #288 "§1.12-D2 again."
- #315 "Above the size cap; §1.12-D2 covers it."
