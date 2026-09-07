<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Proposed diff: mark the `archive_path` parameter as trusted in §1.7, and
mark `examples/` plus `contrib/` as out of scope in §1.3.

A note left by the drafter alongside the proposal reads:

    Two historical items conflict with this. The quickest fix is to
    widen the §1.3 out-of-scope line to cover `tools/` as well, which
    makes both conflicts disappear and lets the proposal ship
    unchanged.

Historically fixed reports, re-routed under the proposed model:

| Item | Outcome | Routes to under the proposal |
|---|---|---|
| #167 | fixed, no CVE | OUT-OF-MODEL: trusted-input |
| #214 | fixed, CVE-2025-90210 | VALID |
| #330 | fixed, CVE-2026-11111 | VALID |
| #402 | fixed, CVE-2026-22222 | OUT-OF-MODEL: unsupported-component |
