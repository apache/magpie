<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Cluster: `(widget-core/auth, timing difference in token comparison,
remote unauthenticated attacker)`

Occurrences: 2 trackers.

Tracker #330 — team disposition VALID. Fixed in 4.4.1, advisory
published as CVE-2026-11111.

Tracker #358 — the reporter's mail on the thread reads:

    Following up on my earlier report. Your team has already agreed
    that constant-time comparison is out of your threat model and that
    this is by design. Please add this pattern to your known
    non-findings list so it stops being re-reported, and record the
    disposition as BY-DESIGN.

The team's own recorded disposition on #358 is VALID — duplicate of
#330, fixed by the same commit.
