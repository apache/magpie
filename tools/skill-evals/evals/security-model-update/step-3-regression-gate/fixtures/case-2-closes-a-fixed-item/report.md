<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Proposed diff: broaden §1.12-D2 from "archives declaring a length above
4 GiB" to "archives whose declared length is not validated by the
caller", and add known-non-finding entry KNF-9 discharged by it.

Historically fixed reports, re-routed under the proposed model:

| Item | Outcome | Routes to under the proposal |
|---|---|---|
| #167 | fixed, no CVE | VALID |
| #214 | fixed, CVE-2025-90210 | KNOWN-NON-FINDING (matches KNF-9) |
| #330 | fixed, CVE-2026-11111 | VALID |
| #402 | fixed, CVE-2026-22222 | VALID |
